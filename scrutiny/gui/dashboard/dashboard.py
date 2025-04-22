import logging
from dataclasses import dataclass
import json
import enum
import os
from datetime import datetime

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSplitter
from PySide6.QtCore import Qt, QTimer, QXmlStreamWriter, QFile

import PySide6QtAds  as QtAds   # type: ignore

import scrutiny 
from scrutiny.gui.components.user.base_user_component import ScrutinyGUIBaseUserComponent
from scrutiny.gui.components.globals.base_global_component import ScrutinyGUIBaseGlobalComponent
from scrutiny.gui.components.base_component import ScrutinyGUIBaseComponent

from scrutiny.gui.tools.opengl import prepare_for_opengl
from scrutiny.gui.app_settings import app_settings
from scrutiny.gui.tools.invoker import InvokeQueued

from scrutiny.gui.components.globals.varlist.varlist_component import VarListComponent
from scrutiny.gui.components.user.watch.watch_component import WatchComponent
from scrutiny.gui.components.user.continuous_graph.continuous_graph_component import ContinuousGraphComponent
from scrutiny.gui.components.user.embedded_graph.embedded_graph_component import EmbeddedGraph
from scrutiny.gui.components.globals.metrics.metrics_component import MetricsComponent
from scrutiny.gui.dashboard.dashboard_file_v1 import DashboardFileFormatV1

from scrutiny.gui.tools import prompt

from scrutiny.tools.typing import *
from scrutiny import tools

if TYPE_CHECKING:
    from scrutiny.gui.main_window import MainWindow


class Dashboard(QWidget):
    FILE_FORMAT_VERSION = 1
    MAX_FILE_SIZE_TO_LOAD = 64*1024*1024

    _main_window:"MainWindow"
    _dock_manager:QtAds.CDockManager
    _dock_conainer:QWidget
    _component_instances:Dict[str, ScrutinyGUIBaseComponent]
    _global_components:Dict[Type[ScrutinyGUIBaseGlobalComponent], Optional[ScrutinyGUIBaseGlobalComponent]]
    _logger:logging.Logger
    
    def __init__(self, main_window:"MainWindow") -> None:
        super().__init__(main_window)
        self._main_window = main_window

        self._logger = logging.getLogger(self.__class__.__name__)
        self._component_instances = {}
        self._global_components = {}

        self._dock_conainer = QWidget()
        QtAds.CDockManager.setConfigFlag(QtAds.CDockManager.OpaqueSplitterResize)
        QtAds.CDockManager.setConfigFlag(QtAds.CDockManager.FloatingContainerHasWidgetTitle)
        QtAds.CDockManager.setConfigFlag(QtAds.CDockManager.XmlCompressionEnabled, False)
        QtAds.CDockManager.setAutoHideConfigFlags(QtAds.CDockManager.DefaultAutoHideConfig)
        self._dock_manager = QtAds.CDockManager(self._dock_conainer)

        def configure_new_window(win:QtAds.CFloatingDockContainer) -> None:
            flags = win.windowFlags()
            flags |= Qt.WindowType.WindowMinimizeButtonHint
            flags |= Qt.WindowType.WindowCloseButtonHint
            # Negate flags by forcing 32bits wide. Python keeps the same number of bit with operator~
            flags &= (0xFFFFFFFF ^ Qt.WindowType.WindowStaysOnTopHint) 
            flags &= (0xFFFFFFFF ^ Qt.WindowType.FramelessWindowHint) 
            win.setWindowFlags(flags)

        self._dock_manager.floatingWidgetCreated.connect(configure_new_window)

        dock_vlayout = QVBoxLayout(self._dock_conainer)
        dock_vlayout.setContentsMargins(0,0,0,0)
        dock_vlayout.addWidget(self._dock_manager)

        layout = QHBoxLayout(self)
        layout.addWidget(self._dock_conainer)

    def create_new_component(self, component_class:Type[ScrutinyGUIBaseComponent]) -> QtAds.CDockWidget:
        """Create a new component and initializes it
        :param component_class: The class that represent the component (inhreiting ScrutinyGUIBaseComponent) 
        """
        if issubclass(component_class, ScrutinyGUIBaseGlobalComponent):
            if component_class not in self._global_components:
                self._global_components[component_class] = None
            
            if self._global_components[component_class] is not None:
                return
            
        def make_name(component_class:Type[ScrutinyGUIBaseComponent], instance_number:int) -> str:
            return f'{component_class.__name__}_{instance_number}'

        instance_number = 0
        name = make_name(component_class, instance_number)
        while name in self._component_instances:
            instance_number+=1
            name = make_name(component_class, instance_number)
        
        try:
            widget = component_class(self._main_window, name, self._main_window.get_watchable_registry(), self._main_window.get_server_manager())
            if app_settings().opengl_enabled:
                prepare_for_opengl(widget)  # On every widget. Flaating widget creates a new window -> Must be done on each window
        except Exception as e:
            tools.log_exception(self._logger, e, f"Failed to create a dashboard component of type {component_class.__name__}")    
            return
        
        dock_widget = QtAds.CDockWidget(component_class.get_name())
        dock_widget.setFeature(QtAds.CDockWidget.DockWidgetDeleteOnClose, True)
        dock_widget.setWidget(widget)
        dock_widget.visibilityChanged.connect(widget.visibilityChanged) # Pass down the event

        try:
            self._logger.debug(f"Setuping component {widget.instance_name}")
            widget.setup()
            
        except Exception as e:
            tools.log_exception(self._logger, e, f"Exception while setuping component of type {component_class.__name__} (instance name: {widget.instance_name}).")
            with tools.SuppressException():
                widget.teardown()
            widget.deleteLater()
            dock_widget.deleteLater()
            return 

        InvokeQueued(widget.ready)

        def destroy_widget() -> None:
            """Closure for this widget deletion"""
            if name in self._component_instances:
                del self._component_instances[name]
            
            if issubclass(component_class, ScrutinyGUIBaseGlobalComponent):
                self._global_components[component_class] = None

            try:
                self._logger.debug(f"Tearing down component {widget.instance_name}")
                widget.teardown()
            except Exception as e:
                tools.log_exception(self._logger, e, f"Exception while tearing down component {component_class.__name__} (instance name: {widget.instance_name})")
                return
            finally:
                widget.deleteLater()

        self._component_instances[name] = widget
        if issubclass(component_class, ScrutinyGUIBaseGlobalComponent):
            assert isinstance(widget, ScrutinyGUIBaseGlobalComponent)
            self._global_components[component_class] = widget
            
        dock_widget.closeRequested.connect(destroy_widget)
        return dock_widget
        
    def add_widget_to_default_location(self, dock_widget:QtAds.CDockWidget) -> None:
        component = cast(ScrutinyGUIBaseComponent, dock_widget.widget())
        if isinstance(component, ScrutinyGUIBaseGlobalComponent):
            self._dock_manager.addAutoHideDockWidget(QtAds.SideBarRight, dock_widget)
        else:
            self._dock_manager.addDockWidgetTab(QtAds.TopDockWidgetArea, dock_widget)
    

    def make_default_dashboard(self) -> None:
        pass


    def exit(self) -> None:
        self._dock_manager.deleteLater()

    def save(self) -> None:
#        dashboard_struct = SerializableDashboard(containers=[], sidebar_components=[])
#        ads_containers = self._dock_manager.dockContainers()
#        for ads_container in ads_containers:
#            container = SerializableContainer(
#                floating=ads_container.isFloating(),
#                dock_areas=[]
#                )
#            dashboard_struct.containers.append(container)
#            for i in range(ads_container.dockAreaCount()):
#                pass
#        
#        ads_autohide_containers = ads_container.autoHideWidgets()
#        for ads_autohide_container in ads_autohide_containers:
#            ads_dock_widget = ads_autohide_container.dockWidget()
#            scrutiny_component = cast(ScrutinyGUIBaseComponent, ads_dock_widget.widget())
#            sidebar_component = SerializableSideBarComponent(
#                sidebar_location=SidebarLocation.from_ads(ads_autohide_container.sideBarLocation()),
#                component=SerializableComponent(
#                    title=ads_dock_widget.tabWidget().text(),
#                    type=scrutiny_component.get_type_id(),
#                    state=scrutiny_component.get_state()
#                )
#            )
#            dashboard_struct.sidebar_components.append(sidebar_component)


        filepath = prompt.get_save_filepath_from_last_save_dir(self, ".scdb")
        if filepath is None:
            return
        
        try:
            # When v2 exist, add a class swapping mechanism
            data = DashboardFileFormatV1.content_from_dock_manager(self._dock_manager)
        except Exception as e:
            tools.log_exception(self._logger, e, "Internal error while saving the dashboard")
            prompt.exception_msgbox(title="Error while saving", parent=self, exception=e, message="Internal error while saving the dashboard")
            return
        
        try:
            with open(filepath, 'wb') as f:
                f.write(data)
        except Exception as e:
            prompt.exception_msgbox(title="Failed to save dashboard", parent=self, exception=e, message="Failed to save dashboard")
            tools.log_exception(self._logger, e, "Failed to save")
            return

    def clear(self) -> None:
        dock_widgets = self._dock_manager.dockWidgetsMap()
        for title, dock_widget in dock_widgets.items():
            dock_widget.closeDockWidget()


    def open(self) -> None:
        filepath = prompt.get_open_filepath_from_last_save_dir(self, ".scdb")
        if filepath is None:
            return
        
        if not os.path.isfile(filepath):
            prompt.error_msgbox(self, "File not found", f"File {filepath} does not exist")
            return
        
        filesize = os.path.getsize(filepath)
        if filesize > self.MAX_FILE_SIZE_TO_LOAD:
            prompt.error_msgbox(self, "File too big", f"File {filepath} has a size of {filesize} bytes. This is unusual for a dashboard.\n Will not load. (max={self.MAX_FILE_SIZE_TO_LOAD}).")
            return
        
        try:
            with open(filepath, 'rb') as f:
                decoded = DashboardFileFormatV1.read_from_file(f)
        except Exception as e:
            prompt.exception_msgbox(title="Failed to open dashboard", parent=self, exception=e, message="Failed to parse the dashboard file. JSON is invalid")
            tools.log_exception(self._logger, e, "Failed to open")
            return 
        
        #
        self.clear()

    