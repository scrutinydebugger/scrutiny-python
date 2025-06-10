#    scrutiny_drag_data.py
#        Application-wide drag&drop data format. Used to drag watchables items around
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = [
    'SerializableWatchableElement',
    'ScrutinyDragData',
    'SingleWatchableDescriptor',
    'WatchableListDescriptor'
]

import enum
import json
from dataclasses import dataclass

from PySide6.QtCore import QMimeData, QByteArray
from scrutiny.tools import validation
from scrutiny.tools.typing import *


@dataclass(frozen=True)
class ScrutinyDragData:
    """Represent data being dragged when doing a drag&drop"""
    class DataType(enum.Enum):
        WatchableTreeNodesTiedToRegistry = 'watchable_tree_nodes_tied_to_index'
        WatchableFullTree = 'watchable_full_tree'
        WatchableList = 'watchable_list'

    type: DataType
    """The type of data being carried"""
    data_copy: Any = None
    """Data for copy action"""
    data_move: Any = None
    """Data for move action"""

    def __post_init__(self) -> None:
        validation.assert_type(self.type, 'type', (self.DataType))

    def to_mime(self) -> Optional[QMimeData]:
        """Converts the drag data object to QMimeData supported by QT

        :return: Mime data if valid. ``None`` otherwise
        """
        d = {
            'type': self.type.value,
            'data_copy': self.data_copy,
            'data_move': self.data_move
        }

        try:
            s = json.dumps(d)
        except Exception:
            return None

        data = QMimeData()
        data.setData('application/json', QByteArray.fromStdString(s))
        return data

    @classmethod
    def from_mime(cls, data: QMimeData) -> Optional["ScrutinyDragData"]:
        """Creates drag data object from QMimeData supported by QT

        :return: The DragData object data if valid. ``None`` otherwise
        """
        if not isinstance(data, QMimeData):
            return None

        if not data.hasFormat('application/json'):
            return None
        s = QByteArray(data.data('application/json')).toStdString()

        try:
            d = json.loads(s)
        except Exception:
            return None

        try:
            return ScrutinyDragData(
                type=ScrutinyDragData.DataType(d['type']),
                data_copy=d['data_copy'],
                data_move=d['data_move']
            )
        except Exception:
            return None


class SerializableWatchableElement(TypedDict):
    """Representation of a single watchable element through a serializable dict"""
    text: str
    fqn: str


@dataclass(frozen=True)
class SingleWatchableDescriptor:
    """Non-serializable description of a single Watchable element"""

    text: str
    fqn: str

    def to_serializable(self) -> SerializableWatchableElement:
        """Creates a serializable version of this descriptor using a dict"""
        return {
            'text': self.text,
            'fqn': self.fqn
        }

    @classmethod
    def from_serializable(cls, data: SerializableWatchableElement) -> Optional["SingleWatchableDescriptor"]:
        """Create an descriptor object from a serializable dict created by ``to_serializable()``"""
        if not isinstance(data, dict):
            return None

        if 'text' not in data or 'fqn' not in data:
            return None

        text = data['text']
        fqn = data['fqn']
        if not isinstance(text, str) or not isinstance(fqn, str):
            return None

        return SingleWatchableDescriptor(
            text=text,
            fqn=fqn
        )


@dataclass
class WatchableListDescriptor:
    """A non serializable object containing a list of :class:`SingleWatchableDescriptor<SingleWatchableDescriptor>`"""

    data: List[SingleWatchableDescriptor]
    """The list of watchable descriptors"""

    def to_serializable(self) -> List[SerializableWatchableElement]:
        """Create a serialized version of this object using a list of dict"""
        return [x.to_serializable() for x in self.data]

    def to_drag_data(self, data_move: Optional[Any] = None) -> ScrutinyDragData:
        """Create a :class:`ScrutinyDragData` object that contains a serializaed version of this data"""

        return ScrutinyDragData(
            type=ScrutinyDragData.DataType.WatchableList,
            data_copy=self.to_serializable(),
            data_move=data_move
        )

    def to_mime(self, data_move: Optional[Any] = None) -> QMimeData:
        """Converts this list of watchables to a QMimeData that encodes it in a serialized version. Used for drag&drop """
        mime_data = self.to_drag_data(data_move).to_mime()
        assert mime_data is not None
        return mime_data

    @classmethod
    def from_serializable(cls, data: List[SerializableWatchableElement]) -> Optional["WatchableListDescriptor"]:
        """Creates an descriptor object from a serializable dict created by ``to_serializable()``"""
        if not isinstance(data, list):
            return None
        deserialized_data: List[SingleWatchableDescriptor] = []
        for x in data:
            deserialized = SingleWatchableDescriptor.from_serializable(x)
            if deserialized is None:
                return None
            deserialized_data.append(deserialized)

        return WatchableListDescriptor(data=deserialized_data)

    @classmethod
    def from_drag_data(cls, data: ScrutinyDragData) -> Optional["WatchableListDescriptor"]:
        """Creates an descriptor object from a ScrutinyDragData received after a drop event"""
        if not isinstance(data, ScrutinyDragData):
            return None

        if data.type != ScrutinyDragData.DataType.WatchableList:
            return None

        return cls.from_serializable(cast(List[SerializableWatchableElement], data.data_copy))

    @classmethod
    def from_mime(cls, data: QMimeData) -> Optional["WatchableListDescriptor"]:
        """Creates an descriptor object from a QMimeData received after a drop event"""
        drag_data = ScrutinyDragData.from_mime(data)
        if drag_data is None:
            return None
        return cls.from_drag_data(drag_data)
