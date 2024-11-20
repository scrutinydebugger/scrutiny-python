#    main_window.py
#        The QT Main window object
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import logging
import traceback

from PySide6.QtWidgets import  QWidget, QVBoxLayout, QHBoxLayout

from PySide6.QtGui import  QCloseEvent, QAction
from PySide6.QtCore import Qt, QRect

from PySide6.QtWidgets import QMainWindow

import PySide6QtAds  as QtAds   # type: ignore
from scrutiny.gui.dialogs.about_dialog import AboutDialog
from scrutiny.gui.widgets.sidebar import Sidebar
from scrutiny.gui.widgets.status_bar import StatusBar
from scrutiny.gui.widgets.menu_bar import MenuBar
from scrutiny.gui.dialogs.server_config_dialog import ServerConfigDialog

from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from scrutiny.gui.dashboard_components.debug.debug_component import DebugComponent
from scrutiny.gui.dashboard_components.varlist.varlist_component import VarListComponent
from scrutiny.gui.dashboard_components.watch.watch_component import WatchComponent
from scrutiny.gui.dashboard_components.embedded_graph.embedded_graph_component import EmbeddedGraph

from scrutiny.gui.core.server_manager import ServerManager
from scrutiny.gui.core.watchable_index import WatchableIndex
from typing import List, Type, Dict, Optional



class MainWindow(QMainWindow):
    INITIAL_W = 1200
    INITIAL_H = 900

    ENABLED_COMPONENTS = [
        DebugComponent,
        VarListComponent,
        WatchComponent,
        EmbeddedGraph
    ]

    _dashboard_components:Dict[str, ScrutinyGUIBaseComponent]
    _logger: logging.Logger

    _central_widget:QWidget
    _dock_conainer:QWidget
    _dock_manager:QtAds.CDockManager
    _sidebar:Sidebar
    _server_config_dialog:ServerConfigDialog
    _watchable_index:WatchableIndex
    _server_manager:ServerManager
    _menu_bar:MenuBar
    _status_bar:StatusBar

    def __init__(self) -> None:
        super().__init__()
        self._dashboard_components = {}
        self._logger = logging.getLogger(self.__class__.__name__)

        self.setWindowTitle('Scrutiny Debugger')
        self.setGeometry(self.centered(self.INITIAL_W, self.INITIAL_H))
        self.setWindowState(Qt.WindowState.WindowMaximized)

        self.make_main_zone()

        self._watchable_index = WatchableIndex()
        self._server_manager = ServerManager(watchable_index=self._watchable_index)
        
        self._status_bar = StatusBar(self, server_manager=self._server_manager)
        self.setStatusBar(self._status_bar)

        self._menu_bar = MenuBar()
        self.setMenuBar(self._menu_bar)

        self._menu_bar.buttons.info_about.triggered.connect(self.show_about)
        self._menu_bar.buttons.dashboard_close.triggered.connect(self.dashboard_close_click)
        self._menu_bar.buttons.dashboard_save.triggered.connect(self.dashboard_save_click)
        self._menu_bar.buttons.dashboard_open.triggered.connect(self.dashboard_open_click)

        self._menu_bar.buttons.dashboard_close.setDisabled(True)
        self._menu_bar.buttons.dashboard_open.setDisabled(True)
        self._menu_bar.buttons.dashboard_save.setDisabled(True)
        self._menu_bar.buttons.server_launch_local.setDisabled(True)



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
        
    def make_main_zone(self) -> None:
        self._central_widget = QWidget()
        self._central_widget.setContentsMargins(0,0,0,0)
        self.setCentralWidget(self._central_widget)
        
        hlayout = QHBoxLayout(self._central_widget)
        hlayout.setContentsMargins(0,0,0,0)
        hlayout.setSpacing(0)
        
        self._dock_conainer = QWidget()
        QtAds.CDockManager.setConfigFlag(QtAds.CDockManager.OpaqueSplitterResize)
        QtAds.CDockManager.setConfigFlag(QtAds.CDockManager.FloatingContainerHasWidgetTitle)
        QtAds.CDockManager.setConfigFlag(QtAds.CDockManager.XmlCompressionEnabled, False)
        self._dock_manager = QtAds.CDockManager(self._dock_conainer)
        
        dock_vlayout = QVBoxLayout(self._dock_conainer)
        dock_vlayout.setContentsMargins(0,0,0,0)
        
        self._sidebar = Sidebar(self.ENABLED_COMPONENTS)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self._sidebar)
        self._sidebar.insert_component.connect(self.add_new_component)

        hlayout.addWidget(self._dock_conainer)
        dock_vlayout.addWidget(self._dock_manager)
        
    def get_central_widget(self) -> QWidget:
        return self._central_widget

    def add_new_component(self, component_class:Type[ScrutinyGUIBaseComponent]) -> None:
        """Adds a new component inside the dashboard
        :param component_class: The class that represent the component (inhreiting ScrutinyGUIBaseComponent) 
        """
        
        def make_name(component_class:Type[ScrutinyGUIBaseComponent], instance_number:int) -> str:
            return f'{component_class.__name__}_{instance_number}'

        instance_number = 0
        name = make_name(component_class, instance_number)
        while name in self._dashboard_components:
            instance_number+=1
            name = make_name(component_class, instance_number)
        
        try:
            widget = component_class(self, 
                                     instance_name=name, 
                                     server_manager = self._server_manager
                                     )
        except Exception:
            self._logger.error(f"Failed to create a dashboard component of type {component_class.__name__}")
            self._logger.debug(traceback.format_exc())
            return
        QtAds.CDockWidgetTab.mouseDoubleClickEvent = None
        dock_widget = QtAds.CDockWidget(component_class.get_name())
        dock_widget.setFeature(QtAds.CDockWidget.DockWidgetDeleteOnClose, True)
        dock_widget.setWidget(widget)

        try:
            self._logger.debug(f"Setuping component {widget.instance_name}")
            widget.setup()
        except Exception as e:
            self._logger.error(f"Exception while setuping component of type {component_class.__name__} (instance name: {widget.instance_name}). {e}")
            self._logger.debug(traceback.format_exc())
            try:
                widget.teardown()
            except Exception:
                pass
            widget.deleteLater()
            dock_widget.deleteLater()
            return


        def destroy_widget() -> None:
            """Closure for this widget deletion"""
            if name in self._dashboard_components:
                del self._dashboard_components[name]

            try:
                self._logger.debug(f"Tearing down component {widget.instance_name}")
                widget.teardown()
            except Exception:
                self._logger.error(f"Exception while tearing down component {component_class.__name__} (instance name: {widget.instance_name})")
                self._logger.debug(traceback.format_exc())
                return
            finally:
                widget.deleteLater()

        self._dashboard_components[name] = widget
        dock_widget.closeRequested.connect(destroy_widget)
        self._dock_manager.addDockWidget(QtAds.TopDockWidgetArea, dock_widget)

    def start_server_manager(self) -> None:
        self._status_bar.emulate_connect_click()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._server_manager.stop()
        self._dock_manager.deleteLater()
        super().closeEvent(event)
        
    def dashboard_close_click(self) -> None:
        pass

    def dashboard_save_click(self) -> None:
        print(self._dock_manager.saveState())

    def dashboard_open_click(self) -> None:
        pass
