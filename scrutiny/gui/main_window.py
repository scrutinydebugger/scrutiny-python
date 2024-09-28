import logging
import traceback

from qtpy.QtWidgets import  QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStatusBar, QDialog

from qtpy.QtGui import  QAction, QCloseEvent
from qtpy.QtCore import Qt, QRect
from qtpy.QtWidgets import QMainWindow

from scrutiny.gui.qtads import QtAds    #Advanced Docking System
from scrutiny.gui.widgets.about_dialog import AboutDialog
from scrutiny.gui.widgets.sidebar import Sidebar
from scrutiny.gui.widgets.server_config_dialog import ServerConfigDialog

from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from scrutiny.gui.dashboard_components.debug.debug_component import DebugComponent
from scrutiny.gui.dashboard_components.varlist.varlist_component import VarListComponent
from scrutiny.gui.dashboard_components.watch.watch_component import WatchComponent
from scrutiny.gui.dashboard_components.embedded_graph.embedded_graph_component import EmbeddedGraph

from typing import List, Type, Dict



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
    _logger = logging.Logger

    _central_widget:QWidget
    _dock_conainer:QWidget
    _dock_manager:QtAds.CDockManager
    _sidebar:Sidebar
    _status_bar:QStatusBar
    _server_config_dialog:ServerConfigDialog

    def __init__(self):
        super().__init__()
        self._dashboard_components = {}
        self._logger = logging.getLogger(self.__class__.__name__)

        self.setWindowTitle('Scrutiny Debugger')
        self.setGeometry(self.centered(self.INITIAL_W, self.INITIAL_H))
        self.setWindowState(Qt.WindowState.WindowMaximized)

        self.make_menubar()
        self.make_main_zone()
        self.make_status_bar()

        self._server_config_dialog = ServerConfigDialog(self, self.server_config_changed)

    def make_menubar(self) -> None:
        menu_bar = self.menuBar()
        dashboard_menu = menu_bar.addMenu('Dashboard')
        dashboard_menu.addAction("Open").setDisabled(True)
        dashboard_menu.addAction("Save").setDisabled(True)
        dashboard_menu.addAction("Clear").setDisabled(True)

        server_menu = menu_bar.addMenu('Server')
        server_config_action = server_menu.addAction("Configure")
        server_config_action.triggered.connect(self.menu_server_config_click)

        server_menu.addAction("Launch local").setDisabled(True)
        server_menu = menu_bar.addMenu('Device')
        server_menu.addAction("Configure").setDisabled(True)

        info_menu = menu_bar.addMenu("Info")
        show_about_action = QAction("About this software", self)
        show_about_action.triggered.connect(self.show_about)
        info_menu.addAction(show_about_action)
    
    def centered(self, w:int, h:int) -> QRect:
        """Returns a rectangle centered in the screen of given width/height"""
        return QRect(
            max((self.screen().geometry().width() - w), 0) // 2,
            max((self.screen().geometry().height() - h), 0) // 2,
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

    def make_status_bar(self) -> None:
        self._status_bar = self.statusBar()
        self._status_bar.addWidget(QLabel("hello"))

    def add_new_component(self, component_class:Type[ScrutinyGUIBaseComponent]) -> None:
        """Adds a new component inside the dashboard
        :param component_class: The class that represent the component (inhreiting ScrutinyGUIBaseComponent) 
        """
        
        def make_name(component_class:Type[ScrutinyGUIBaseComponent], instance_number:int):
            return f'{component_class.__name__}_{instance_number}'

        instance_number = 0
        name = make_name(component_class, instance_number)
        while name in self._dashboard_components:
            instance_number+=1
            name = make_name(component_class, instance_number)
        
        try:
            widget = component_class(self, name)
        except Exception:
            self._logger.error(f"Failed to create a dashboard component of type {component_class.__name__}")
            self._logger.debug(traceback.format_exc())
            return

        dock_widget = QtAds.CDockWidget(component_class.get_name())
        dock_widget.setFeature(QtAds.CDockWidget.DockWidgetDeleteOnClose, True)
        dock_widget.setWidget(widget)

        try:
            self._logger.debug(f"Setuping component {widget.instance_name}")
            widget.setup()
        except Exception:
            self._logger.error(f"Exception while setuping component of type {component_class.__name__} (instance name: {widget.instance_name})")
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

    def closeEvent(self, event: QCloseEvent):
        self._dock_manager.deleteLater()
        super().closeEvent(event)

    def menu_server_config_click(self) -> None:
        self._server_config_dialog.show()

    def server_config_changed(self):
        print("config changed")
        
