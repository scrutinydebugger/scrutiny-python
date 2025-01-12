#    gui.py
#        The highest level class to manipulate the GUI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import sys
import ctypes

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

import scrutiny
from scrutiny.gui.main_window import MainWindow
from scrutiny.gui import assets
from scrutiny.tools.thread_enforcer import register_thread
from scrutiny.gui.core.threads import QT_THREAD_NAME
from scrutiny.gui.tools.invoker import CrossThreadInvoker
from scrutiny.gui.themes import set_theme
from scrutiny.gui.themes.default_theme import DefaultTheme 
from dataclasses import dataclass

from typing import List, Optional

class ScrutinyQtGUI:

    @dataclass(frozen=True)
    class Settings:
        debug_layout:bool
        auto_connect:bool
        opengl_enabled:bool

    _instance:Optional["ScrutinyQtGUI"] = None
    _settings:Settings

    @classmethod
    def instance(cls) -> "ScrutinyQtGUI":
        if cls._instance is None:
            raise RuntimeError(f"No instance of {cls.__name__} is running")
        return cls._instance
    
    @property
    def settings(self) -> Settings:
        return self._settings

    def __init__(self, 
                 debug_layout:bool=False,
                 auto_connect:bool=False,
                 opengl_enabled:bool=True
                 ) -> None:
        if self.__class__._instance is not None:
            raise RuntimeError(f"Only a single instance of {self.__class__.__name__} can run.")
        self.__class__._instance = self
        self._settings = self.Settings(
            debug_layout = debug_layout,
            auto_connect = auto_connect,
            opengl_enabled = opengl_enabled
        )

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

        if self.settings.opengl_enabled:
            #QTBUG-108190. PySide6.4 regression. Workaround to force OpenGL to initialize
            from PySide6.QtOpenGLWidgets import QOpenGLWidget
            _dummy_widget = QOpenGLWidget(window) 
            _dummy_widget.setVisible(False)
        
        if self.settings.debug_layout:
            window.setStyleSheet("border:1px solid red")

        CrossThreadInvoker.init()  # Internal tool to run functions in the QT Thread fromother thread
        window.show()
        
        return app.exec()
