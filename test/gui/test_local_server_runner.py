#    test_local_server_runner.py
#        A test suite for the LocalServerRunner
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

import os,sys
import time

from test.gui.base_gui_test import ScrutinyBaseGuiTest, EventType
from scrutiny.tools.typing import *
from scrutiny import tools
from scrutiny.gui.core.local_server_runner import LocalServerRunner
from test import logger

class TestLocalServerRunner(ScrutinyBaseGuiTest):
    def setUp(self):
        super().setUp()
        self.runner = LocalServerRunner()
    
    def tearDown(self):
        self.runner.stop()
        super().tearDown()

    def test_run(self):
        state_list:List[LocalServerRunner.State] = []

        server_crashed = tools.MutableBool(False)
        def _abnormal_termination():
            logger.warning("Server crashed")
            server_crashed.set()

        def _log_stderr(line:str):
            logger.debug("->stderr: " + line)

        def _log_stdout(line:str):
            logger.debug("->stdout: " + line)

        def state_changed(state:LocalServerRunner.State):
            self.declare_event(EventType.LOCAL_SERVER_STATE_CHANGED)
            state_list.append(state)
        
        self.runner.signals.stderr.connect(_log_stderr)
        self.runner.signals.stdout.connect(_log_stdout)
        self.runner.signals.state_changed.connect(state_changed)
        self.runner.signals.abnormal_termination.connect(_abnormal_termination)
        
        self.runner.start(0)    # Picks any available port

        #self.wait_with_event(0.5)   # Leave some time for stderr/stdout to be received
        self.wait_events_and_clear([EventType.LOCAL_SERVER_STATE_CHANGED, EventType.LOCAL_SERVER_STATE_CHANGED], timeout=2)
        self.assertFalse(server_crashed.val)
        self.assertEqual(state_list, [LocalServerRunner.State.STARTING, LocalServerRunner.State.STARTED])
        state_list.clear()
        
        self.runner.stop()

        #self.wait_with_event(0.5)   # Leave some time for stderr/stdout to be received
        self.wait_events_and_clear([EventType.LOCAL_SERVER_STATE_CHANGED, EventType.LOCAL_SERVER_STATE_CHANGED], timeout=2)
        self.assertFalse(server_crashed.val)
        self.assertEqual(state_list, [LocalServerRunner.State.STOPPING, LocalServerRunner.State.STOPPED])
        state_list.clear()


   