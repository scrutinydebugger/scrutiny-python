#    gui.py
#        The highest level class to manipulate the GUI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = [
    'DEFAULT_SERVER_PORT',
    'SupportedTheme',
    'ScrutinyQtGUI',
]

import sys
import os
import ctypes
import logging
import enum

from PySide6.QtCore import QTimer, Qt

import scrutiny
from scrutiny.gui.main_window import MainWindow
from scrutiny.gui import assets
from scrutiny.gui.core.qt import make_qt_app
from scrutiny.gui.tools.invoker import CrossThreadInvoker
from scrutiny.gui.tools.opengl import prepare_for_opengl
from scrutiny.gui.themes import scrutiny_set_theme, scrutiny_get_theme
from dataclasses import dataclass

from scrutiny.tools.typing import *
from scrutiny.tools.signals import SignalExitHandler

from scrutiny.gui import DEFAULT_SERVER_PORT


class SupportedTheme(enum.Enum):
    Default = enum.auto()
    Fusion = enum.auto()


class ScrutinyQtGUI:
    @dataclass(frozen=True)
    class Settings:
        debug_layout: bool = False
        auto_connect: bool = False
        opengl_enabled: bool = False
        start_local_server: bool = False
        local_server_port: int = DEFAULT_SERVER_PORT
        theme: SupportedTheme = SupportedTheme.Default

    _instance: Optional["ScrutinyQtGUI"] = None
    _settings: Settings
    _exit_handler: Optional[SignalExitHandler]

    @classmethod
    def instance(cls) -> "ScrutinyQtGUI":
        if cls._instance is None:
            raise RuntimeError(f"No instance of {cls.__name__} is running")
        return cls._instance

    @property
    def settings(self) -> Settings:
        return self._settings

    def __init__(self,
                 debug_layout: bool = False,
                 auto_connect: bool = False,
                 opengl_enabled: bool = True,
                 start_local_server: bool = False,
                 local_server_port: int = DEFAULT_SERVER_PORT,
                 theme: SupportedTheme = SupportedTheme.Fusion
                 ) -> None:
        if self.__class__._instance is not None:
            raise RuntimeError(f"Only a single instance of {self.__class__.__name__} can run.")

        self.__class__._instance = self
        self._exit_handler = None

        self._settings = self.Settings(
            debug_layout=debug_layout,
            auto_connect=auto_connect,
            opengl_enabled=opengl_enabled,
            local_server_port=local_server_port,
            start_local_server=start_local_server,
            theme=theme
        )

    def run(self, args: List[str]) -> int:
        logger = logging.getLogger(self.__class__.__name__)

        if sys.platform == "win32":
            # Tells windows that python process host another application. Enables the QT icon in the task bar
            # see https://stackoverflow.com/questions/1551605/how-to-set-applications-taskbar-icon-in-windows-7
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u'scrutiny.gui.%s' % scrutiny.__version__)

        elif sys.platform == 'linux':
            # QtADS doesn't work well with Wayland. Works with X11.
            # https://github.com/githubuser0xFFFF/Qt-Advanced-Docking-System/issues/714
            is_wsl = 'microsoft' in os.uname().version.lower()

            if 'QT_QPA_PLATFORM' not in os.environ:
                logger.warning(
                    "Forcing usage of X11 windowing system because Wayland has known issues. Make sure to have libxcb and its component installed. Specify env QT_QPA_PLATFORM to change this behavior.")
                os.environ['QT_QPA_PLATFORM'] = 'xcb'
            else:
                platform = os.environ['QT_QPA_PLATFORM'].lower().strip()
                if platform == 'wayland':
                    logger.warning(
                        "There are known issues with Wayland windowing system and this software dependencies (QT & QT-ADS). Specifying QT_QPA_PLATFORM=xcb may solve display bugs.")

            if os.environ['QT_QPA_PLATFORM'] == 'xcb' and is_wsl:
                if 'DISPLAY' not in os.environ:
                    logger.warning(
                        "Using X11 on WSL. An improper X11 configuration may prevent this app from starting. Make sure you can run a basic application (e.g. xeyes).")

        app = make_qt_app(args)
        app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)  # Mac OS doesn't display the icon by default.

        if self._settings.theme == SupportedTheme.Default:
            from scrutiny.gui.themes.default_theme import DefaultTheme
            scrutiny_set_theme(app, DefaultTheme())
        elif self._settings.theme == SupportedTheme.Fusion:
            from scrutiny.gui.themes.fusion_theme import FusionTheme
            scrutiny_set_theme(app, FusionTheme())
        else:
            raise NotImplementedError("Unsupported theme")

        def exit_signal_callback() -> None:
            app.quit()

        self._exit_handler = SignalExitHandler(exit_signal_callback)

        app.setWindowIcon(scrutiny_get_theme().load_medium_icon(assets.Icons.ScrutinyLogo))
        app.setApplicationDisplayName("Scrutiny Debugger")
        app.setApplicationVersion(scrutiny.__version__)

        window = MainWindow()

        # Signals are processed only when an event is being checked for.
        # This timer create an opportunity for signal handling every 500 msec
        check_signal_timer = QTimer()
        check_signal_timer.setInterval(500)
        check_signal_timer.start()
        check_signal_timer.timeout.connect(lambda: None)

        if self.settings.opengl_enabled:
            prepare_for_opengl(window)

        if self.settings.debug_layout:
            window.setStyleSheet("border:1px solid red")

        window.show()

        return app.exec()
