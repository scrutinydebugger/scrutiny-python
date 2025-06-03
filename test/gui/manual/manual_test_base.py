#    manual_test_base.py
#        Common setup for all manual test files that launches a standalone apps for testing
#        GUI elements
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

import sys
import os
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

project_root = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

from scrutiny.gui.core.threads import QT_THREAD_NAME
from scrutiny.tools.thread_enforcer import register_thread
from scrutiny.gui.themes import scrutiny_set_theme
from scrutiny.gui.themes.default_theme import DefaultTheme
from scrutiny.gui.themes.fusion_theme import FusionTheme
from scrutiny.gui.tools.invoker import CrossThreadInvoker

from scrutiny.tools.signals import SignalExitHandler


def make_manual_test_app() -> QApplication:
    os.environ['SCRUTINY_MANUAL_TEST'] = '1'
    logging.basicConfig(level=logging.DEBUG)
    register_thread(QT_THREAD_NAME)
    app = QApplication([])
    CrossThreadInvoker.init()

    theme_str = os.environ.get('SCRUTINY_THEME', 'default')
    if theme_str == 'default':
        scrutiny_set_theme(app, DefaultTheme())
    elif theme_str == 'fusion':
        scrutiny_set_theme(app, FusionTheme())

    app._scrutiny_check_signal_timer = QTimer()
    app._scrutiny_check_signal_timer.setInterval(500)
    app._scrutiny_check_signal_timer.start()
    app._scrutiny_check_signal_timer.timeout.connect(lambda *a: None)

    app._scrutiny_exit_handler = SignalExitHandler(app.quit)

    return app
