#    websocket_client_handler.py
#        Manage the API websocket connections .
#        This class has a list of all clients and identifiy them by a unique ID
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import websockets
import websockets.server
import queue
import time
import asyncio
import threading
import uuid
import logging
import json

from .abstract_client_handler import AbstractClientHandler, ClientHandlerConfig, ClientHandlerMessage
from typing import List, Dict, Tuple, Any, Coroutine, Optional, Callable

WebsocketType = websockets.server.WebSocketServerProtocol


class Timer:
    timeout: float
    args: Tuple[Any, ...]
    kwargs: Dict

    def __init__(self, timeout: float, callback: Callable[..., Coroutine], *args, **kwargs):
        self.timeout = timeout
        self.callback = callback
        self.args = args
        self.kwargs = kwargs
        self.start()

    async def job(self):
        await asyncio.sleep(self.timeout)  # wait
        try:
            await self.callback(*self.args, **self.kwargs)
            self.start()
        except Exception as e:
            raise e

    def start(self) -> None:
        self.task = asyncio.ensure_future(self.job())

    def cancel(self) -> None:
        self.task.cancel()


class WebsocketClientHandler(AbstractClientHandler):

    rxqueue: queue.Queue
    txqueue: queue.Queue
    config: ClientHandlerConfig
    loop: asyncio.AbstractEventLoop
    logger: logging.Logger
    id2ws_map: Dict[str, WebsocketType]
    ws2id_map: Dict[WebsocketType, str]
   # ws_server: Optional[websockets.server.Serve]
    started_event: threading.Event

    def __init__(self, config: ClientHandlerConfig):
        self.rxqueue = queue.Queue()
        self.txqueue = queue.Queue()
        self.config = config
        self.loop = asyncio.new_event_loop()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.id2ws_map = dict()
        self.ws2id_map = dict()
        self.ws_server = None
        self.started_event = threading.Event()  # This event synchronise the start of the server

    async def register(self, websocket: WebsocketType):
        wsid = self.make_id()
        self.id2ws_map[wsid] = websocket
        self.ws2id_map[websocket] = wsid
        self.logger.info('New client connected (ID=%s). %d clients total' % (wsid, len(self.ws2id_map)))
        return wsid

    async def unregister(self, websocket: WebsocketType):
        wsid = self.ws2id_map[websocket]
        del self.ws2id_map[websocket]
        del self.id2ws_map[wsid]
        self.logger.info('Client disconnected (ID=%s). %d clients remainings' % (wsid, len(self.ws2id_map)))

    def is_connection_active(self, conn_id: str) -> bool:
        return True if conn_id in self.id2ws_map else False

    # Executed for each websocket
    async def server_routine(self, websocket: WebsocketType, path: str):
        wsid = await self.register(websocket)
        tx_sync_timer = Timer(0.05, callback=self.process_tx_queue)

        try:
            async for message in websocket:
                try:
                    msg = message if isinstance(message, str) else message.decode('utf8')
                    #self.logger.debug('Received Conn:%s - %s' % (wsid, msg))
                    obj = json.loads(msg)
                    self.rxqueue.put(ClientHandlerMessage(conn_id=wsid, obj=obj))
                except Exception as e:
                    self.logger.error('Received malformed JSON. %s' % str(e))
                    self.logger.debug(msg)
        finally:
            tx_sync_timer.cancel()
            await self.unregister(websocket)

    async def process_tx_queue(self):
        while not self.txqueue.empty():
            popped = self.txqueue.get()

            wsid = popped.conn_id
            if wsid not in self.id2ws_map:
                self.debug('Conn ID %s not known. Discarding')
                continue
            websocket = self.id2ws_map[wsid]
            try:
                msg = json.dumps(popped.obj)
                #self.logger.debug('Send Conn:%s - %s' % (wsid, msg))
                await websocket.send(msg)
            except Exception as e:
                self.logger.error('Cannot send message. Invalid JSON. %s' % str(e))

    def process(self) -> None:
        pass  # nothing to do

    # Run in client_handler thread
    def run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.ws_server = websockets.serve(self.server_routine, self.config['host'], int(self.config['port']))

        self.logger.info('Starting websocket listener on %s:%s' % (self.config['host'], self.config['port']))
        self.loop.run_until_complete(self.ws_server)
        self.started_event.set()
        self.loop.run_forever()

    # Called from Main Thread
    def start(self) -> None:
        self.started_event.clear()
        self.thread = threading.Thread(target=self.run)
        self.thread.start()
        self.started_event.wait()   # Wait for the websocket server to start. Avoid race conditions

    # Called from Main Thread
    def stop(self) -> None:
        self.logger.info('Stopping websocket listener')
        self.loop.call_soon_threadsafe(self.stop_from_thread)
        if self.thread is not None:
            self.thread.join()

    # Called from client_handler Thread
    def stop_from_thread(self) -> None:
        asyncio.ensure_future(self.async_close())

    async def async_close(self):
        try:
            self.ws_server.ws_server.close()

            await self.ws_server.ws_server.wait_closed()
        except:
            pass
        self.loop.stop()

    def send(self, msg: ClientHandlerMessage):
        if not self.txqueue.full():
            self.txqueue.put(msg)
        else:
            self.logger.critical('Transmit queue full')

    def available(self) -> bool:
        return not self.rxqueue.empty()

    def recv(self) -> Optional[ClientHandlerMessage]:
        try:
            return self.rxqueue.get_nowait()
        except:
            pass
        return None

    def make_id(self) -> str:
        return uuid.uuid4().hex
