#    scrutiny_drag_data.py
#        Application-wide drag&drop data format. Used to drag watcahbles items around
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

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
from scrutiny.core import validation
from typing import Any, Optional, TypedDict, cast, List

class SerializableWatchableElement(TypedDict):
    text:str
    fqn:str

@dataclass(frozen=True)
class ScrutinyDragData:
    class DataType(enum.Enum):
        WatchableTreeNodesTiedToRegistry = 'watchable_tree_nodes_tied_to_index'
        WatchableFullTree = 'watchable_full_tree'
        WatchableList = 'watchable_list'

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

@dataclass
class WatchableListDescriptor:
    data:List[SingleWatchableDescriptor]

    def to_serializable(self) -> List[SerializableWatchableElement]:
        return [x.to_serializable() for x in self.data]
    
    def to_drag_data(self, data_move:Optional[Any] = None) -> ScrutinyDragData:
        return ScrutinyDragData(
            type = ScrutinyDragData.DataType.WatchableList,
            data_copy=self.to_serializable(),
            data_move=data_move
        )
    
    def to_mime(self) -> QMimeData:
        mime_data = self.to_drag_data().to_mime()
        assert mime_data is not None
        return mime_data

    @classmethod
    def from_serializable(cls, data:List[SerializableWatchableElement]) -> Optional["WatchableListDescriptor"]:
        deserialized_data:List[SingleWatchableDescriptor] = []
        for x in data:
            deserialized = SingleWatchableDescriptor.from_serializable(x)
            if deserialized is None:
                return None
            deserialized_data.append(deserialized)

        return WatchableListDescriptor(data = deserialized_data)

    @classmethod
    def from_drag_data(cls, data:ScrutinyDragData) -> Optional["WatchableListDescriptor"]:
        if data.type != ScrutinyDragData.DataType.WatchableList:
            return None
        
        return cls.from_serializable(cast(List[SerializableWatchableElement], data.data_copy))
        
    
    @classmethod
    def from_mime(cls, data:QMimeData) -> Optional["WatchableListDescriptor"]:
        drag_data = ScrutinyDragData.from_mime(data)
        if drag_data is None:
            return None
        return cls.from_drag_data(drag_data)



