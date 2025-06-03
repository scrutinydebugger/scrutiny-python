#    menu_bar.py
#        The window top menubar
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = ['MenuBar']

import os
import functools

from PySide6.QtWidgets import QMenuBar, QMenu
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtCore import QObject, Signal

from pathlib import Path
from scrutiny.tools.typing import *


class MenuBar(QMenuBar):
    class _Signals(QObject):
        dashboard_open_click = Signal()
        dashboard_save_click = Signal()
        dashboard_save_as_click = Signal()
        dashboard_clear_click = Signal()
        dashboard_recent_open = Signal(str)

        device_configure_click = Signal()
        info_about_click = Signal()

    _signals: _Signals
    _action_dashboard_open: QAction
    _action_dashboard_save: QAction
    _action_dashboard_save_as: QAction
    _action_dashboard_clear: QAction
    _action_server_launch_local: QAction
    _action_device_configure: QAction
    _action_info_about: QAction
    _recent_action: QAction

    def __init__(self, ) -> None:
        super().__init__()
        self._signals = self._Signals()
        dashboard_menu = self.addMenu('Dashboard')
        self._action_dashboard_open = dashboard_menu.addAction("Open", QKeySequence.StandardKey.Open)
        self._action_dashboard_open.triggered.connect(self._signals.dashboard_open_click)

        self._action_dashboard_save = dashboard_menu.addAction("Save", QKeySequence.StandardKey.Save)
        self._action_dashboard_save.triggered.connect(self._signals.dashboard_save_click)

        self._action_dashboard_save_as = dashboard_menu.addAction("Save as", QKeySequence.StandardKey.SaveAs)
        self._action_dashboard_save_as.triggered.connect(self._signals.dashboard_save_as_click)

        self._action_dashboard_clear = dashboard_menu.addAction("Clear")
        self._action_dashboard_clear.triggered.connect(self._signals.dashboard_clear_click)

        dashboard_menu.addSeparator()
        self._recent_action = dashboard_menu.addAction("Recent")

        info_menu = self.addMenu("Info")
        self._action_info_about = info_menu.addAction("About this software")
        self._action_info_about.triggered.connect(self._signals.info_about_click)

    @property
    def signals(self) -> _Signals:
        return self._signals

    def set_dashboard_recents(self, history: List[Path]) -> None:
        """Add the list of recent loaded dashboard to Dashboard-->Recent"""
        menu = QMenu()
        count = 0

        def emit_recent_clicked(file: str) -> None:
            self._signals.dashboard_recent_open.emit(file)

        for path in history:
            if os.path.isfile(path):
                action = menu.addAction(str(path))
                action.triggered.connect(functools.partial(emit_recent_clicked, str(path)))
                count += 1

        self._recent_action.setMenu(menu)
        self._recent_action.setEnabled(count > 0)
