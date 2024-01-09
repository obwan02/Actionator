from starlette.applications import Starlette
from starlette.requests import Request
from starlette.templating import Jinja2Templates
from starlette.routing import Route
from starlette import responses
from pathlib import Path
from typing import Iterable
import typing
import inspect

class RegisteredFunc:
    
    def __init__(self, func: typing.Callable, actionator) -> None:
        self.func = func
        self._actionator = actionator

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

        return arg_types
    
    
def call_registered_func(func: RegisteredFunc, request: Request):
    sig = inspect.signature(func)
    if len(sig.parameters) != len(func.fn_arg_types):
        raise NotImplementedError("Untyped function parameters are not currently supported ...")

    if len(func.fn_arg_types) == 0:
        return {}
    if len(func.fn_arg_types) == 1:
        key, value = next(func.fn_arg_types.items())
        func(key=value)
        


class Actionator:
    def __init__(self, api_prefix="/api/v1"):
        self.registered_funcs: list[RegisteredFunc] = []
        self.api_prefix = api_prefix

    def fn(self, func):
        """
        A decorator to register a function. This does a couple of things.
        Firstly, it makes the function accessible through RPC when API is generated.
        Secondly, when a frontend is generated (if a frontend is generated), it will create
        an item.

        Args:
            func: The function that is being registered
        """
        self.registered_funcs.append(RegisteredFunc(func, self))
        return func

    def _js_create_api_endpoints(self) -> Iterable[Route]:
        routes = []
        for func in self.registered_funcs:
            
            args_types = func.fn_arg_types

            if inspect.iscoroutinefunction(func.func):

                async def endpoint(req: Request):
                    json = await req.json()
                    return responses.JSONResponse(await func.func(obj))

            elif inspect.isasyncgenfunction(func.func):

                async def endpoint(req: Request):
                    obj = adapter.validate_json(await req.body())
                    async for x in func.func(obj):
                        print(f"MSG: {x}")

                    return responses.PlainTextResponse("200")

            elif inspect.isgeneratorfunction(func.func):

                async def endpoint(req: Request):
                    obj = adapter.validate_json(await req.body())
                    for x in func.func(obj):
                        print(f"MSG: {x}")

                    return responses.PlainTextResponse("200")

            else:

                async def endpoint(req: Request):
                    obj = adapter.validate_json(await req.body())
                    return responses.JSONResponse(func.gunc(obj))

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

        routes = self._js_create_api_endpoints() + self._js_create_html_part_routes(templates) + [Route('/parts/action_bar', endpoint=action_bar_template, methods=["GET"])]
        api = Starlette(routes=routes)
        
        
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