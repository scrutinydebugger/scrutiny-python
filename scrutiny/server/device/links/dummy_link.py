#    dummy_link.py
#        Fake communication link with a device. Used by the EmulatedDevice for unit test purpose
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import threading
from .abstract_link import AbstractLink, LinkConfig
from typing import Dict, Any


class ThreadSafeDummyLink(AbstractLink):
    """
    Thread safe fake communication channel that implement the 
    required interface to talk with a device. Used for unit teststing
    """
    to_device_data: bytes
    from_device_data: bytes
    from_device_mutex: threading.Lock
    to_device_mutex: threading.Lock
    _initialized: bool
    emulate_broken: bool

    INSTANCES: Dict[Any, "ThreadSafeDummyLink"] = {}

    @classmethod
    def make(cls, config: LinkConfig = {}) -> "ThreadSafeDummyLink":
        if 'channel_id' in config:
            if config['channel_id'] not in cls.INSTANCES:
                cls.INSTANCES[config['channel_id']] = cls(config)
            return cls.INSTANCES[config['channel_id']]

        return cls(config)

    def __init__(self, config: LinkConfig = {}):
        self._initialized = False
        self.clear_all()
        self.emulate_broken = False

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
        if self.emulate_broken:
            return None

        with self.to_device_mutex:
            self.to_device_data += data

    def read(self) -> bytes:
        if self.emulate_broken:
            return bytes()

        with self.from_device_mutex:
            data = self.from_device_data
            self.from_device_data = bytes()
        return data

    def emulate_device_read(self) -> bytes:
        if self.emulate_broken:
            return bytes()

        with self.to_device_mutex:
            data = self.to_device_data
            self.to_device_data = bytes()

        return data

    def emulate_device_write(self, data: bytes) -> None:
        if self.emulate_broken:
            return None

        with self.from_device_mutex:
            self.from_device_data += data

    def process(self) -> None:
        pass

    def operational(self) -> bool:
        return self._initialized and not self.emulate_broken

    def initialized(self) -> bool:
        return self._initialized

    def get_config(self):
        return {}

    @staticmethod
    def validate_config(config: LinkConfig) -> None:
        pass


class DummyLink(AbstractLink):
    """
    Non-thread safe fake communication channel that implement the 
    required interface to talk with a device. Used for unit teststing
    """
    to_device_data: bytes
    from_device_data: bytes
    _initialized: bool
    emulate_broken: bool

    INSTANCES: Dict[Any, "DummyLink"] = {}

    @classmethod
    def make(cls, config: LinkConfig = {}) -> "DummyLink":
        if 'channel_id' in config:
            if config['channel_id'] not in cls.INSTANCES:
                cls.INSTANCES[config['channel_id']] = cls(config)
            return cls.INSTANCES[config['channel_id']]

        return cls(config)

    def __init__(self, config: LinkConfig = None):
        self._initialized = False
        self.clear_all()
        self.emulate_broken = False

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
        if self.emulate_broken:
            return None
        self.to_device_data += data

    def read(self) -> bytes:
        if self.emulate_broken:
            return bytes()

        data = self.from_device_data
        self.from_device_data = bytes()
        return data

    def emulate_device_read(self) -> bytes:
        data = self.to_device_data
        self.to_device_data = bytes()
        if self.emulate_broken:
            data = bytes()

        return data

    def emulate_device_write(self, data: bytes) -> None:
        if not self.emulate_broken:
            self.from_device_data += data

    def process(self) -> None:
        pass

    def operational(self) -> bool:
        return self._initialized and not self.emulate_broken

    def initialized(self) -> bool:
        return self._initialized

    def get_config(self):
        return {}

    @staticmethod
    def validate_config(config: LinkConfig) -> None:
        pass
