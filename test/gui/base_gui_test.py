#    base_gui_test.py
#        Base class for GUI tests
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from test import ScrutinyUnitTest
from PySide6.QtWidgets import QApplication
import PySide6.QtGui
import enum
import time
from test import logger

from typing import List


class EventType(enum.Enum):
    SERVER_CONNECTED = enum.auto()
    SERVER_DISCONNECTED = enum.auto()
    DEVICE_READY = enum.auto()
    DEVICE_DISCONNECTED = enum.auto()
    DATALOGGING_STATE_CHANGED = enum.auto()
    WATCHABLE_INDEX_CHANGED = enum.auto()
    SFD_LOADED = enum.auto()
    SFD_UNLOADED = enum.auto()

class ScrutinyBaseGuiTest(ScrutinyUnitTest):

    def declare_event(self, event_type:EventType):
       logger.debug(f"Event: {event_type.name}")
       self.event_list.append(event_type)

    def setUp(self) -> None:
        self.event_list:List[EventType] = []
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication([]) # Required to process event because they are emitted in a different thread, therefore the connectiontype is queued
    
    def tearDown(self):
        self.process_events()
       # self.app.deleteLater()  # Segfault without this. don't know why
        

    def wait_equal(self, fn, val, timeout, no_assert=False):
        t = time.perf_counter()

        while time.perf_counter() - t < timeout:
            if fn() == val:
                break
            time.sleep(0.01)
        if not no_assert:
            self.assertEqual(fn(), val)

    def wait_equal_with_events(self, fn, val, timeout, no_assert=False):
        t = time.perf_counter()

        while time.perf_counter() - t < timeout:
            self.process_events()
            if fn() == val:
                break
            time.sleep(0.01)
        if not no_assert:
            self.assertEqual(fn(), val)
    
    def wait_true(self, fn, timeout, no_assert=False):
        return self.wait_equal(fn, True, timeout, no_assert)

    def wait_false(self, fn, timeout, no_assert=False):
        return self.wait_equal(fn, False, timeout, no_assert)
    
    def wait_true_with_events(self, fn, timeout, no_assert=False):
        return self.wait_equal_with_events(fn, True, timeout, no_assert)

    def wait_false_with_events(self, fn, timeout, no_assert=False):
        return self.wait_equal_with_events(fn, False, timeout, no_assert)
    
    def wait_events(self, events:List[EventType], timeout:float,msg=""):
        t = time.perf_counter()

        while time.perf_counter() - t < timeout:
            self.process_events()
            if len(self.event_list) == len(events):
                break
            time.sleep(0.01)

        self.assert_events(events, f"Condition did not happen after {timeout} sec." + msg)
    
    def wait_events_and_clear(self, events:List[EventType], timeout:float, msg=""):
        self.wait_events(events, timeout, msg)
        self.clear_events()
    
    def clear_events(self):
        self.event_list = []

    def assert_events(self, events:List[EventType], msg="") -> None:
        self.process_events()
        self.assertEqual(self.event_list, events, msg=msg)
    
    def process_events(self):
        self.app.processEvents()
    
    def assert_events_and_clear(self, events:List[EventType])->None:
        self.assert_events(events)
        self.clear_events()
