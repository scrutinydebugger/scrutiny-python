#    gui.py
#        The highest level class to manipulate the GUI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from qtpy.QtWidgets import QApplication
from qtpy.QtGui import QIcon, QPalette
from scrutiny.gui.main_window import MainWindow
from scrutiny.gui import assets
import scrutiny
import ctypes
import platform
from typing import List

class ScrutinyQtGUI:
    debug_layout:bool

    def __init__(self, debug_layout:bool=False) -> None:
        self.debug_layout = debug_layout
    
    def run(self, args:List[str]) -> int:
        app = QApplication(args)
        app.setWindowIcon(QIcon(str(assets.logo_icon())))
        app.setApplicationDisplayName("Scrutiny Debugger")
        app.setApplicationVersion(scrutiny.__version__)

        if platform.system() == "Windows":
            # Tells windows that python process host another application. Enables the QT icon in the task bar
            # see https://stackoverflow.com/questions/1551605/how-to-set-applications-taskbar-icon-in-windows-7
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u'scrutiny.gui.%s' % scrutiny.__version__)

        window = MainWindow()
        if self.debug_layout:
            window.setStyleSheet("border:1px solid red")
        window.show()
        return app.exec()
