__all__ = [
    'get_watchable_icon',
    'NodeSerializableData',
    'WatchableItemSerializableData',
    'FolderItemSerializableData',
    'BaseWatchableIndexTreeStandardItem',
    'FolderStandardItem',
    'WatchableStandardItem',
    'item_from_serializable_data',
    'WatchableTreeModel',
    'WatchableTreeWidget'
]

from scrutiny.sdk import WatchableType, WatchableConfiguration
from PySide6.QtGui import  QFocusEvent, QStandardItem, QIcon, QKeyEvent, QStandardItemModel, QColor
from PySide6.QtCore import Qt, QModelIndex, QByteArray, QMimeData, QPersistentModelIndex
from PySide6.QtWidgets import QTreeView, QWidget
from scrutiny.gui import assets
from scrutiny.gui.core.watchable_index import WatchableIndex, WatchableIndexNodeContent
from scrutiny.core import validation
from typing import Any, List, Optional, TypedDict,  cast, Literal, Dict, Union, Sequence, Set
from dataclasses import dataclass
import enum
import json

def get_watchable_icon(wt:WatchableType) -> QIcon:
    if wt == WatchableType.Variable:
        return assets.load_icon(assets.Icons.TreeVar)
    if wt == WatchableType.Alias:
        return assets.load_icon(assets.Icons.TreeAlias)
    if wt == WatchableType.RuntimePublishedValue:
        return assets.load_icon(assets.Icons.TreeRpv)
    raise NotImplementedError(f"Unsupported icon for {wt}")

NodeSerializableType = Literal['watchable', 'folder']
class NodeSerializableData(TypedDict):
    type:NodeSerializableType
    display_text: str
    fqn:Optional[str]
    

class WatchableItemSerializableData(NodeSerializableData):
    pass

class FolderItemSerializableData(NodeSerializableData):
    pass


@dataclass(frozen=True)
class TreeDragData:
    class DataType(enum.Enum):
        WatchableTreeNodesTiedToIndex = 'watchable_tree_nodes_tied_to_index'
        WatchableTreeNodes = 'watchable_tree_nodes'

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
    def from_mime(cls, data:QMimeData) -> Optional["TreeDragData"]:
        if not data.hasFormat('application/json'):
            return None
        s = QByteArray(data.data('application/json')).toStdString()
            
        try:
            d = json.loads(s)
        except Exception:
            return None
        
        try:
            return TreeDragData(
                type = TreeDragData.DataType(d['type']), 
                data_copy = d['data_copy'],
                data_move = d['data_move']
                )
        except Exception:
            return None


class BaseWatchableIndexTreeStandardItem(QStandardItem):
    _fqn:Optional[str]
    _loaded:bool

    def __init__(self, fqn:Optional[str], *args:Any, **kwargs:Any):
        self._fqn = fqn
        self._loaded = False
        super().__init__(*args, **kwargs)

    def to_serialized_data(self) -> NodeSerializableData:
        raise NotImplementedError(f"Cannot serialize node of type {self.__class__.__name__}")

    def set_loaded(self) -> None:
        self._loaded = True
    
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def fqn(self) -> Optional[str]:
        return self._fqn


class FolderStandardItem(BaseWatchableIndexTreeStandardItem):
    _NODE_TYPE:NodeSerializableType='folder'
      # fqn is optional for folders. They might be created by the user

    def __init__(self, text:str, fqn:Optional[str]=None):
        folder_icon = assets.load_icon(assets.Icons.TreeFolder)
        super().__init__(fqn, folder_icon, text)
    
    def to_serialized_data(self) -> FolderItemSerializableData:
        return {
            'type' : self._NODE_TYPE,
            'display_text' : self.text(),
            'fqn' : self._fqn
        }

    @classmethod
    def from_serializable_data(cls, data:FolderItemSerializableData) -> "FolderStandardItem":
        assert data['type'] == cls._NODE_TYPE
        return FolderStandardItem(
            text=data['display_text'],
            fqn=data['fqn']
        )
    


class WatchableStandardItem(BaseWatchableIndexTreeStandardItem):
    _NODE_TYPE:NodeSerializableType='watchable'

    def __init__(self, watchable_type:WatchableType, text:str, fqn:str):
        icon = get_watchable_icon(watchable_type)
        super().__init__(fqn, icon, text)

    @property
    def fqn(self) -> str:
        assert self._fqn is not None
        return self._fqn
    
    def to_serialized_data(self) -> WatchableItemSerializableData:
        return {
            'type' : self._NODE_TYPE,
            'display_text' : self.text(),
            'fqn' : self.fqn
        }

    @classmethod
    def from_serializable_data(cls, data:WatchableItemSerializableData) -> "WatchableStandardItem":
        assert data['type'] == cls._NODE_TYPE
        assert data['fqn'] is not None
        prased = WatchableIndex.parse_fqn(data['fqn'])
        
        return WatchableStandardItem(
            watchable_type=prased.watchable_type,
            text=data['display_text'], 
            fqn=data['fqn']
        ) 

def item_from_serializable_data(data:NodeSerializableData) -> BaseWatchableIndexTreeStandardItem:
    if data['type'] == FolderStandardItem._NODE_TYPE:
        return FolderStandardItem.from_serializable_data(cast(FolderItemSerializableData, data))
    if data['type'] == WatchableStandardItem._NODE_TYPE:
        return WatchableStandardItem.from_serializable_data(cast(WatchableItemSerializableData, data))
    
    raise NotImplementedError(f"Cannot create an item from serializable data of type {data['type']}")

class WatchableTreeModel(QStandardItemModel):
    """Extension of the Standard Item Model to represent watchables in a tree. The generic model is specialized to get :
     - Automatic icon choice
     - Leaf nodes that cannot accept children
     - Autofill from the global watchable index (with possible lazy loading)
    
    """
    _watchable_index:WatchableIndex

    def __init__(self, parent:Optional[QWidget], watchable_index:WatchableIndex) -> None:
        super().__init__(parent)
        self._watchable_index = watchable_index

    def get_watchable_columns(self,  watchable_config:Optional[WatchableConfiguration] = None) -> List[QStandardItem]:
        return []

    @classmethod
    def make_watchable_row_from_existing_item(cls,
                        item:WatchableStandardItem,
                        editable:bool, 
                        extra_columns:List[QStandardItem]=[]) -> List[QStandardItem]:
        item.setEditable(editable)
        item.setDragEnabled(True)
        for col in extra_columns:
            col.setDragEnabled(True)
        return [item] + extra_columns

    @classmethod
    def make_watchable_row(cls, 
                        name:str, 
                        watchable_type:WatchableType, 
                        fqn:str, 
                        editable:bool, 
                        extra_columns:List[QStandardItem]=[]) -> List[QStandardItem]:
        
        item =  WatchableStandardItem(watchable_type, name, fqn)
        return cls.make_watchable_row_from_existing_item(item, editable, extra_columns)

        
    @classmethod
    def make_folder_row_existing_item(cls, item:FolderStandardItem, editable:bool) -> List[QStandardItem]:
        item.setEditable(editable)
        item.setDragEnabled(True)
        return [item]

    @classmethod
    def make_folder_row(cls,  name:str, fqn:Optional[str], editable:bool ) -> List[QStandardItem]:
        item =  FolderStandardItem(name, fqn)
        return cls.make_folder_row_existing_item(item, editable)
    
    def add_row(self, index:Union[QModelIndex, QPersistentModelIndex], row_index:int, row_content:List[QStandardItem]) -> None:
        if index.isValid():
            parent_item = self.itemFromIndex(index)
            if row_index == -1:
                parent_item.appendRow(row_content)
            else:
                parent_item.insertRow(row_index, row_content)
        else:
            if row_index == -1:
                self.appendRow(row_content)
            else:
                self.insertRow(row_index, row_content)

    def lazy_load(self, parent:BaseWatchableIndexTreeStandardItem, watchable_type:WatchableType, path:str) -> None:
        self.fill_from_index_recursive(parent, watchable_type, path, max_level=0)

    def fill_from_index_recursive(self, 
                                  parent:BaseWatchableIndexTreeStandardItem, 
                                  watchable_type:WatchableType, 
                                  path:str,
                                  max_level:Optional[int]=None,
                                  keep_folder_fqn:bool=True,
                                  editable:bool=False,
                                  level:int=0
                                  ) -> None:
        parent.set_loaded()
        content = self._watchable_index.read(watchable_type, path)
        if path.endswith('/'):
            path=path[:-1]

        if isinstance(content, WatchableIndexNodeContent):  # Equivalent to a folder
            for name in content.subtree:
                subtree_path = f'{path}/{name}'
                folder_fqn:Optional[str] = None
                if keep_folder_fqn:
                    folder_fqn = self._watchable_index.make_fqn(watchable_type, subtree_path)
                row = self.make_folder_row(
                    name=name,
                    fqn=folder_fqn,
                    editable=editable
                )
                parent.appendRow(row)

                if max_level is None or level < max_level:
                    self.fill_from_index_recursive(
                        parent = cast(BaseWatchableIndexTreeStandardItem, row[0]), 
                        watchable_type=watchable_type, 
                        path=subtree_path,
                        editable=editable, 
                        max_level=max_level,
                        keep_folder_fqn=keep_folder_fqn,
                        level=level+1)
            
            for name, watchable_config in content.watchables.items():
                watchable_path = f'{path}/{name}'
                row = self.make_watchable_row(
                    name = name, 
                    watchable_type = watchable_config.watchable_type, 
                    fqn = self._watchable_index.make_fqn(watchable_type, watchable_path), 
                    editable=editable,
                    extra_columns=self.get_watchable_columns(watchable_config)
                )
                parent.appendRow(row)

    def remove_nested_indexes(self, indexes:Sequence[QModelIndex], columns_to_keep:List[int]=[0]) -> Set[QModelIndex]:
        indexes_without_nested_values = set([index for index in indexes if index.column() in columns_to_keep])
        # If we have nested nodes, we only keep the parent.
        for index in indexes:
            parent = index.parent()
            while parent.isValid():
                if parent in indexes_without_nested_values:
                    indexes_without_nested_values.remove(index)
                    break
                parent = parent.parent()
        
        return indexes_without_nested_values

class WatchableTreeWidget(QTreeView):
    _model:WatchableTreeModel

    DEFAULT_ITEM0_WIDTH = 400
    DEFAULT_ITEM_WIDTH = 100

    def __init__(self, parent:QWidget, model:WatchableTreeModel) -> None:
        super().__init__(parent)
        self._model = model

        self.setModel(self._model)
        self.setUniformRowHeights(True)   # Documentation says it helps performance
        self.setAnimated(False)
        self.header().setStretchLastSection(False)
    
    def set_header_labels(self, headers:List[str]) -> None:
        self._model.setColumnCount(len(headers))
        self._model.setHorizontalHeaderLabels(headers)
    
    def expand_first_column_to_content(self) -> None:
        """Resize the first column to content if it makes it grow."""
        header = self.header()
        original_sizes = [header.sectionSize(i) for i in range(self._model.columnCount())]
        header.resizeSections(header.ResizeMode.ResizeToContents)

        if header.sectionSize(0) < original_sizes[0]:
            header.resizeSection(0, original_sizes[0])

        for i in range(1, len(original_sizes)):
            header.resizeSection(i, original_sizes[i])

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Control:
            self.setSelectionMode(self.SelectionMode.MultiSelection)
        elif event.key() == Qt.Key.Key_Shift:
            self.setSelectionMode(self.SelectionMode.ContiguousSelection)
        elif event.key() == Qt.Key.Key_Escape:
            self.clearSelection()
        else:
            return super().keyPressEvent(event)
    
    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Control:
            if self.selectionMode() == self.SelectionMode.MultiSelection:
                self.setSelectionMode(self.SelectionMode.SingleSelection)
        elif event.key() == Qt.Key.Key_Shift:
            if self.selectionMode() == self.SelectionMode.ContiguousSelection:
                self.setSelectionMode(self.SelectionMode.SingleSelection)
        else:
            return super().keyReleaseEvent(event)
    
    def focusOutEvent(self, event: QFocusEvent) -> None:
        self.setSelectionMode(self.SelectionMode.SingleSelection)
        return super().focusOutEvent(event)
    
    def get_model(self) -> WatchableTreeModel:
        return self._model
    
    def set_row_color(self, index:QModelIndex, color:QColor) -> None:
        item = self._model.itemFromIndex(index)
        for i in range(self._model.columnCount()):
            item = self._model.itemFromIndex(index.siblingAtColumn(i))
            if item is not None:
                item.setBackground(color)
        
