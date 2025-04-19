import logging
from dataclasses import dataclass
import json
import enum

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt, QTimer, QXmlStreamWriter, QFile

import PySide6QtAds  as QtAds   # type: ignore

from scrutiny.gui.components.user.base_user_component import ScrutinyGUIBaseUserComponent
from scrutiny.gui.components.globals.base_global_component import ScrutinyGUIBaseGlobalComponent
from scrutiny.gui.components.base_component import ScrutinyGUIBaseComponent

from scrutiny.gui.tools.opengl import prepare_for_opengl
from scrutiny.gui.app_settings import app_settings

from scrutiny.gui.components.globals.varlist.varlist_component import VarListComponent
from scrutiny.gui.components.user.watch.watch_component import WatchComponent
from scrutiny.gui.components.user.continuous_graph.continuous_graph_component import ContinuousGraphComponent
from scrutiny.gui.components.user.embedded_graph.embedded_graph_component import EmbeddedGraph
from scrutiny.gui.components.globals.metrics.metrics_component import MetricsComponent

from scrutiny.tools.typing import *
from scrutiny import tools

if TYPE_CHECKING:
    from scrutiny.gui.main_window import MainWindow

@dataclass
class SerializableComponent:
    title:str
    component_type:str
    component_state:Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'title' : self.title,
            'component_type' : self.component_type,
            'component_state' : self.component_state
        }


@dataclass
class SerializableDockWidget:
    current_tab:bool
    component:SerializableComponent

    def to_dict(self) -> Dict[str, Any]:
        return {
            'current_tab' : self.current_tab,
            'component' : self.component.to_dict()
        }

@dataclass
class SerializableDockArea:
    dock_widgets:List[SerializableDockWidget]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'dock_widgets' : [dw.to_dict() for dw in self.dock_widgets]
        }

@dataclass
class SerializableContainer:
    floating:bool
    dock_areas : List[SerializableDockArea]

    def to_dict(self)-> Dict[str, Any]:
        return {
            'floating' : self.floating,
            'dock_areas' : [da.to_dict() for da in self.dock_areas]
        }

class SidebarLocation(enum.Enum):
    TOP = 'top'
    LEFT = 'left'
    RIGHT = 'right'
    BOTTOM = 'bottom'

    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def from_str(cls, v:str) -> "SidebarLocation":
        return cls(v)
    
    @classmethod
    def from_ads(cls, v:int) -> "SidebarLocation":
        lookup = {
            QtAds.SideBarLeft.value : cls.LEFT,
            QtAds.SideBarTop.value : cls.TOP,
            QtAds.SideBarBottom.value : cls.BOTTOM,
            QtAds.SideBarRight.value : cls.RIGHT,
        }

        return lookup[v]

@dataclass
class SerializableSideBarComponent:
    sidebar_location:SidebarLocation
    component:SerializableComponent

    def to_dict(self) -> Dict[str, Any]:
        return {
            'sidebar_location' : str(self.sidebar_location),
            'component' : self.component.to_dict()
        }

@dataclass
class SerializableDashboard:
    containers:List[SerializableContainer]
    sidebar_components:List[SerializableSideBarComponent]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'containers' : [c.to_dict() for c in self.containers],
            'sidebar_components' : [sc.to_dict() for sc in self.sidebar_components]
        }




class Dashboard(QWidget):
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

    def add_new_component(self, component_class:Type[ScrutinyGUIBaseComponent]) -> None:
        """Adds a new component inside the dashboard
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

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(0)
        timer.timeout.connect(widget.ready)
        timer.start()

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
        if issubclass(component_class, ScrutinyGUIBaseGlobalComponent):
            self._dock_manager.addAutoHideDockWidget(QtAds.SideBarRight, dock_widget)
        else:
            self._dock_manager.addDockWidgetTab(QtAds.TopDockWidgetArea, dock_widget)
        

    def make_default_dashboard(self) -> None:
        pass


    def exit(self) -> None:
        self._dock_manager.deleteLater()

    def save(self) -> None:
        dashboard_struct = SerializableDashboard(containers=[], sidebar_components=[])
        ads_containers = self._dock_manager.dockContainers()
        for ads_container in ads_containers:
            container = SerializableContainer(
                floating=ads_container.isFloating(),
                dock_areas=[]
                )
            dashboard_struct.containers.append(container)
            for i in range(ads_container.dockAreaCount()):
                ads_dock_area = ads_container.dockArea(i)
                dock_area = SerializableDockArea(
                    dock_widgets=[]
                )
                container.dock_areas.append(dock_area)
                for j in range(ads_dock_area.dockWidgetsCount()):
                    ads_dock_widget = ads_dock_area.dockWidget(j)
                    scrutiny_component = cast(ScrutinyGUIBaseComponent, ads_dock_widget.widget())
                    dock_widget = SerializableDockWidget(
                        current_tab = ads_dock_widget.isCurrentTab(),
                        component=SerializableComponent(
                            title="???",
                            component_type=scrutiny_component.get_type_id(),
                            component_state= scrutiny_component.get_state()
                        )
                    )
                    dock_area.dock_widgets.append(dock_widget)
        
        ads_autohide_containers = ads_container.autoHideWidgets()
        for ads_autohide_container in ads_autohide_containers:
            ads_dock_widget = ads_autohide_container.dockWidget()
            scrutiny_component = cast(ScrutinyGUIBaseComponent, ads_dock_widget.widget())
            sidebar_component = SerializableSideBarComponent(
                sidebar_location=SidebarLocation.from_ads(ads_autohide_container.sideBarLocation()),
                component=SerializableComponent(
                    title="???",
                    component_type=scrutiny_component.get_type_id(),
                    component_state=scrutiny_component.get_state()
                )
            )
            dashboard_struct.sidebar_components.append(sidebar_component)

        print(json.dumps(dashboard_struct.to_dict(), indent=4))

    def clear(self) -> None:
        dock_widgets = self._dock_manager.dockWidgetsMap()
        for title, dock_widget in dock_widgets.items():
            component = dock_widget.widget()
            dock_widget.closeDockWidget()


    def open(self) -> None:
        pass
    