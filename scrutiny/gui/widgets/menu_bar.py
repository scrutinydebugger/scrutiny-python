#    menu_bar.py
#        The window top menubar
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['MenuBar']

from PySide6.QtWidgets import QMenuBar
from PySide6.QtGui import QAction, QKeySequence

class Actions:
    dashboard_open: QAction
    dashboard_save: QAction
    dashboard_clear: QAction
    
    server_launch_local: QAction
    device_configure: QAction
    info_about: QAction

class MenuBar(QMenuBar):
    buttons:Actions
    
    def __init__(self, ) -> None:
        super().__init__()
        self.buttons = Actions()
       
        dashboard_menu = self.addMenu('Dashboard')
        self.buttons.dashboard_open = dashboard_menu.addAction("Open", QKeySequence.StandardKey.Open)
        self.buttons.dashboard_save = dashboard_menu.addAction("Save", QKeySequence.StandardKey.SaveAs)
        self.buttons.dashboard_clear = dashboard_menu.addAction("Clear",)

        server_menu =  self.addMenu('Server')
        self.buttons.server_launch_local = server_menu.addAction("Launch local")

        info_menu =  self.addMenu("Info")
        self.buttons.info_about = info_menu.addAction("About this software")
