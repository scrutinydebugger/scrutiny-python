

import sys, os
import logging
from PySide6.QtWidgets import QApplication

project_root = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

from scrutiny.gui.core.threads import QT_THREAD_NAME
from scrutiny.tools.thread_enforcer import register_thread
from scrutiny.gui.themes import set_theme
from scrutiny.gui.themes.default_theme import DefaultTheme 
from scrutiny.gui import assets

def make_manual_test_app() -> QApplication:
    os.environ['SCRUTINY_MANUAL_TEST'] = '1'
    logging.basicConfig(level=logging.DEBUG)
    register_thread(QT_THREAD_NAME)
    app = QApplication([])
    app.setStyleSheet(assets.load_text(["stylesheets", "scrutiny_base.qss"]))
    set_theme(DefaultTheme())

    return app
