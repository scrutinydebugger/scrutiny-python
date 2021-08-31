import asyncio
import websockets
import json
import time

obj = {'prop1' : 'val1'}

async def hello():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        await websocket.send(json.dumps(obj))
        print(await websocket.recv())
        time.sleep(5)
        await websocket.send(json.dumps(obj))
        print(await websocket.recv())

asyncio.get_event_loop().run_until_complete(hello())