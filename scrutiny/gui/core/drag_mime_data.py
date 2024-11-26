import enum
from dataclasses import dataclass
from typing import Any, Literal, get_args, Optional
from scrutiny.core import validation

from PySide6.QtCore import QByteArray, QMimeData
import json


@dataclass(frozen=True)
class DragData:
    class DataType(enum.Enum):
        WatchableTreeNodesTiedToIndex = 'watchable_tree_nodes_tied_to_index'
        WatchableTreeNodes = 'watchable_tree_nodes'

    type:DataType
    data:Any

    def __post_init__(self):
        validation.assert_type(self.type, 'type', (self.DataType))
        if self.data is None:
             raise ValueError("Data is empty")
         
    def to_mime(self) -> Optional[QMimeData]:
        d = {
             'type' : self.type.value,
             'data' : self.data
        }

        try:
             s = json.dumps(d)
        except Exception:
             return None

        data = QMimeData()
        data.setData('text/plain', QByteArray.fromStdString(s))
        return data
    
    @classmethod
    def from_mime(cls, data:QMimeData) -> Optional["DragData"]:
        if not data.hasText():
            return None
        s = QByteArray(data.data('text/plain')).toStdString()
            
        try:
            d = json.loads(s)
        except Exception:
            return None
        
        try:
            return DragData(type=DragData.DataType(d['type']), data=d['data'])
        except Exception:
            return None
