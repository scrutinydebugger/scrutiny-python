from qtpy.QtWidgets import QMenuBar, QAction
from scrutiny.gui.core.server_manager import ServerManager

class Actions:
    dashboard_open: QAction
    dashboard_save: QAction
    dashboard_close: QAction
    
    server_configure: QAction
    server_connect: QAction
    server_disconnect: QAction
    server_launch_local: QAction

    device_configure: QAction
    
    info_about: QAction

class MenuBar(QMenuBar):
    actions:Actions
    
    def __init__(self, ) -> None:
        super().__init__()
        self.actions = Actions()
       
        dashboard_menu = self.addMenu('Dashboard')
        self.actions.dashboard_open = dashboard_menu.addAction("Open")
        self.actions.dashboard_save = dashboard_menu.addAction("Save")
        self.actions.dashboard_close = dashboard_menu.addAction("Clear")

        server_menu = self.addMenu('Server')
        self.actions.server_configure = server_menu.addAction("Configure")
        self.actions.server_connect = server_menu.addAction("Connect")
        self.actions.server_disconnect = server_menu.addAction("Disconnect")
        self.actions.server_launch_local = server_menu.addAction("Launch local")

        server_menu = self.addMenu('Device')
        self.actions.device_configure = server_menu.addAction("Configure")

        info_menu = self.addMenu("Info")
        self.actions.info_about = info_menu.addAction("About this software")
