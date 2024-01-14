#    dummy_client_handler.py
#        Stubbed API connector to make API requests in unit tests without relying on websockets
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = [
    'DummyConnection',
    'DummyClientHandler'
]

import queue
import time
import threading
import uuid
import logging
import json
import uuid

from .abstract_client_handler import AbstractClientHandler, ClientHandlerConfig, ClientHandlerMessage
from typing import Optional, Dict, List


class DummyConnection:

    conn_id: str
    client_to_server_queue: "queue.Queue[str]"
    server_to_client_queue: "queue.Queue[str]"
    opened: bool

    def __init__(self, conn_id: Optional[str] = None) -> None:
        if conn_id is not None:
            self.conn_id = conn_id
        else:
            self.conn_id = uuid.uuid4().hex

        self.client_to_server_queue = queue.Queue()
        self.server_to_client_queue = queue.Queue()
        self.opened = False

    def open(self) -> None:
        self.opened = True

    def close(self) -> None:
        self.opened = False

    def is_open(self) -> bool:
        return self.opened

    def write_to_client(self, msg: str) -> None:
        if self.opened:
            self.server_to_client_queue.put(msg, block=False)

    def write_to_server(self, msg: str) -> None:
        if self.opened:
            self.client_to_server_queue.put(msg, block=False)

    def read_from_server(self) -> Optional[str]:
        if self.opened:
            if not self.server_to_client_queue.empty():
                return self.server_to_client_queue.get()
        return None

    def read_from_client(self) -> Optional[str]:
        if self.opened:
            if not self.client_to_server_queue.empty():
                return self.client_to_server_queue.get()
        return None

    def from_server_available(self) -> bool:
        return self.opened and not self.server_to_client_queue.empty()

    def from_client_available(self) -> bool:
        return self.opened and not self.client_to_server_queue.empty()

    def get_id(self) -> str:
        return self.conn_id

    def __repr__(self) -> str:
        return '<%s - %s>' % (self.__class__.__name__, self.get_id())


class DummyClientHandler(AbstractClientHandler):

    rxqueue: "queue.Queue[ClientHandlerMessage]"
    txqueue: "queue.Queue[ClientHandlerMessage]"
    config: Dict[str, str]
    logger: logging.Logger
    stop_requested: bool
    connections: List[DummyConnection]
    connection_map: Dict[str, DummyConnection]
    started: bool

    def __init__(self, config: ClientHandlerConfig) -> None:
        self.rxqueue = queue.Queue()
        self.txqueue = queue.Queue()
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.stop_requested = False
        self.validate_config(config)
        self.connection_map = {}
        self.connections = []
        self.started = False

    def set_connections(self, connections: List[DummyConnection]) -> None:
        self.connections = connections
        for conn in self.connections:
            self.connection_map[conn.get_id()] = conn

    def validate_config(self, config: ClientHandlerConfig) -> None:
        if not isinstance(config, dict):
            raise ValueError('Config must be a dict object')

        required_field: List[str] = []
        for field in required_field:
            if field not in config:
                raise ValueError('%s : Missing config field : %s' % (self.__class__.__name__, field))

    def is_connection_active(self, conn_id: str) -> bool:
        active = False
        if conn_id in self.connection_map:
            active = self.connection_map[conn_id].is_open()
        return active

    def run(self) -> None:
        while not self.stop_requested:
            try:
                for conn in self.connections:
                    while conn.from_client_available():
                        msg = conn.read_from_client()
                        if msg is not None:
                            try:
                                self.logger.debug('Received from ID %s. "%s"' % (conn.get_id(), msg))
                                obj = json.loads(msg)
                                self.rxqueue.put(ClientHandlerMessage(conn_id=conn.get_id(), obj=obj))
                            except Exception as e:
                                self.logger.error('Received invalid msg.  %s' % str(e))

                while not self.txqueue.empty():
                    container = self.txqueue.get()
                    if container is not None:
                        try:
                            msg = json.dumps(container.obj)
                            conn_id = container.conn_id
                            self.logger.debug('Writing to ID %s. "%s"' % (conn_id, msg))
                            if conn_id in self.connection_map:
                                self.connection_map[conn_id].write_to_client(msg)
                        except Exception as e:
                            self.logger.error('Cannot send message.  %s' % str(e))

            except Exception as e:
                self.logger.error(str(e))
                self.stop_requested = True
                raise e
            time.sleep(0.01)

    def process(self) -> None:
        pass  # nothing to do

    def start(self) -> None:
        self.thread = threading.Thread(target=self.run)
        self.thread.start()
        self.started = True

    def stop(self) -> None:
        self.stop_requested = True
        self.thread.join()

    def send(self, msg: ClientHandlerMessage) -> None:
        if not self.txqueue.full():
            self.txqueue.put(msg)

    def available(self) -> bool:
        return not self.rxqueue.empty()

    def recv(self) -> Optional[ClientHandlerMessage]:
        return self.rxqueue.get()
