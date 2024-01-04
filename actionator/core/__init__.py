from starlette.applications import Starlette
from starlette.requests import Request
from starlette.background import BackgroundTask
from starlette.routing import Route
from starlette import responses
from bs4 import BeautifulSoup, Tag
from pathlib import Path
import copy
import typing
import pydantic
import inspect


DEFAULT_ACTION_CONTAINER = BeautifulSoup("""
<ul class="list pl0 mv1">
</ul>
""").ul.extract()

DEFAULT_ACTION_TEMPLATE = BeautifulSoup("""
<li class="pa2 ba b--dark-red br2 mv1 mh1 bg-dark-gray dim near-white">
</li>
""").li.extract()

class Actionator:
    def __init__(self, api_prefix="/api/v1"):
        self.registered_funcs = []
        self.api_prefix = api_prefix

    def fn(self, func):
        """
        A decorator to register a function. This does a couple of things.
        Firstly, it makes the function accessible through RPC when API is generated.
        Secondly, when a frontend is generated (if a frontend is generated), it will create
        an item 
        """
        self.registered_funcs.append(func)
        return func

    def generate_js(self, 
                    gen_dir: Path,
                    action_container_html: Tag = DEFAULT_ACTION_CONTAINER, 
                    action_template_html: Tag = DEFAULT_ACTION_TEMPLATE) -> Starlette:
        
        routes = []
        
        for func in self.registered_funcs:
            arg_types = typing.get_type_hints(func)

            if ('return' in arg_types and len(arg_types) != 2) or ('return' not in arg_types and len(arg_types) != 1):
                raise TypeError(f"Function {func.__module__}.{func.__name__} doesn't have exactly 1 parameters (typing hints: {arg_types}")

            
            arg_type = next(typ for key, typ in arg_types.items() if key != "return")
            adapter = pydantic.TypeAdapter(arg_type)
            
            if inspect.iscoroutinefunction(func):
                async def endpoint(req: Request):
                    obj = adapter.validate_json(await req.body())
                    return responses.JSONResponse(await func(obj))

            elif inspect.isasyncgenfunction(func):
                async def endpoint(req: Request):
                    obj = adapter.validate_json(await req.body())
                    async for x in func(obj):
                        print(f"MSG: {x}")
                        
                    return responses.PlainTextResponse("200")

            elif inspect.isgeneratorfunction(func):
                async def endpoint(req: Request):
                    obj = adapter.validate_json(await req.body())
                    for x in func(obj):
                        print(f"MSG: {x}")
                        
                    return responses.PlainTextResponse("200")
            else:
                async def endpoint(req: Request):
                    obj = adapter.validate_json(await req.body())
                    return responses.JSONResponse(func(obj))
                

            # TODO: Add function name as an overridable
            # parameter when registering function
            routes.append(Route(self.get_route_name(func), endpoint=endpoint, methods=['POST']))

        api = Starlette(routes=routes)
        
        with open(gen_dir / 'action_bar.html', 'w') as f:
            js = generate_js(self.registered_funcs, [self.get_route_name(func) for func in self.registered_funcs])

            html_tree = BeautifulSoup()
            gen_tag = generate_actionbar_html(self.registered_funcs, action_container_html, action_template_html)
            html_tree.append(gen_tag)

            script = html_tree.new_tag("script")
            script.string = js
            html_tree.append(script)

            f.write(str(html_tree))

        for func in self.registered_funcs:
            with open(gen_dir / f"{func.__name__}.html", 'w') as f:
                html_tree = BeautifulSoup()
                html_tree.append(generate_inputform_html_for_func(func, self.get_route_name(func)))
                f.write(str(html_tree))

        return api

    def get_route_name(self, func):
        return f'{self.api_prefix}/{func.__name__}'
        
    def generate_native():
        raise NotImplementedError("Native app support hasn't been implemented yet")
       
    
ACTION_BUT_ID_SUFFIX = "-action-but"
ACTION_OUTPUT_ID_SUFFIX = "-action-out"
    
def generate_actionbar_html(funcs,
                  action_but_container: Tag,
                  action_but_template: Tag) -> Tag:
    
    action_but_container = copy.deepcopy(action_but_container)

    for func in funcs:
        arg_types = typing.get_type_hints(func)

        if ('return' in arg_types and len(arg_types) != 2) or  ('return' not in arg_types and len(arg_types) != 1):
            raise TypeError(f"Function {func.__module__}.{func.__name__} doesn't have exactly 1 parameters (typing hints: {arg_types}")
        
        but_inst = copy.deepcopy(action_but_template)
        but_inst.string = str(func.__name__).replace("_", " ").title()
        but_inst["id"] = f"{func.__name__}{ACTION_BUT_ID_SUFFIX}"
        action_but_container.append(but_inst)
        
    return action_but_container

def generate_inputform_html_for_func(func: typing.Callable, post_url: str) -> Tag:
    container = Tag(name="form")
    container["action"] = post_url
    container["method"] = "post"
    
    hints = typing.get_type_hints(func)

    if 'return' in hints:
        del hints['return']
        
    for name, typ in hints.items():
        if issubclass(typ, int):
            text_input = Tag(name="input")
            text_input["class"] = "input-reset"
            text_input["name"] = name
            text_input["placeholder"] = name
            text_input["type"] = "int"
            container.append(text_input)
        
        if issubclass(typ, str):
            text_input = Tag(name="input")
            text_input["class"] = "input-reset"
            text_input["name"] = name
            text_input["placeholder"] = name
            container.append(text_input)

    submit = Tag(name="input")
    submit["type"] = "submit"
    return container

    

# JS isn't as nice to manipulate (unlike HTML), so we don't bother
# parsing it, and we are just very careful with templates :)
def generate_actionbar_js(funcs) -> str:
    output = []
    for func in funcs:
        template = f"""
document.getElementById("{func.__name__}{ACTION_BUT_ID_SUFFIX}").onclick = async _ => {{
    let output = await fetch("/static/gen/{func.__name__}");
    document.getElementById("{func.__name__}{ACTION_OUTPUT_ID_SUFFIX}").innerHTML = output;
}};
"""
        output.append(template)

    return "\n".join(output)
        