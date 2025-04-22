from dataclasses import dataclass
import enum
import json
from datetime import datetime

import PySide6QtAds  as QtAds   # type: ignore
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSplitter

import scrutiny
from scrutiny.gui.components.base_component import ScrutinyGUIBaseComponent
from scrutiny.tools.typing import *
from scrutiny.tools import validation

if TYPE_CHECKING:
    from _typeshed import SupportsRead


@dataclass
class SerializableComponent:
    TYPE = 'component'

    title:str
    type_id:str
    state:Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type' : self.TYPE,
            'title' : self.title,
            'type_id' : self.type_id,
            'state' : self.state
        }
    
    @classmethod
    def from_dict(cls, d:Dict[str, Any]) -> Self:
        validation.assert_dict_key(d, 'type', str)
        validation.assert_dict_key(d, 'title', str)
        validation.assert_dict_key(d, 'type_id', str)
        validation.assert_dict_key(d, 'state', dict)
        
        if d['type'] != cls.TYPE:
            raise ValueError(f"Expected node of type {cls.TYPE}, got {d['type']}")
        
        return cls(
            title = d['title'],
            type_id = d['type_id'],
            state = d['state']
        )


@dataclass
class SerializableDockWidget:
    TYPE = 'dock_widget'

    current_tab:bool
    component:SerializableComponent

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type' : self.TYPE,
            'current_tab' : self.current_tab,
            'component' : self.component.to_dict()
        }
    
    @classmethod
    def from_dict(cls, d:Dict[str, Any]) -> Self:
        validation.assert_dict_key(d, 'type', str)
        validation.assert_dict_key(d, 'current_tab', bool)
        validation.assert_dict_key(d, 'component', dict)
        
        if d['type'] != cls.TYPE:
            raise ValueError(f"Expected node of type {cls.TYPE}, got {d['type']}")
        
        return cls(
            current_tab = d['current_tab'],
            component = SerializableComponent.from_dict(d['component'])
        )

@dataclass
class SerializableDockArea:
    TYPE = 'dock_area'
    dock_widgets:List[SerializableDockWidget]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type' : self.TYPE,
            'dock_widgets' : [dw.to_dict() for dw in self.dock_widgets]
        }
    
    @classmethod
    def from_dict(cls, d:Dict[str, Any]) -> Self:
        validation.assert_dict_key(d, 'type', str)
        validation.assert_dict_key(d, 'dock_widgets', list)
        if d['type'] != cls.TYPE:
            raise ValueError(f"Expected node of type {cls.TYPE}, got {d['type']}")
        
        dock_widgets:List[SerializableDockWidget] = []
        for element in d['dock_widgets']:
            validation.assert_type(element, 'dock_area.dock_widgets[...]', dict)
            validation.assert_dict_key(element, 'type', str)

            dock_widgets.append(SerializableDockWidget.from_dict(element))

        return cls(
            dock_widgets=dock_widgets
        )

@dataclass
class SerializableContainer:
    TYPE = 'container'
    floating:bool
    dock_areas : List[SerializableDockArea]

    def to_dict(self)-> Dict[str, Any]:
        return {
            'type' : self.TYPE,
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
    TYPE = 'sidebar_component'
    sidebar_location:SidebarLocation
    component:SerializableComponent

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type' : self.TYPE,
            'sidebar_location' : str(self.sidebar_location),
            'component' : self.component.to_dict()
        }

class SplitterOrientation(enum.Enum):
    VERTICAL = 'vertical'
    HORIZONTAL = 'horizontal'

    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def from_str(cls, v:str) -> "SplitterOrientation":
        return cls(v)
    
    @classmethod
    def from_qt(cls, v:Qt.Orientation) -> "SplitterOrientation":
        lookup = {
            Qt.Orientation.Vertical : cls.VERTICAL,
            Qt.Orientation.Horizontal : cls.HORIZONTAL,
        }

        return lookup[v]

@dataclass
class SerializableSplitter:
    TYPE = 'splitter'

    orientation:SplitterOrientation
    sizes:List[int]
    content:List[Union["SerializableSplitter", "SerializableDockArea"]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type' : self.TYPE,
            'orientation' : str(self.orientation),
            'sizes' : self.sizes,
            'content' : [elem.to_dict() for elem in self.content]
        }
    
    @classmethod
    def from_dict(cls, d:Dict[str, Any]) -> Self:
        validation.assert_dict_key(d, 'type', str)
        validation.assert_dict_key(d, 'orientation', str)
        validation.assert_dict_key(d, 'sizes', list)
        validation.assert_dict_key(d, 'content', list)

        for v in d['sizes']:
            validation.assert_type(v, 'd["sizes"][...]', int)

        if d['type'] != cls.TYPE:
            raise ValueError(f"Expected node of type {cls.TYPE}, got {d['type']}")
        
        content:List[Union[SerializableDockArea, SerializableSplitter]] = []
        for element in d['content']:
            validation.assert_type(element, 'splitter.content[...]', dict)
            validation.assert_dict_key(element, 'type', str)

            if element['type'] == SerializableSplitter.TYPE:
                content.append(SerializableSplitter.from_dict(element))
            elif element['type'] == SerializableDockArea.TYPE:
                content.append(SerializableDockArea.from_dict(element))
            else:
                raise ValueError(f"Unsupported node type {d['type']}")

        return cls(
            orientation = SplitterOrientation.from_str(d['orientation']),
            sizes = d['sizes'],
            content = content
        )

@dataclass
class SerializableDashboard:
    TYPE = 'dashboard'

    root_splitter:SerializableSplitter
    metadata:Dict[str,str]
    file_version: int
    scrutiny_version:str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type':self.TYPE,
            'root_splitter' : self.root_splitter.to_dict(),
            'file_version' : self.file_version,
            'scrutiny_version' : self.scrutiny_version,
            'metadata' : self.metadata
        }
    
    @classmethod
    def from_dict(cls, d:Dict[str, Any]) -> Self:
        validation.assert_dict_key(d, 'type', str)
        validation.assert_dict_key(d, 'root_splitter', dict)
        validation.assert_dict_key(d, 'file_version', int)
        validation.assert_dict_key(d, 'scrutiny_version', (str, float))

        if d['file_version'] != 1:
            raise ValueError("Expect file version : v1")
        
        if d['type'] != cls.TYPE:
            raise ValueError(f"Expected node of type {cls.TYPE}, got {d['type']}")

        return cls(
            root_splitter=SerializableSplitter.from_dict(d['root_splitter']),
            file_version = d['file_version'],
            metadata = d.get('metadata', {}),
            scrutiny_version=str(d['scrutiny_version'])
        )



class DashboardFileFormatV1:
    @classmethod
    def _get_struct_recursive(cls, parent:Union[QtAds.CDockSplitter, QtAds.CDockAreaWidget]) -> Union[SerializableSplitter, SerializableDockArea]:
        if isinstance(parent, QtAds.CDockSplitter):
            splitter = cast(QSplitter, parent)    # Better type hint
            out = SerializableSplitter(
                orientation=SplitterOrientation.from_qt(splitter.orientation()),
                sizes=splitter.sizes(),
                content=[]
            )

            for i in range(splitter.count()):
                children = cls._get_struct_recursive(splitter.widget(i))
                out.content.append(children)
            return out
        elif isinstance(parent, QtAds.CDockAreaWidget):
            ads_dock_area = parent
            dock_area = SerializableDockArea(
                dock_widgets=[]
            )
            for j in range(ads_dock_area.dockWidgetsCount()):
                ads_dock_widget = ads_dock_area.dockWidget(j)
                scrutiny_component = cast(ScrutinyGUIBaseComponent, ads_dock_widget.widget())
                dock_widget = SerializableDockWidget(
                    current_tab = ads_dock_widget.isCurrentTab(),
                    component=SerializableComponent(
                        title=ads_dock_widget.tabWidget().text(),
                        type_id=scrutiny_component.get_type_id(),
                        state=scrutiny_component.get_state()
                    )
                )
                dock_area.dock_widgets.append(dock_widget)
            return dock_area
        raise NotImplementedError("Unsupported widget type inside dock manager")


    @classmethod
    def content_from_dock_manager(cls, dock_manager:QtAds.CDockManager) -> bytes:
        root_splitter = cls._get_struct_recursive(dock_manager.rootSplitter())
        assert isinstance(root_splitter, SerializableSplitter)

        dashboard_struct = SerializableDashboard(
            root_splitter=root_splitter,
            file_version=1,
            scrutiny_version=scrutiny.__version__,
            metadata={
                'created_on' : datetime.now().astimezone().strftime(r'%Y-%m-%d %H:%M:%S')
            }
        )
        dashboard_json = json.dumps(dashboard_struct.to_dict(), indent=4)
        return dashboard_json.encode('utf8')

    @classmethod
    def read_from_file(cls, f:"SupportsRead[bytes]") ->  SerializableDashboard:
        content = json.load(f)
        return SerializableDashboard.from_dict(content)
        
