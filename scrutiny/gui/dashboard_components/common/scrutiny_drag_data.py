__all__ = [
    'SerializableWatchableElement',
    'ScrutinyDragData',
    'SingleWatchableDescriptor'
]

import enum
import json
from dataclasses import dataclass

from PySide6.QtCore import QMimeData, QByteArray
from scrutiny.core import validation
from typing import Any, Optional, TypedDict, cast

class SerializableWatchableElement(TypedDict):
    text:str
    fqn:str

@dataclass(frozen=True)
class ScrutinyDragData:
    class DataType(enum.Enum):
        WatchableTreeNodesTiedToIndex = 'watchable_tree_nodes_tied_to_index'
        WatchableTreeNodes = 'watchable_tree_nodes'
        SingleWatchable = 'single_watchable'

    type:DataType
    data_copy:Any = None
    data_move:Any = None

    def __post_init__(self) -> None:
        validation.assert_type(self.type, 'type', (self.DataType))
         
    def to_mime(self) -> Optional[QMimeData]:
        d = {
             'type' : self.type.value,
             'data_copy' : self.data_copy,
             'data_move' : self.data_move
        }

        try:
             s = json.dumps(d)
        except Exception:
             return None

        data = QMimeData()
        data.setData('application/json', QByteArray.fromStdString(s))
        return data
    
    @classmethod
    def from_mime(cls, data:QMimeData) -> Optional["ScrutinyDragData"]:
        if not data.hasFormat('application/json'):
            return None
        s = QByteArray(data.data('application/json')).toStdString()
            
        try:
            d = json.loads(s)
        except Exception:
            return None
        
        try:
            return ScrutinyDragData(
                type = ScrutinyDragData.DataType(d['type']), 
                data_copy = d['data_copy'],
                data_move = d['data_move']
                )
        except Exception:
            return None

@dataclass
class SingleWatchableDescriptor:
    text:str
    fqn:str

    def to_serializable(self) -> SerializableWatchableElement:
        return  {
            'text' : self.text,
            'fqn':self.fqn
        }

    def to_drag_data(self, data_move:Optional[Any] = None) -> ScrutinyDragData:
        return ScrutinyDragData(
            type = ScrutinyDragData.DataType.SingleWatchable,
            data_copy=self.to_serializable(),
            data_move=data_move
        )
    
    def to_mime(self) -> QMimeData:
        mime_data = self.to_drag_data().to_mime()
        assert mime_data is not None
        return mime_data

    @classmethod
    def from_serializable(cls, data:SerializableWatchableElement) -> Optional["SingleWatchableDescriptor"]:
        if not isinstance(data, dict):
            return None
        
        if 'text' not in data or 'fqn' not in data:
            return  None

        text = data['text']
        fqn = data['fqn']
        if not isinstance(text, str) or not isinstance(fqn, str):
            return None
        
        return SingleWatchableDescriptor(
            text = text,
            fqn=fqn
        )

    @classmethod
    def from_drag_data(cls, data:ScrutinyDragData) -> Optional["SingleWatchableDescriptor"]:
        if data.type != ScrutinyDragData.DataType.SingleWatchable:
            return None
        
        return cls.from_serializable(cast(SerializableWatchableElement, data.data_copy))
        
    
    @classmethod
    def from_mime(cls, data:QMimeData) -> Optional["SingleWatchableDescriptor"]:
        drag_data = ScrutinyDragData.from_mime(data)
        if drag_data is None:
            return None
        return cls.from_drag_data(drag_data)
