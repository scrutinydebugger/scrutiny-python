#    dummy_link.py
#        Fake communication link with a device. Used by the EmulatedDevice for unit test purpose
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import threading
from .abstract_link import AbstractLink, LinkConfig


class ThreadSafeDummyLink(AbstractLink):

    to_device_data: bytes
    from_device_data: bytes
    from_device_mutex: threading.Lock
    to_device_mutex: threading.Lock
    _initialized:bool

    def __init__(self, config: LinkConfig = None):
        self._initialized = False
        self.clear_all()

    def clear_all(self) -> None:
        self.to_device_data = bytes()
        self.from_device_data = bytes()
        self.from_device_mutex = threading.Lock()
        self.to_device_mutex = threading.Lock()

    def initialize(self) -> None:
        self.clear_all()
        self._initialized = True

    def destroy(self) -> None:
        self.clear_all()
        self._initialized = False

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
        return self._initialized
    
    def initialized(self) -> bool:
        return self._initialized

    def get_config(self):
        return {}
    
    @staticmethod
    def validate_config(config:LinkConfig) -> None:
        pass


class DummyLink(AbstractLink):
    to_device_data: bytes
    from_device_data: bytes
    _initialized:bool

    def __init__(self, config: LinkConfig = None):
        self._initialized = False
        self.clear_all()

    def clear_all(self) -> None:
        self.to_device_data = bytes()
        self.from_device_data = bytes()

    def initialize(self) -> None:
        self.clear_all()
        self._initialized = True

    def destroy(self) -> None:
        self.clear_all()
        self._initialized = False

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
        return self._initialized

    def initialized(self) -> bool:
        return self._initialized

    def get_config(self):
        return {}
    
    @staticmethod
    def validate_config(config:LinkConfig) -> None:
        pass
