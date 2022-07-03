#    dummy_link.py
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import threading
from .abstract_link import AbstractLink, LinkConfig


class ThreadSafeDummyLink(AbstractLink):

    to_device_data: bytes
    from_device_data: bytes
    from_device_mutex: threading.Lock
    to_device_mutex: threading.Lock

    def __init__(self, config: LinkConfig = None):
        self.initialize()

    def initialize(self) -> None:
        self.to_device_data = bytes()
        self.from_device_data = bytes()
        self.from_device_mutex = threading.Lock()
        self.to_device_mutex = threading.Lock()

    def destroy(self) -> None:
        self.initialize()

    def write(self, data: bytes) -> None:
        with self.to_device_mutex:
            self.to_device_data += data

    def read(self) -> bytes:
        with self.from_device_mutex:
            data = self.from_device_data
            self.from_device_data = bytes()
        return data

    def emulate_device_read(self) -> bytes:
        with self.to_device_mutex:
            data = self.to_device_data
            self.to_device_data = bytes()
        return data

    def emulate_device_write(self, data: bytes) -> None:
        with self.from_device_mutex:
            self.from_device_data += data

    def process(self) -> None:
        pass

    def operational(self) -> bool:
        return True

    def get_config(self):
        return {}


class DummyLink(AbstractLink):
    to_device_data: bytes
    from_device_data: bytes

    def __init__(self, config: LinkConfig = None):
        self.initialize()

    def initialize(self) -> None:
        self.to_device_data = bytes()
        self.from_device_data = bytes()

    def destroy(self) -> None:
        self.to_device_data = bytes()
        self.from_device_data = bytes()

    def write(self, data: bytes) -> None:
        self.to_device_data += data

    def read(self) -> bytes:
        data = self.from_device_data
        self.from_device_data = bytes()
        return data

    def emulate_device_read(self) -> bytes:
        data = self.to_device_data
        self.to_device_data = bytes()
        return data

    def emulate_device_write(self, data: bytes) -> None:
        self.from_device_data += data

    def process(self) -> None:
        pass

    def operational(self) -> bool:
        return True

    def get_config(self):
        return {}
