from pathlib import Path
from dotenv import load_dotenv
from starlette.staticfiles import StaticFiles

from .lib import Actionator
 
import os

load_dotenv(Path(__file__).parent.parent / ".env")
server = Actionator()


@server.fn
def echo(msg: str) -> str:
   return msg


api = server.generate_js(Path("static/gen"))

api.mount("/static", StaticFiles(directory="static"), "static")

def main():
    import uvicorn
    uvicorn.run("actionator:api", host="0.0.0.0", port=8888, reload=bool(os.environ.get("ACTIONATOR_DEV")))

if __name__ == "__main__":
    main()