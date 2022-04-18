#    dummy_link.py
#        Fake communication link with a device. Used by the EmulatedDevice for unit test purpose
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import threading


class ThreadSafeDummyLink:
    def __init__(self, config=None):
        self.initialize()

    def initialize(self):
        self.to_device_data = bytes()
        self.from_device_data = bytes()
        self.from_device_mutex = threading.Lock()
        self.to_device_mutex = threading.Lock()

    def destroy(self):
        self.initialize()

    def write(self, data):
        with self.to_device_mutex:
            self.to_device_data += data

    def read(self):
        with self.from_device_mutex:
            data = self.from_device_data
            self.from_device_data = bytes()
        return data

    def emulate_device_read(self):
        with self.to_device_mutex:
            data = self.to_device_data
            self.to_device_data = bytes()
        return data

    def emulate_device_write(self, data):
        with self.from_device_mutex:
            self.from_device_data += data

    def process(self):
        pass

    def operational(self):
        return True


class DummyLink:
    def __init__(self, config=None):
        self.initialize()

    def initialize(self):
        self.to_device_data = bytes()
        self.from_device_data = bytes()

    def destroy(self):
        self.to_device_data = bytes()
        self.from_device_data = bytes()

    def write(self, data):
        self.to_device_data += data

    def read(self):
        data = self.from_device_data
        self.from_device_data = bytes()
        return data

    def emulate_device_read(self):
        data = self.to_device_data
        self.to_device_data = bytes()
        return data

    def emulate_device_write(self, data):
        self.from_device_data += data

    def process(self):
        pass

    def operational(self):
        return True
