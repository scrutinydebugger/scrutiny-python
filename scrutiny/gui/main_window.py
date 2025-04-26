#    main_window.py
#        The QT Main window object
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import logging

from PySide6.QtWidgets import  QWidget, QHBoxLayout
from PySide6.QtGui import  QCloseEvent
from PySide6.QtCore import Qt, QRect
from PySide6.QtWidgets import QMainWindow 

from scrutiny.gui.core.preferences import gui_preferences
from scrutiny.gui.app_settings import app_settings
from scrutiny.gui.tools.invoker import InvokeQueued

from scrutiny.gui.dialogs.about_dialog import AboutDialog
from scrutiny.gui.widgets.component_sidebar import ComponentSidebar
from scrutiny.gui.widgets.status_bar import StatusBar
from scrutiny.gui.widgets.menu_bar import MenuBar
from scrutiny.gui.dialogs.server_config_dialog import ServerConfigDialog
from scrutiny.gui.dashboard.dashboard import Dashboard

from scrutiny.gui.components.locals.base_local_component import ScrutinyGUIBaseLocalComponent
from scrutiny.gui.components.globals.base_global_component import ScrutinyGUIBaseGlobalComponent
from scrutiny.gui.components.base_component import ScrutinyGUIBaseComponent
from scrutiny.gui.components.globals.varlist.varlist_component import VarListComponent
from scrutiny.gui.components.locals.watch.watch_component import WatchComponent
from scrutiny.gui.components.locals.continuous_graph.continuous_graph_component import ContinuousGraphComponent
from scrutiny.gui.components.locals.embedded_graph.embedded_graph_component import EmbeddedGraph
from scrutiny.gui.components.globals.metrics.metrics_component import MetricsComponent

from scrutiny.gui.core.server_manager import ServerManager
from scrutiny.gui.core.watchable_registry import WatchableRegistry

from scrutiny.tools.typing import *

class MainWindow(QMainWindow):
    INITIAL_W = 1200
    INITIAL_H = 900

    ENABLED_GLOBALS_COMPONENTS:List[Type[ScrutinyGUIBaseGlobalComponent]] = [
        VarListComponent,
        MetricsComponent
    ]

    ENABLED_LOCAL_COMPONENTS:List[Type[ScrutinyGUIBaseLocalComponent]] = [
        WatchComponent,
        ContinuousGraphComponent,
        EmbeddedGraph
    ]
    
    _logger: logging.Logger

    _central_widget:QWidget
    
    _component_sidebar:ComponentSidebar
    _server_config_dialog:ServerConfigDialog
    _watchable_registry:WatchableRegistry
    _server_manager:ServerManager
    _menu_bar:MenuBar
    _status_bar:StatusBar
    _dashboard:Dashboard

    def __init__(self) -> None:
        super().__init__()       
        
        self._logger = logging.getLogger(self.__class__.__name__)
        
        self.setWindowTitle('Scrutiny Debugger')
        self.setGeometry(self.centered(self.INITIAL_W, self.INITIAL_H))
        self.setWindowState(Qt.WindowState.WindowMaximized)

        self._watchable_registry = WatchableRegistry()
        self._server_manager = ServerManager(watchable_registry=self._watchable_registry)
        self._dashboard = Dashboard(self)

        self._make_main_zone()
        
        self._status_bar = StatusBar(self, server_manager=self._server_manager)
        self.setStatusBar(self._status_bar)

        self._menu_bar = MenuBar()
        self.setMenuBar(self._menu_bar)

        self._menu_bar.buttons.info_about.triggered.connect(self.show_about)
        self._menu_bar.buttons.dashboard_clear.triggered.connect(self._dashboard_clear_click)
        self._menu_bar.buttons.dashboard_save.triggered.connect(self._dashboard_save_click)
        self._menu_bar.buttons.dashboard_open.triggered.connect(self._dashboard_open_click)

        self._menu_bar.buttons.dashboard_clear.setDisabled(False)
        self._menu_bar.buttons.dashboard_open.setDisabled(False)
        self._menu_bar.buttons.dashboard_save.setDisabled(False)
        self._menu_bar.buttons.server_launch_local.setDisabled(True)

        if app_settings().auto_connect:
            InvokeQueued(self.start_server_manager)

    def centered(self, w:int, h:int) -> QRect:
        """Returns a rectangle centered in the screen of given width/height"""
        screen = self.screen()
        assert screen is not None
        return QRect(
            max((screen.geometry().width() - w), 0) // 2,
            max((screen.geometry().height() - h), 0) // 2,
            w,h)

    def show_about(self) -> None:
        dialog = AboutDialog(self)
        dialog.setGeometry(self.centered(400, 200))
        dialog.show()
        
    def _make_main_zone(self) -> None:
        self._central_widget = QWidget()
        self._central_widget.setContentsMargins(0,0,0,0)
        self.setCentralWidget(self._central_widget)
        
        hlayout = QHBoxLayout(self._central_widget)
        hlayout.setContentsMargins(0,0,0,0)
        hlayout.setSpacing(0)
        
        self._component_sidebar = ComponentSidebar(
            global_components=self.ENABLED_GLOBALS_COMPONENTS, 
            local_components=self.ENABLED_LOCAL_COMPONENTS
            )
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self._component_sidebar)

        self._component_sidebar.insert_local_component.connect(self._dashboard.add_local_component)
        self._component_sidebar.show_global_component.connect(self._dashboard.create_or_show_global_component)

        hlayout.addWidget(self._dashboard)
        self._dashboard.make_default_dashboard()
        
    def start_server_manager(self) -> None:
        self._status_bar.emulate_connect_click()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._server_manager.exit()
        self._watchable_registry.clear()
        self._dashboard.exit()
        gui_preferences.save()  # Not supposed to raise
        super().closeEvent(event)
        
    def _dashboard_clear_click(self) -> None:
        self._dashboard.make_default_dashboard()

    def _dashboard_save_click(self) -> None:
        self._dashboard.save()

    def _dashboard_open_click(self) -> None:
        self._dashboard.open()

    def get_server_manager(self) -> ServerManager:
        return self._server_manager

    def get_watchable_registry(self) -> WatchableRegistry:
        return self._watchable_registry
