#    dashboard_file_format.py
#        Definitions of the serialized data representing a dashboard written into files when
#        saving
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = [
    'SerializableComponent',
    'SerializableDockWidget',
    'SerializableDockArea',
    'SidebarLocation',
    'SerializableSideBarComponent',
    'SplitterOrientation',
    'SerializableSplitter',
    'SerializableContainer',
    'SerializableWindow',
    'SerializableDashboard',
    'serialize_container',
    'serialize_floating_container'
]

from dataclasses import dataclass
import enum

import PySide6QtAds as QtAds
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter

from scrutiny.gui.components.base_component import ScrutinyGUIBaseComponent
from scrutiny.tools import validation
from scrutiny.tools.typing import *


@dataclass
class SerializableComponent:
    TYPE = 'component'

    title: str
    type_id: str
    state: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.TYPE,
            'title': self.title,
            'type_id': self.type_id,
            'state': self.state
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Self:
        validation.assert_dict_key(d, 'type', str)
        validation.assert_dict_key(d, 'title', str)
        validation.assert_dict_key(d, 'type_id', str)
        validation.assert_dict_key(d, 'state', dict)

        if d['type'] != cls.TYPE:
            raise ValueError(f"Expected node of type {cls.TYPE}, got {d['type']}")

        return cls(
            title=d['title'],
            type_id=d['type_id'],
            state=d['state']
        )

    def __post_init__(self) -> None:
        assert isinstance(self.title, str)
        assert isinstance(self.type_id, str)
        assert isinstance(self.state, dict)


@dataclass
class SerializableDockWidget:
    TYPE = 'dock_widget'

    current_tab: bool
    component: SerializableComponent

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.TYPE,
            'current_tab': self.current_tab,
            'component': self.component.to_dict()
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Self:
        validation.assert_dict_key(d, 'type', str)
        validation.assert_dict_key(d, 'current_tab', bool)
        validation.assert_dict_key(d, 'component', dict)

        if d['type'] != cls.TYPE:
            raise ValueError(f"Expected node of type {cls.TYPE}, got {d['type']}")

        return cls(
            current_tab=d['current_tab'],
            component=SerializableComponent.from_dict(d['component'])
        )

    def __post_init__(self) -> None:
        assert isinstance(self.current_tab, bool)
        assert isinstance(self.component, SerializableComponent)


@dataclass
class SerializableDockArea:
    TYPE = 'dock_area'
    dock_widgets: List[SerializableDockWidget]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.TYPE,
            'dock_widgets': [dw.to_dict() for dw in self.dock_widgets]
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Self:
        validation.assert_dict_key(d, 'type', str)
        validation.assert_dict_key(d, 'dock_widgets', list)
        if d['type'] != cls.TYPE:
            raise ValueError(f"Expected node of type {cls.TYPE}, got {d['type']}")

        dock_widgets: List[SerializableDockWidget] = []
        for element in d['dock_widgets']:
            validation.assert_type(element, 'dock_area.dock_widgets[...]', dict)
            validation.assert_dict_key(element, 'type', str)

            dock_widgets.append(SerializableDockWidget.from_dict(element))

        return cls(
            dock_widgets=dock_widgets
        )

    def __post_init__(self) -> None:
        assert isinstance(self.dock_widgets, list)
        for dw in self.dock_widgets:
            assert isinstance(dw, SerializableDockWidget)


class SidebarLocation(enum.Enum):
    TOP = 'top'
    LEFT = 'left'
    RIGHT = 'right'
    BOTTOM = 'bottom'

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_str(cls, v: str) -> "SidebarLocation":
        return cls(v)

    @classmethod
    def from_ads(cls, v: QtAds.ads.SideBarLocation) -> "SidebarLocation":
        lookup = {
            QtAds.SideBarLeft: cls.LEFT,
            QtAds.SideBarTop: cls.TOP,
            QtAds.SideBarBottom: cls.BOTTOM,
            QtAds.SideBarRight: cls.RIGHT,
        }

        return lookup[v]

    def to_ads(self) -> QtAds.ads.SideBarLocation:
        lookup = {
            self.__class__.LEFT.value: QtAds.SideBarLeft,
            self.__class__.TOP.value: QtAds.SideBarTop,
            self.__class__.BOTTOM.value: QtAds.SideBarBottom,
            self.__class__.RIGHT.value: QtAds.SideBarRight,
        }
        return lookup[self.value]

    def is_left_right(self) -> bool:
        return self.value in (self.__class__.LEFT.value, self.__class__.RIGHT.value)

    def is_top_bottom(self) -> bool:
        return self.value in (self.__class__.TOP.value, self.__class__.BOTTOM.value)


@dataclass
class SerializableSideBarComponent:
    TYPE = 'sidebar_component'
    sidebar_location: SidebarLocation
    component: SerializableComponent
    size: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.TYPE,
            'sidebar_location': str(self.sidebar_location),
            'component': self.component.to_dict(),
            'size': self.size
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Self:
        validation.assert_dict_key(d, 'type', str)
        validation.assert_dict_key(d, 'sidebar_location', str)
        validation.assert_dict_key(d, 'component', dict)
        validation.assert_dict_key(d, 'size', int)

        if d['type'] != cls.TYPE:
            raise ValueError(f"Expected node of type {cls.TYPE}, got {d['type']}")

        return cls(
            sidebar_location=SidebarLocation.from_str(d['sidebar_location']),
            component=SerializableComponent.from_dict(d['component']),
            size=d['size']
        )

    def __post_init__(self) -> None:
        assert isinstance(self.sidebar_location, SidebarLocation)
        assert isinstance(self.component, SerializableComponent)
        assert isinstance(self.size, int)


class SplitterOrientation(enum.Enum):
    VERTICAL = 'vertical'
    HORIZONTAL = 'horizontal'

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_str(cls, v: str) -> "SplitterOrientation":
        return cls(v)

    @classmethod
    def from_qt(cls, v: Qt.Orientation) -> "SplitterOrientation":
        lookup = {
            Qt.Orientation.Vertical: cls.VERTICAL,
            Qt.Orientation.Horizontal: cls.HORIZONTAL,
        }

        return lookup[v]


@dataclass
class SerializableSplitter:
    TYPE = 'splitter'

    orientation: SplitterOrientation
    sizes: List[int]
    content: List[Union["SerializableSplitter", "SerializableDockArea"]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.TYPE,
            'orientation': str(self.orientation),
            'sizes': self.sizes,
            'content': [elem.to_dict() for elem in self.content]
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Self:
        validation.assert_dict_key(d, 'type', str)
        validation.assert_dict_key(d, 'orientation', str)
        validation.assert_dict_key(d, 'sizes', list)
        validation.assert_dict_key(d, 'content', list)

        for v in d['sizes']:
            validation.assert_type(v, 'd["sizes"][...]', int)

        if d['type'] != cls.TYPE:
            raise ValueError(f"Expected node of type {cls.TYPE}, got {d['type']}")

        content: List[Union[SerializableDockArea, SerializableSplitter]] = []
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
            orientation=SplitterOrientation.from_str(d['orientation']),
            sizes=d['sizes'],
            content=content
        )

    def __post_init__(self) -> None:
        assert isinstance(self.orientation, SplitterOrientation)
        assert isinstance(self.sizes, list)
        for v in self.sizes:
            assert isinstance(v, int)

        assert isinstance(self.content, list)
        for element in self.content:
            assert isinstance(element, (SerializableSplitter, SerializableDockArea))


@dataclass
class SerializableContainer:
    TYPE = 'container'
    root_splitter: SerializableSplitter
    sidebar_components: List[SerializableSideBarComponent]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.TYPE,
            'root_splitter': self.root_splitter.to_dict(),
            'sidebar_components': [sb_comp.to_dict() for sb_comp in self.sidebar_components]
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Self:
        validation.assert_dict_key(d, 'type', str)
        validation.assert_dict_key(d, 'root_splitter', dict)
        validation.assert_dict_key(d, 'sidebar_components', list)
        for x in d['sidebar_components']:
            validation.assert_type(x, 'container["sidebar_components"][N]', dict)

        if d['type'] != cls.TYPE:
            raise ValueError(f"Expected node of type {cls.TYPE}, got {d['type']}")

        return cls(
            root_splitter=SerializableSplitter.from_dict(d['root_splitter']),
            sidebar_components=[SerializableSideBarComponent.from_dict(x) for x in d['sidebar_components']]
        )

    def __post_init__(self) -> None:
        assert isinstance(self.root_splitter, SerializableSplitter)
        assert isinstance(self.sidebar_components, list)
        for x in self.sidebar_components:
            assert isinstance(x, SerializableSideBarComponent)


@dataclass
class SerializableWindow:
    TYPE = 'window'

    container: SerializableContainer
    width: int
    height: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.TYPE,
            'container': self.container.to_dict(),
            'width': self.width,
            'height': self.height
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Self:
        validation.assert_dict_key(d, 'type', str)
        validation.assert_dict_key(d, 'container', dict)
        validation.assert_dict_key(d, 'width', int)
        validation.assert_dict_key(d, 'height', int)

        if d['type'] != cls.TYPE:
            raise ValueError(f"Expected node of type {cls.TYPE}, got {d['type']}")

        return cls(
            container=SerializableContainer.from_dict(d['container']),
            width=d['width'],
            height=d['height']
        )

    def __post_init__(self) -> None:
        assert isinstance(self.container, SerializableContainer)
        assert isinstance(self.width, int)
        assert isinstance(self.height, int)


@dataclass
class SerializableDashboard:
    TYPE = 'dashboard'

    main_container: SerializableContainer
    windows: List[SerializableWindow]
    metadata: Dict[str, str]
    file_version: int
    scrutiny_version: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.TYPE,
            'main_container': self.main_container.to_dict(),
            'windows': [win.to_dict() for win in self.windows],
            'file_version': self.file_version,
            'scrutiny_version': self.scrutiny_version,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Self:
        validation.assert_dict_key(d, 'type', str)
        validation.assert_dict_key(d, 'main_container', dict)
        validation.assert_dict_key(d, 'windows', list)
        for x in d['windows']:
            validation.assert_type(x, 'container["windows"][...]', dict)
        validation.assert_dict_key(d, 'file_version', int)
        validation.assert_dict_key(d, 'scrutiny_version', (str, float))

        if d['file_version'] != 1:
            raise ValueError("Expect file version : v1")

        if d['type'] != cls.TYPE:
            raise ValueError(f"Expected node of type {cls.TYPE}, got {d['type']}")

        return cls(
            main_container=SerializableContainer.from_dict(d['main_container']),
            windows=[SerializableWindow.from_dict(x) for x in d['windows']],
            file_version=d['file_version'],
            metadata=d.get('metadata', {}),
            scrutiny_version=str(d['scrutiny_version'])
        )

    def __post_init__(self) -> None:
        assert isinstance(self.main_container, SerializableContainer)
        assert isinstance(self.windows, list)
        for win in self.windows:
            assert isinstance(win, SerializableWindow)
        assert isinstance(self.metadata, dict)
        assert isinstance(self.file_version, int)
        assert isinstance(self.scrutiny_version, str)


def _get_sidebar_components_from_container(container: QtAds.CDockContainerWidget) -> List[SerializableSideBarComponent]:
    outlist: List[SerializableSideBarComponent] = []
    for ads_autohide_container in container.autoHideWidgets():
        ads_dock_widget = ads_autohide_container.dockWidget()
        scrutiny_component = cast(ScrutinyGUIBaseComponent, ads_dock_widget.widget())
        sidebar_location = SidebarLocation.from_ads(ads_autohide_container.sideBarLocation())

        size_hw = ads_dock_widget.dockAreaWidget().size()
        size = size_hw.width() if sidebar_location.is_left_right() else size_hw.height()
        sidebar_component = SerializableSideBarComponent(
            sidebar_location=sidebar_location,
            component=SerializableComponent(
                title=ads_dock_widget.tabWidget().text(),
                type_id=scrutiny_component.get_type_id(),
                state=scrutiny_component.get_state()
            ),
            size=size
        )

        outlist.append(sidebar_component)

    return outlist


def _get_container_splitter_recursive(parent: Union[QtAds.CDockSplitter, QtAds.CDockAreaWidget]) -> Union[SerializableSplitter, SerializableDockArea]:
    if isinstance(parent, QtAds.CDockSplitter):
        splitter = cast(QSplitter, parent)    # Better type hint
        out = SerializableSplitter(
            orientation=SplitterOrientation.from_qt(splitter.orientation()),
            sizes=splitter.sizes(),
            content=[]
        )

        for i in range(splitter.count()):
            children = _get_container_splitter_recursive(cast(Union[QtAds.CDockSplitter, QtAds.CDockAreaWidget], splitter.widget(i)))
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
                current_tab=ads_dock_widget.isCurrentTab(),
                component=SerializableComponent(
                    title=ads_dock_widget.tabWidget().text(),
                    type_id=scrutiny_component.get_type_id(),
                    state=scrutiny_component.get_state()
                )
            )
            dock_area.dock_widgets.append(dock_widget)
        return dock_area
    raise NotImplementedError("Unsupported widget type inside dock manager")


def serialize_container(dock_container: QtAds.CDockContainerWidget) -> SerializableContainer:
    return SerializableContainer(
        root_splitter=cast(SerializableSplitter, _get_container_splitter_recursive(dock_container.rootSplitter())),     # type: ignore
        sidebar_components=_get_sidebar_components_from_container(dock_container)
    )


def serialize_floating_container(floating_dock_container: QtAds.CFloatingDockContainer) -> SerializableWindow:
    return SerializableWindow(
        container=serialize_container(floating_dock_container.dockContainer()),
        height=floating_dock_container.size().height(),
        width=floating_dock_container.size().width()
    )
