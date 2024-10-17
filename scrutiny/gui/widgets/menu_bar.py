__all__ = ['MenuBar']
from qtpy.QtWidgets import QMenuBar
from qtpy.QtGui import QAction

class Actions:
    dashboard_open: QAction
    dashboard_save: QAction
    dashboard_close: QAction
    
    server_launch_local: QAction
    device_configure: QAction
    info_about: QAction

class MenuBar(QMenuBar):
    buttons:Actions
    
    def __init__(self, ) -> None:
        super().__init__()
        self.buttons = Actions()
       
        dashboard_menu = self.addMenu('Dashboard')
        self.buttons.dashboard_open = dashboard_menu.addAction("Open")
        self.buttons.dashboard_save = dashboard_menu.addAction("Save")
        self.buttons.dashboard_close = dashboard_menu.addAction("Clear")

        server_menu =  self.addMenu('Server')
        self.buttons.server_launch_local = server_menu.addAction("Launch local")

        info_menu =  self.addMenu("Info")
        self.buttons.info_about = info_menu.addAction("About this software")
