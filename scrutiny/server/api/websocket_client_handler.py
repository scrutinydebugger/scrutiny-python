#    websocket_client_handler.py
#        Manage the API websocket connections .
#        This class has a list of all clients and identify them by a unique ID
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import uuid
import logging
import json

from scrutiny.server.api.abstract_client_handler import AbstractClientHandler, ClientHandlerConfig, ClientHandlerMessage
from scrutiny.tools.synchronous_websocket_server import SynchronousWebsocketServer

from typing import Dict, Any, Optional
from scrutiny.core.typehints import GenericCallback

# WebsocketType = websockets.server.WebSocketServerProtocol
WebsocketType = Any  # todo fix this


class WebsocketClientHandler(AbstractClientHandler):
    """
    Manages connections to the API through websockets
    and implements the AbstractClientHandler, the connection handler for the API.

    """

    server: SynchronousWebsocketServer
    config: ClientHandlerConfig
    logger: logging.Logger
    id2ws_map: Dict[str, WebsocketType]
    ws2id_map: Dict[WebsocketType, str]
    port: Optional[int]
    force_silent: bool  # For unit testing of timeouts

    def __init__(self, config: ClientHandlerConfig):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.id2ws_map = dict()
        self.ws2id_map = dict()
        self.force_silent = False
        self.server = SynchronousWebsocketServer(connect_callback=GenericCallback(
            self.register), disconnect_callback=GenericCallback(self.unregister))

    def register(self, websocket: WebsocketType) -> None:
        # Callback on new websocket connection.  We make a unique ID for each object.
        wsid = self.make_id()
        self.id2ws_map[wsid] = websocket
        self.ws2id_map[websocket] = wsid
        self.logger.info('New client connected (ID=%s). %d clients total' % (wsid, len(self.ws2id_map)))

    def unregister(self, websocket: WebsocketType) -> None:
        # Callback on websocket disconnection.
        wsid = self.ws2id_map[websocket]
        del self.ws2id_map[websocket]
        del self.id2ws_map[wsid]
        self.logger.info('Client disconnected (ID=%s). %d clients remaining' % (wsid, len(self.ws2id_map)))

    def get_port(self) -> Optional[int]:
        return self.port

    def is_connection_active(self, conn_id: str) -> bool:
        return True if conn_id in self.id2ws_map else False

    def process(self) -> None:
        self.server.process(5)

    def start(self) -> None:
        self.logger.info('Starting websocket listener on %s:%s' % (self.config['host'], self.config['port']))
        self.port = self.server.start(self.config['host'], int(self.config['port']))

    def stop(self) -> None:
        self.logger.info('Stopping websocket listener')
        self.server.stop()

    def send(self, msg: ClientHandlerMessage) -> None:
        # Sends data given by the API to a given client identified by its unique connection ID
        wsid = msg.conn_id
        if wsid not in self.id2ws_map:
            self.logger.error('Conn ID %s not known. Discarding' % wsid)
            return
        websocket = self.id2ws_map[wsid]

        try:
            msg_string = json.dumps(msg.obj)
        except Exception as e:
            self.logger.error('Cannot send message. Invalid JSON. %s' % str(e))
            return

        if not self.server.txqueue.full():
            if not self.force_silent:
                self.server.txqueue.put((websocket, msg_string))
        else:
            self.logger.critical('Transmit queue full')

    def available(self) -> bool:
        return not self.server.rxqueue.empty()

    def recv(self) -> Optional[ClientHandlerMessage]:
        # Returns to the API messages received associated with the client connection unique ID
        try:
            (websocket, msg) = self.server.rxqueue.get_nowait()
        except Exception:
            return None

        if websocket not in self.ws2id_map:
            self.logger.critical('Received message from unregistered websocket')
            return None

        wsid = self.ws2id_map[websocket]
        msg = msg if isinstance(msg, str) else msg.decode('utf8')

        try:
            obj = json.loads(msg)
        except json.JSONDecodeError as e:
            self.logger.error('Received malformed JSON. %s' % str(e))
            if msg:
                self.logger.debug(msg)
            return None

        return ClientHandlerMessage(conn_id=wsid, obj=obj)

    def make_id(self) -> str:
        return uuid.uuid4().hex
