from pathlib import Path
from dotenv import load_dotenv
from starlette.staticfiles import StaticFiles
from asyncio import sleep

from actionator.core import Actionator
from io import TextIOBase

import os

server = Actionator()


@server.fn(gen_output_io=True)
async def echo(msg: str, output_io: TextIOBase):
    while True:
        print(msg, file=output_io)
        await sleep(2)


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
    
if __name__ == "__main__":
    main()