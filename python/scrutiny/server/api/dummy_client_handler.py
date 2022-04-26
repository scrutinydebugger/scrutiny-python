#    dummy_client_handler.py
#        Stubbed API connector to make API requests in unittests without relying on websockets
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import websockets
import queue
import time
import asyncio
import threading
import uuid
import logging
import json
import uuid

from .abstract_client_handler import AbstractClientHandler, ClientHandlerConfig, ClientHandlerMessage


class DummyConnection:
    def __init__(self, conn_id=None):
        if conn_id is not None:
            self.conn_id = conn_id
        else:
            self.conn_id = uuid.uuid4().hex

        self.client_to_server_queue = queue.Queue()
        self.server_to_client_queue = queue.Queue()
        self.opened = False

    def open(self):
        self.opened = True

    def close(self):
        self.opened = False

    def is_open(self):
        return self.opened

    def write_to_client(self, msg):
        if self.opened:
            if not self.server_to_client_queue.full():
                self.server_to_client_queue.put(msg)

    def write_to_server(self, msg):
        if self.opened:
            if not self.client_to_server_queue.full():
                self.client_to_server_queue.put(msg)

    def read_from_server(self):
        if self.opened:
            if not self.server_to_client_queue.empty():
                return self.server_to_client_queue.get()

    def read_from_client(self):
        if self.opened:
            if not self.client_to_server_queue.empty():
                return self.client_to_server_queue.get()

    def from_server_available(self):
        return self.opened and not self.server_to_client_queue.empty()

    def from_client_available(self):
        return self.opened and not self.client_to_server_queue.empty()

    def get_id(self):
        return self.conn_id

    def __repr__(self):
        return '<%s - %s>' % (self.__class__.__name__, self.get_id())


class DummyClientHandler(AbstractClientHandler):
    def __init__(self, config):
        self.rxqueue = queue.Queue()
        self.txqueue = queue.Queue()
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.stop_requested = False

        self.validate_config(config)

        self.connections = config['connections']
        self.connection_map = {}
        for conn in self.connections:
            self.connection_map[conn.get_id()] = conn

        self.started = False

    def validate_config(self, config):
        if not isinstance(config, dict):
            raise ValueError('Config ust be a dict object')

        required_field = ['connections']
        for field in required_field:
            if field not in config:
                raise ValueError('%s : Missing config field : %s' % (self.__class__.__name__, field))

        for conn in config['connections']:
            if not isinstance(conn, DummyConnection):
                raise ValueError('Connections must be valid DummyConnection instances')

    def is_connection_active(self, conn_id):
        active = False
        if conn_id in self.connection_map:
            active = self.connection_map[conn_id].is_open()
        return active

    def run(self):
        while not self.stop_requested:
            try:
                for conn in self.connections:
                    while conn.from_client_available():
                        msg = conn.read_from_client()
                        if msg is not None:
                            try:
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
                            if conn_id in self.connection_map:
                                self.connection_map[conn_id].write_to_client(msg)
                        except Exception as e:
                            self.logger.error('Cannot send message.  %s' % str(e))

            except Exception as e:
                self.logger.error(str(e))
                self.stop_requested = True
                raise e
            time.sleep(0.01)

    def process(self):
        pass  # nothing to do

    def start(self):
        self.thread = threading.Thread(target=self.run)
        self.thread.start()
        self.started = True

    def stop(self):
        self.stop_requested = True
        self.thread.join()

    def send(self, conn_id, obj):
        if not self.txqueue.full():
            container = ClientHandlerMessage(conn_id=conn_id, obj=obj)
            self.txqueue.put(container)

    def available(self):
        return not self.rxqueue.empty()

    def recv(self):
        return self.rxqueue.get()
