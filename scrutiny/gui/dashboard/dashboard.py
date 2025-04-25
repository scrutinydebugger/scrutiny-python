import logging
from dataclasses import dataclass
import os
from uuid import uuid4
import json
from datetime import datetime

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt

import PySide6QtAds  as QtAds   # type: ignore
import shiboken6

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
from scrutiny.gui.dashboard import dashboard_file_format

from scrutiny.gui.tools import prompt

from scrutiny.tools.typing import *
from scrutiny import tools

if TYPE_CHECKING:
    from scrutiny.gui.main_window import MainWindow

@dataclass 
class SplitterAndSizePair:
    splitter : QtAds.CDockSplitter
    sizes:List[int]

@dataclass
class BuildSplitterRecursiveMutableData:
    splitter_sizes:List[ SplitterAndSizePair]

@dataclass
class BuildSplitterRecursiveImmutableData:
    name_suffix:str
    top_level : bool

class Dashboard(QWidget):
    FILE_EXT = ".scdb"
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
        except Exception as e:
            tools.log_exception(self._logger, e, f"Failed to create a dashboard component of type {component_class.__name__}")    
            return
        
        dock_widget = QtAds.CDockWidget(component_class.get_name())
        self._configure_new_dock_widget(dock_widget)
        if widget.instance_name in self._dock_manager.dockWidgetsMap():
            self._logger.error(f"Duplicate dashboard instance name {widget.instance_name}.")
        dock_widget.setObjectName(widget.instance_name) # Name required to be unique by QT ADS.
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

        def ready_if_not_deleted() -> None:
            # If the component is created but unused (deleted at func exit), this could happend
            if shiboken6.isValid(widget):
                widget.ready()

        InvokeQueued(ready_if_not_deleted)

        def destroy_widget() -> None:
            """Closure for this widget deletion"""
            if name in self._component_instances:
                del self._component_instances[name]
            
            if issubclass(component_class, ScrutinyGUIBaseGlobalComponent):
                self._global_components[component_class] = None

            if not shiboken6.isValid(widget):
                self._logger.warning("Cannot teardown widget, already deleted")
                return

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
        if component is None:
            self._logger.error("Dock widget has no component widget")
            return
        if isinstance(component, ScrutinyGUIBaseGlobalComponent):
            self._dock_manager.addAutoHideDockWidget(QtAds.SideBarRight, dock_widget)
        else:
            self._dock_manager.addDockWidgetTab(QtAds.TopDockWidgetArea, dock_widget)
    

    def make_default_dashboard(self) -> None:
        pass


    def exit(self) -> None:
        self._dock_manager.deleteLater()

    def save(self) -> None:
        """Export the actual dashboard to a file that can be reloaded later"""
        filepath = prompt.get_save_filepath_from_last_save_dir(self, self.FILE_EXT)
        if filepath is None:
            return
        
        try:
            dashboard_struct = dashboard_file_format.SerializableDashboard(
                main_container = dashboard_file_format.serialize_container(self._dock_manager),
                floating_containers=[], # Added below
                file_version=1,
                scrutiny_version=scrutiny.__version__,
                metadata={
                    'created_on' : datetime.now().astimezone().strftime(r'%Y-%m-%d %H:%M:%S')
                }
            )

            ads_floating_dock_containers = self._dock_manager.floatingWidgets()
            for ads_floating_dock_container in ads_floating_dock_containers:
                ads_dock_container = ads_floating_dock_container.dockContainer()
                dashboard_struct.floating_containers.append(dashboard_file_format.serialize_container(ads_dock_container))

            dashboard_json = json.dumps(dashboard_struct.to_dict(), indent=2)

        except Exception as e:
            tools.log_exception(self._logger, e, "Internal error while saving the dashboard")
            prompt.exception_msgbox(title="Error while saving", parent=self, exception=e, message="Internal error while saving the dashboard")
            return
        
        try:
            with open(filepath, 'wb') as f:
                f.write(dashboard_json.encode('utf8'))
        except Exception as e:
            prompt.exception_msgbox(title="Failed to save dashboard", parent=self, exception=e, message="Failed to save dashboard")
            tools.log_exception(self._logger, e, "Failed to save")
            return

    def clear(self) -> None:
        """Removes everything from the dashboard. 
        The ADS internal map maps object name to the widget. title is used if no object name is explicitly set before registration.
        Colliding names may cause this map to not return all the references, leaving some stray widget after clear.
        """
        dock_widgets = self._dock_manager.dockWidgetsMap()
        for title, dock_widget in dock_widgets.items():
            dock_widget.closeDockWidget()   # Widgets are supposed to be "deleteOnClose". Will trigger the destroy callback that will call each component teardown()

    def open(self) -> None:
        filepath = prompt.get_open_filepath_from_last_save_dir(self, self.FILE_EXT)
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
                json_decoded = json.load(f)
                serialized_dashboard = dashboard_file_format.SerializableDashboard.from_dict(json_decoded)
        except Exception as e:
            prompt.exception_msgbox(title="Failed to open dashboard", parent=self, exception=e, message="Failed to parse the dashboard file. JSON is invalid")
            tools.log_exception(self._logger, e, "Failed to open")
            return 
        
        self.clear()
        self._restore_splitpane_recursive(self._dock_manager, serialized_dashboard.main_container.root_splitter)
        self._restore_sidebar_components(self._dock_manager, serialized_dashboard.main_container.sidebar_components)

        for floating_container in serialized_dashboard.floating_containers:
            placeholder = self._create_placeholder_dock_widget()
            ads_floating_container = self._dock_manager.addDockWidgetFloating(placeholder)
            self._restore_splitpane_recursive(ads_floating_container.dockContainer(), floating_container.root_splitter, first_ads_dock_area=placeholder.dockAreaWidget())
            self._restore_sidebar_components(ads_floating_container.dockContainer(), floating_container.sidebar_components)
            placeholder.deleteDockWidget()

    def _configure_new_dock_widget(self, widget:QtAds.CDockWidget) -> None:
        if app_settings().opengl_enabled:
            prepare_for_opengl(widget)
    
    def _create_placeholder_dock_widget(self, title:Optional[str] = None) -> QtAds.CDockWidget:
        if title is None:
            title = "placeholder"
        dock_widget = QtAds.CDockWidget(title)
        dock_widget.setObjectName(uuid4().hex)
        self._configure_new_dock_widget(dock_widget)
        return dock_widget


    def _find_parent_splitter(self, dock_area:QtAds.CDockAreaWidget) -> Optional[QtAds.CDockSplitter]:
        """Finds the splitter that owns a dock area"""
        parent = dock_area.parent()
        while parent is not None:
            if isinstance(parent, QtAds.CDockSplitter):
                return parent
            parent = parent.parent()
        return None

    def _create_dock_widget_from_component_serialized(self, s_component:dashboard_file_format.SerializableComponent) -> Optional[QtAds.CDockWidget]:
        component_class = ScrutinyGUIBaseComponent.class_from_type_id(s_component.type_id)
        if component_class is None:
            self._logger.warning(f"Unknown dashboard component : id={s_component.type_id}")
            return None

        component_dock_widget = self.create_new_component(component_class)
        component_dock_widget.tabWidget().setText(s_component.title)
        return component_dock_widget

    def _restore_splitpane_recursive(self,
                           top_level_container:QtAds.CDockContainerWidget,  
                           s_splitter:dashboard_file_format.SerializableSplitter, 
                           first_ads_dock_area:Optional[QtAds.CDockAreaWidget] = None,
                           mutable_data:Optional[BuildSplitterRecursiveMutableData]=None,
                           immutable_data:Optional[BuildSplitterRecursiveImmutableData]=None
                           ) -> None:
        """ Recreate a dashboard top level container by performing a series of AddDockWidget.
        
        We do not have access to internal ADS dunction to create splitters and containers, so we rely on a workaround
        that consist of adding a series of placeholders widget to create dock areas, fill the dock area then delete the placeholder.

        Mutable data is shared for each recursive call.
        Immurable data is copied for each sub call
        """

        # Top level. Create the data that passes down
        if mutable_data is None:
            mutable_data = BuildSplitterRecursiveMutableData(
                splitter_sizes=[]
            )
        if immutable_data is None:
            immutable_data = BuildSplitterRecursiveImmutableData(name_suffix="", top_level=True)

        # The area to add the widgets
        if s_splitter.orientation == dashboard_file_format.SplitterOrientation.VERTICAL:
            ads_area_direction = QtAds.BottomDockWidgetArea
        elif s_splitter.orientation == dashboard_file_format.SplitterOrientation.HORIZONTAL:
            ads_area_direction = QtAds.RightDockWidgetArea
        else:
            raise RuntimeError("Unknown splitter orientation")
        
        children_count = len(s_splitter.content)
        ads_dock_areas:List[QtAds.CDockAreaWidget] = []     # The areas that contains the placeholder that we create for this splitter
        placeholder_widgets:List[QtAds.CDockWidget] = []    # The placeholder that we create
        
        # First insert goes on top of the parent
        insert_dock_area = first_ads_dock_area
        insert_direction = QtAds.CenterDockWidgetArea

        # For each area in the splitter
        for i in range(children_count):

            # First, we create a placeholder and add it
            new_suffix = f"{immutable_data.name_suffix}_{i}"
            ads_placeholder_widget = self._create_placeholder_dock_widget(f"placeholder_{new_suffix}")
            placeholder_widgets.append(ads_placeholder_widget)

            if i > 0:
                # Lay out all subsequent sibblings next to the last one added
                insert_dock_area = ads_dock_areas[-1]
                insert_direction = ads_area_direction
            
            ads_dock_area = top_level_container.addDockWidget(insert_direction, ads_placeholder_widget, insert_dock_area)
            ads_dock_areas.append(ads_dock_area)
        
        # We need to apply the splitter sizes at the very end because adding dock widgets causes containers to be deleted and recreated, which
        # resets the sizes of the parent splitter. We keep a reference of the splitter and the sizes that it needs and we apply when recursion is finished.
        if len(ads_dock_areas) > 0:
            area = ads_dock_areas[-1]
            splitter = self._find_parent_splitter(area)
            if splitter is not None:
                mutable_data.splitter_sizes.append(SplitterAndSizePair(splitter, s_splitter.sizes))
            else:
                self._logger.error(f"Cannot find splitter containing area {area}. Dashboard sizes might be wrong")
        
        # Placeholder are laid out, the dock areas exists. Now fill the dock areas with either a splitter or a component.
        for i in range(children_count):
            s_child_node = s_splitter.content[i]
            if isinstance(s_child_node, dashboard_file_format.SerializableSplitter):
                new_immutable_data = BuildSplitterRecursiveImmutableData(
                    name_suffix=new_suffix,
                    top_level=False
                )
                self._restore_splitpane_recursive(top_level_container, s_child_node, ads_dock_areas[i], mutable_data=mutable_data, immutable_data=new_immutable_data)
            elif isinstance(s_child_node, dashboard_file_format.SerializableDockArea):
                for s_dock_widget in s_child_node.dock_widgets:
                    component_dock_widget = self._create_dock_widget_from_component_serialized(s_dock_widget.component)
                    if component_dock_widget is None:
                        continue
                    # Todo : Handle active tab
                    top_level_container.addDockWidget(QtAds.CenterDockWidgetArea, component_dock_widget, ads_dock_areas[i])

        # Our splitter is fully created, remove the placeholders.
        for i in range(len(placeholder_widgets)):
            placeholder_widgets[i].deleteDockWidget()
        placeholder_widgets.clear()

        # We're done creating/deleting containers and dock areas. Resizes every splitter now.
        if immutable_data.top_level:
            for splitter_size_pair in mutable_data.splitter_sizes:
                splitter_size_pair.splitter.setSizes(splitter_size_pair.sizes)

    def _restore_sidebar_components(self, 
                     dock_container:QtAds.CDockContainerWidget, 
                     s_sidebar_components:List[dashboard_file_format.SerializableSideBarComponent]
                     ) -> None:
        """Reads a dict struct coming from a dashboard file and restore all the ADS autohide widgets (sidebar buttons).
        Done per container. Each window has a top container.
        """

        for s_sidebar_component in s_sidebar_components:    # For each sidebar component for that container
            component_dock_widget = self._create_dock_widget_from_component_serialized(s_sidebar_component.component)
            if component_dock_widget is None:   # None if the scrutiny component is unknown
                continue
            
            # Register to ADS
            ads_autohide_dock_container = self._dock_manager.addAutoHideDockWidgetToContainer(
                s_sidebar_component.sidebar_location.to_ads(), # Where we add it (LEFT, RIGHT, TOP, BOTTOM)
                component_dock_widget,  # What we add
                dock_container          # On what container we add it
                )
            ads_autohide_dock_container.setSize(s_sidebar_component.size)   # vertical/horizontal handled internally
