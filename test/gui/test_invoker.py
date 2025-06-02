#    test_invoker.py
#        A test suite to test the cross thread invocation helpers
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2021 Scrutiny Debugger

import threading
from test.gui.base_gui_test import ScrutinyBaseGuiTest
from scrutiny.gui.tools.invoker import invoke_in_qt_thread_synchronized, CrossThreadInvoker
from scrutiny import tools

class TestInvoker(ScrutinyBaseGuiTest):
    def test_run_in_qt_thread_synchronized(self):
        CrossThreadInvoker.init()
        thread_id = tools.MutableNullableInt(None)
        def func():
            thread_id.val = threading.get_ident()

        finished = threading.Event()
        def thread_func():
            invoke_in_qt_thread_synchronized(func)
            finished.set()

        thread = threading.Thread(target=thread_func, daemon=True)
        thread.start()
        self.wait_true_with_events(finished.is_set, 1)
        self.assertTrue(finished.is_set())
        self.assertEqual(thread_id.val, threading.get_ident())
