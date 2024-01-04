from pathlib import Path
from dotenv import load_dotenv
from starlette.staticfiles import StaticFiles

from actionator.core import Actionator

import os

server = Actionator()


@server.fn
def echo(msg: str) -> str:
    return msg


api = server.generate_js(Path("templates"))
api.mount("/static", StaticFiles(directory="static"), "static")

def main():
    import uvicorn

    uvicorn.run(
        "actionator:api",
        host="0.0.0.0",
        port=8888,
        reload=bool(os.environ.get("ACTIONATOR_DEV")),
    )