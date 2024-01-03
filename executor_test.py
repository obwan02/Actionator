import asyncio

async def test():
    await asyncio.sleep(1)
    print("Here")

def dispatch(yes):
    if yes:
        asyncio.get_event_loop().create_task(test())
    else:
        asyncio.get_event_loop().run_until_complete(test())


async def main():
    dispatch(True)
    print("Now here")
    await asyncio.sleep(2)

asyncio.run(main())
