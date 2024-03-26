#    synchronous_websocket_server.py
#        Synchronous wrapper around the asynchronous websockets module
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import websockets
import websockets.server
import websockets.exceptions
import queue
import asyncio
import logging

from typing import Any, Optional, Tuple, Callable
from scrutiny.core.typehints import GenericCallback

WebsocketType = websockets.server.WebSocketServerProtocol


ConnectCallback = Callable[[WebsocketType], None]
DiconnectCallback = Callable[[WebsocketType], None]


class SynchronousWebsocketServer:
    """
    Websocket server that wraps the asynchronous "websockets" module into a class that 
    provides a synchronous interface.
    """
    rxqueue: "queue.Queue[Tuple[WebsocketType, Any]]"
    txqueue: "queue.Queue[Tuple[WebsocketType, Any]]"
    loop: asyncio.AbstractEventLoop
    logger: logging.Logger
    connect_callback: Optional[ConnectCallback]
    disconnect_callback: Optional[DiconnectCallback]
   # ws_server: Optional[websockets.server.Serve]

    def __init__(self, connect_callback: Optional[ConnectCallback] = None, disconnect_callback: Optional[DiconnectCallback] = None):
        self.rxqueue = queue.Queue()
        self.txqueue = queue.Queue()
        self.loop = asyncio.new_event_loop()
        self.ws_server = None
        self.connect_callback = connect_callback
        self.disconnect_callback = disconnect_callback
        self.logger = logging.getLogger(self.__class__.__name__)

    async def server_routine(self, websocket: WebsocketType, path: str) -> None:
        """ The routine given to the websockets module. Executed for each websocket"""
        if self.connect_callback is not None:
            self.connect_callback(websocket)

        try:
            async for message in websocket:
                if self.logger.isEnabledFor(logging.DEBUG):
                    if isinstance(message, str):
                        s = message
                    elif isinstance(message, bytes):
                        s = message.decode('utf8')
                    else:
                        s = message
                    self.logger.debug("Receiving %s" % s)
                self.rxqueue.put((websocket, message))   # Possible improvement : Handle queue full scenario.
        except (websockets.exceptions.ConnectionClosedOK, websockets.exceptions.ConnectionClosedError):
            pass
        finally:
            if self.disconnect_callback is not None:
                self.disconnect_callback(websocket)

    def process_tx_queue(self) -> None:
        """Empty the transmit queue and push the data into the websocket"""
        while not self.txqueue.empty():
            (websocket, message) = self.txqueue.get()
            try:
                if self.logger.isEnabledFor(logging.DEBUG):
                    if isinstance(message, str):
                        s = message
                    elif isinstance(message, bytes):
                        s = message.decode('utf8')
                    else:
                        s = message
                    self.logger.debug("Sending %s" % s)
                self.loop.run_until_complete(asyncio.ensure_future(websocket.send(message), loop=self.loop))
            except (websockets.exceptions.ConnectionClosedOK, websockets.exceptions.ConnectionClosedError):
                pass    # Client is disconnected. Disconnect callback not called yet.

    def process(self, nloop: int = 5) -> None:
        """To be called periodically"""
        self.process_tx_queue()
        for i in range(nloop):  # Executes the event loop several times to process events generated during processing
            self.loop.call_soon(self.loop.stop)
            self.loop.run_forever()

    def start(self, host: str, port: int) -> int:
        """Starts the websocket server and listen on the given host/port combination"""
        # Warning. websockets source code says that loop argument might be deprecated.
        self.ws_server = websockets.serve(self.server_routine, host, port, loop=self.loop)  # type: ignore
        assert self.ws_server is not None  # make mypy happy
        self.loop.run_until_complete(self.ws_server)    # Initialize websockets async server
        return self.ws_server.ws_server.server.sockets[0].getsockname()[1]

    def stop(self) -> None:
        """Stops the websocket server"""
        if self.ws_server is not None:
            self.ws_server.ws_server.close()
            self.loop.run_until_complete(asyncio.ensure_future(self.ws_server.ws_server.wait_closed(), loop=self.loop))
            self.loop.stop()
