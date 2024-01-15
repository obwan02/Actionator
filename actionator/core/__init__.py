from starlette.responses import JSONResponse
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.templating import Jinja2Templates
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket
from starlette.endpoints import WebSocketEndpoint
from pathlib import Path
from typing import Iterable
from io import TextIOBase
from threading import Thread
from queue import Queue
import typing
import inspect
import pydantic
import asyncio

class Message(pydantic.BaseModel):
    for_func: str
    msg_type: typing.Literal["line"]
    stream: typing.Literal["stdout", "stderr", "status"]

    msg: str


class WSIOWrapper(TextIOBase):
    """
    A small wrapper around a WebSocket to make
    it usable as an IO-like object. TextIOBase takes care of 
    most of the hard work for us, and implements most relevant methods
    with sane defaults.

    This wrapper will send any data written over 
    """

    def __init__(self, msg_queue: Queue, for_func: str, stream: typing.Literal["stdout", "stderr"]="stdout"):
        self.msg_queue = msg_queue
        self.for_func = for_func
        self.stream = stream
        
        self._line_buffer = []

    def writable(self):
        return True

    def write(self, data: str):

        for line in data.splitlines(keepends=True):
            if line.endswith("\n"):
                self._line_buffer.append(line.rstrip("\r\n"))
                total_msg = "".join(self._line_buffer)
                self._line_buffer.clear()

                msg = Message(for_func=self.for_func, msg_type="line", stream=self.stream, msg=total_msg)
                self.msg_queue.put(msg)
            else:
                self._line_buffer.append(line)

                
    def update_status(self, msg: str):
        self.msg_queue.put(Message(for_func=self.for_func, msg_type='line', stream='status', msg=msg))
            
class MultiWSWriter(TextIOBase):
    def __init__(self, websockets: Iterable[WebSocket], max_queue_size=100_000):
        self.websockets = websockets
        self.msg_queue = Queue(max_queue_size)
        self.ws_io_thread = None

    def append_ws(self, ws: WebSocket):
        self.websockets.append(ws)

    def remove_ws(self, ws: WebSocket):
        self.websockets.remove(ws)

    def output_io_for(self, for_func: str, stream: typing.Literal["stdout", "stderr"]="stdout") -> WSIOWrapper:
        return WSIOWrapper(self.msg_queue, for_func, stream=stream)

    def start_ws_io_loop(self):
        if self.ws_io_thread is None:
            self.ws_io_thread = Thread(target=self._ws_io_thread_loop, daemon=True)
            self.ws_io_thread.start()

    def _ws_io_thread_loop(self):
        async def _inner():
            while True:
                msg: Message = self.msg_queue.get()
                for ws in self.websockets:
                    await ws.send_text(msg.model_dump_json())

        asyncio.run(_inner())


class RegisteredFunc:
    
    def __init__(self, func: typing.Callable, actionator, gen_output_io=False) -> None:
        self.func = func
        self._actionator = actionator
        self.gen_output_io = gen_output_io

    @property
    def api_path(self):
        return f'{self._actionator.api_prefix}/{self.name}'

    @property
    def html_start_form_path(self):
        return f'/parts/{self.name}'

    @property
    def name(self):
        return self.func.__name__
    
    @property 
    def fn_arg_types(self):
        arg_types = typing.get_type_hints(self.func)
        if "return" in arg_types:
            del arg_types['return']
        if self.gen_output_io and 'output_io' in arg_types:
            del arg_types['output_io']

        return arg_types
    
    @property
    def fn_pydantic_model(self):
        if hasattr(self, '_pydantic_model'):
            return self._pydantic_model
        
        self._pydantic_model = type(f'{self.name}_Model', (pydantic.BaseModel,), {"__annotations__": self.fn_arg_types})
        return self._pydantic_model
    


async def call_registered_func(func: RegisteredFunc, request: Request, output_io: WSIOWrapper):
    sig = inspect.signature(func.func)
    sig = sig.replace(parameters=(param for param in sig.parameters.values() if param.name != "output_io"))
    if len(sig.parameters) != len(func.fn_arg_types):
        raise NotImplementedError("Untyped function parameters are not currently supported ...")
        
    model = func.fn_pydantic_model.model_validate_json(await request.body())
    params = model.model_dump()

    if func.gen_output_io:
        params["output_io"] = output_io

    if inspect.iscoroutinefunction(func.func):
        await func.func(**params)

    elif inspect.isasyncgenfunction(func.func):
        async for status in func.func(**params):
            output_io.update_status(status.encode("utf-8"))

    elif inspect.isgeneratorfunction(func.func):
        for status in func.func(**params):
            output_io.update_status(status.encode("utf-8"))

    else:
        func.func(**params)

class Actionator:
    def __init__(self, api_prefix="/api/v1"):
        self.registered_funcs: list[RegisteredFunc] = []
        self.api_prefix = api_prefix
        self.wss_writer = MultiWSWriter([])

    def fn(self, gen_output_io=False):
        """
        A decorator to register a function. This does a couple of things.
        Firstly, it makes the function accessible through RPC when API is generated.
        Secondly, when a frontend is generated (if a frontend is generated), it will create
        an item.

        Args:
            gen_output_io: bool - If True, a parameter called output_io will be passed, as a keyword
                argument to the annotated function. This is a subclass of TextIOBase, and most things requiring
                a file-like object will accept this as input. Anything written to this object will be sent 
                to the user over WebSockets.
        """
        
        def wrapper(func):
            self.registered_funcs.append(RegisteredFunc(func, self, gen_output_io=gen_output_io))
            return func

        return wrapper

    def _js_create_api_endpoints(self) -> Iterable[Route]:
        routes = []


        for func in self.registered_funcs:
            output_io = self.wss_writer.output_io_for(func.name)

            async def endpoint(req: Request):
                await call_registered_func(func, req, output_io)
                return JSONResponse({})

            # TODO: Add function name as an overridable
            # parameter when registering function
            routes.append(
                Route(func.api_path, endpoint=endpoint, methods=["POST"])
            )
            
        return routes


    def _js_create_html_part_routes(self, templates: Jinja2Templates):
        routes = []
        for func in self.registered_funcs:
            def start_form(req: Request):
                return templates.TemplateResponse(req, 'start_form.html', {
                    'inputs': [{'type': 'text', 'name': name} for name in func.fn_arg_types],
                    'func': func,
                })
            
            routes.append(Route(func.html_start_form_path, endpoint=start_form, methods=['GET']))
            
        return routes


    def generate_js(
        self,
        template_dir: Path,
    ) -> Starlette:

        templates = Jinja2Templates(template_dir)

        def action_bar_template(req: Request):
            return templates.TemplateResponse(req, 'action_bar.html', {
                'funcs': self.registered_funcs
            })


        actionator = self
        class WSEndpoint(WebSocketEndpoint):
            encoding = "json"

            async def on_connect(self, websocket: WebSocket) -> None:
                await websocket.accept()
                actionator.wss_writer.append_ws(websocket)
                
            async def on_disconnect(self, websocket: WebSocket, close_code: int) -> None:
                actionator.wss_writer.remove_ws(websocket)

        routes = self._js_create_api_endpoints() + self._js_create_html_part_routes(templates) + [Route('/parts/action_bar', endpoint=action_bar_template, methods=["GET"]), WebSocketRoute('/ws', endpoint=WSEndpoint)]
        print(routes)
        api = Starlette(routes=routes)

        self.wss_writer.start_ws_io_loop()
        
        # for func in self.registered_funcs:
        #     with open(gen_dir / f"{func.__name__}.html", "w") as f:
        #         html_tree = BeautifulSoup()
        #         html_tree.append(
        #             generate_inputform_html_for_func(func, self.get_route_name(func))
        #         )
        #         f.write(str(html_tree))

        return api

    def get_api_route_name(self, func):
        return f"{self.api_prefix}/{func.__name__}"

    def generate_native():
        raise NotImplementedError("Native app support hasn't been implemented yet")