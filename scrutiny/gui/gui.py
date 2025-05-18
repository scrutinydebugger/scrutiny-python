#    gui.py
#        The highest level class to manipulate the GUI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import sys
import os
import ctypes
import logging

from PySide6.QtWidgets import QApplication, QStyleFactory
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPalette, QColor

import scrutiny
from scrutiny.gui.main_window import MainWindow
from scrutiny.gui import assets
from scrutiny.tools.thread_enforcer import register_thread
from scrutiny.gui.core.threads import QT_THREAD_NAME
from scrutiny.gui.tools.invoker import CrossThreadInvoker
from scrutiny.gui.tools.opengl import prepare_for_opengl
from scrutiny.gui.themes import scrutiny_set_theme
from scrutiny.gui.themes.default_theme import DefaultTheme 
from dataclasses import dataclass

from scrutiny.tools.typing import *
from scrutiny.tools.signals import SignalExitHandler

from scrutiny.gui import DEFAULT_SERVER_PORT

class ScrutinyQtGUI:
    @dataclass
    class LocalServerSettings:
        autostart:bool
        port:int
    
    @dataclass
    class RemoteServerSettings:
        hostname:str
        port:int

    @dataclass(frozen=True)
    class Settings:
        debug_layout:bool
        auto_connect:bool
        opengl_enabled:bool
        start_local_server:bool
        local_server_port:int

    _instance:Optional["ScrutinyQtGUI"] = None
    _settings:Settings
    _exit_handler:Optional[SignalExitHandler]

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
                 opengl_enabled:bool=True,
                 start_local_server:bool = False,
                 local_server_port:int = DEFAULT_SERVER_PORT
                 ) -> None:
        if self.__class__._instance is not None:
            raise RuntimeError(f"Only a single instance of {self.__class__.__name__} can run.")
        
        self.__class__._instance = self
        self._exit_handler = None
        
        self._settings = self.Settings(
            debug_layout = debug_layout,
            auto_connect = auto_connect,
            opengl_enabled = opengl_enabled,
            local_server_port = local_server_port,
            start_local_server = start_local_server
        )

    
    def run(self, args:List[str]) -> int:
        register_thread(QT_THREAD_NAME)
        logger = logging.getLogger(self.__class__.__name__)

        if sys.platform == "win32":
            # Tells windows that python process host another application. Enables the QT icon in the task bar
            # see https://stackoverflow.com/questions/1551605/how-to-set-applications-taskbar-icon-in-windows-7
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u'scrutiny.gui.%s' % scrutiny.__version__)
            
        elif sys.platform == 'linux':
                # QtADS doesn't work well with Wayland. Works with X11.
                # https://github.com/githubuser0xFFFF/Qt-Advanced-Docking-System/issues/714
            if 'QT_QPA_PLATFORM' not in os.environ:
                logger.warning("Forcing usage of X11 windowing system because Wayland has known issues. Make sure to have libxcb and its component installed. Specify env QT_QPA_PLATFORM to change this behavior.")
                os.environ['QT_QPA_PLATFORM'] = 'xcb'
            else:
                platform = os.environ['QT_QPA_PLATFORM'].lower().strip()
                if platform == 'wayland':
                    logger.warning("There are known issues with Wayland windowing system and this software dependecies (QT & QT-ADS). Specifying QT_QPA_PLATFORM=xcb may solve display bugs.")

        app = QApplication(args)
        scrutiny_set_theme(DefaultTheme())
        def exit_signal_callback() -> None:
            app.quit()
        
        self._exit_handler = SignalExitHandler(exit_signal_callback)

        app.setWindowIcon(assets.load_medium_icon(assets.Icons.ScrutinyLogo))
        app.setApplicationDisplayName("Scrutiny Debugger")
        app.setApplicationVersion(scrutiny.__version__)

        window = MainWindow()
        
        # Signals are processed only when an event is being checked for. 
        # This timer create an opporunity for signal handling every 500 msec
        check_signal_timer = QTimer()
        check_signal_timer.setInterval(500)
        check_signal_timer.start()
        check_signal_timer.timeout.connect(lambda : None)

        if self.settings.opengl_enabled:
            prepare_for_opengl(window)
           
        if self.settings.debug_layout:
            window.setStyleSheet("border:1px solid red")

        CrossThreadInvoker.init()  # Internal tool to run functions in the QT Thread from other thread
        window.show()
        
        return app.exec()
