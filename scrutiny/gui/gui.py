#    gui.py
#        The highest level class to manipulate the GUI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from scrutiny.gui.main_window import MainWindow
from scrutiny.gui import assets
import scrutiny
import ctypes
import sys
from typing import List
from scrutiny.tools.thread_enforcer import register_thread
from scrutiny.gui import QT_THREAD_NAME
from scrutiny.gui.themes import set_theme
from scrutiny.gui.themes.default_theme import DefaultTheme


class ScrutinyQtGUI:
    debug_layout:bool
    auto_connect:bool

    def __init__(self, 
                 debug_layout:bool=False,
                 auto_connect:bool=False
                 ) -> None:
        self.debug_layout = debug_layout
        self.auto_connect = auto_connect
        set_theme(DefaultTheme())
    
    def run(self, args:List[str]) -> int:
        register_thread(QT_THREAD_NAME)
        app = QApplication(args)
        app.setWindowIcon(QIcon(str(assets.logo_icon())))
        app.setApplicationDisplayName("Scrutiny Debugger")
        app.setApplicationVersion(scrutiny.__version__)

        if sys.platform == "win32":
            # Tells windows that python process host another application. Enables the QT icon in the task bar
            # see https://stackoverflow.com/questions/1551605/how-to-set-applications-taskbar-icon-in-windows-7
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u'scrutiny.gui.%s' % scrutiny.__version__)

        window = MainWindow()

        stylesheet = assets.load_text(['stylesheets', 'scrutiny_base.qss'])
        app.setStyleSheet(stylesheet)

        if self.debug_layout:
            window.setStyleSheet("border:1px solid red")
        
        window.show()
        
        if self.auto_connect:
            window.start_server_manager()
        return app.exec()
