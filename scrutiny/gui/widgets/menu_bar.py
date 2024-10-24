__all__ = ['MenuBar']
from PyQt5.QtWidgets import QMenuBar, QAction
from scrutiny.tools import get_not_none
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
       
        dashboard_menu = get_not_none(self.addMenu('Dashboard'))
        self.buttons.dashboard_open = get_not_none(dashboard_menu.addAction("Open"))
        self.buttons.dashboard_save = get_not_none(dashboard_menu.addAction("Save"))
        self.buttons.dashboard_close = get_not_none(dashboard_menu.addAction("Clear"))

        server_menu =  get_not_none(self.addMenu('Server'))
        self.buttons.server_launch_local = get_not_none(server_menu.addAction("Launch local"))

        info_menu =  get_not_none(self.addMenu("Info"))
        self.buttons.info_about = get_not_none(info_menu.addAction("About this software"))
