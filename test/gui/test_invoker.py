#    test_invoker.py
#        A test suite to test the cross thread invocation helpers
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from dataclasses import dataclass
import threading
from test.gui.base_gui_test import ScrutinyBaseGuiTest
from typing import Optional
from scrutiny.gui.tools.invoker import InvokeInQtThreadSynchronized

class TestInvoker(ScrutinyBaseGuiTest):
    def test_run_in_qt_thread_synchronized(self):
        @dataclass
        class Container:
            thread_id:Optional[int] = None

        obj = Container()
        def func():
            obj.thread_id = threading.get_ident()

        finished = threading.Event()
        def thread_func():
            InvokeInQtThreadSynchronized(func)
            finished.set()

        thread = threading.Thread(target=thread_func, daemon=True)
        thread.start()
        self.wait_true_with_events(finished.is_set, 1)
        self.assertTrue(finished.is_set())
        self.assertEqual(obj.thread_id, threading.get_ident())
