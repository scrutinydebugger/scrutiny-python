#    watchable_tree.py
#        An enhanced QTreeView with a data model dedicated to Watchables displayed in folder
#        structure.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = [
    'get_watchable_icon',
    'NodeSerializableData',
    'WatchableItemSerializableData',
    'FolderItemSerializableData',
    'BaseWatchableRegistryTreeStandardItem',
    'FolderStandardItem',
    'WatchableStandardItem',
    'item_from_serializable_data',
    'WatchableTreeModel',
    'WatchableTreeWidget'
]

from scrutiny.sdk import WatchableType, WatchableConfiguration
from PySide6.QtGui import  QFocusEvent, QMouseEvent, QStandardItem, QIcon, QKeyEvent, QStandardItemModel, QColor
from PySide6.QtCore import Qt, QModelIndex, QPersistentModelIndex
from PySide6.QtWidgets import QTreeView, QWidget
from scrutiny.gui import assets
from scrutiny.gui.core.watchable_registry import WatchableRegistry, WatchableRegistryNodeContent
from scrutiny.gui.core.scrutiny_drag_data import WatchableListDescriptor, SingleWatchableDescriptor, ScrutinyDragData
from typing import Any, List, Optional, TypedDict,  cast, Literal, Sequence, Set, Iterable, Union


def get_watchable_icon(wt:WatchableType) -> QIcon:
    """Return the proper tree icon for a given watchable type (car, alias, rpv)"""
    if wt == WatchableType.Variable:
        return assets.load_icon(assets.Icons.TreeVar)
    if wt == WatchableType.Alias:
        return assets.load_icon(assets.Icons.TreeAlias)
    if wt == WatchableType.RuntimePublishedValue:
        return assets.load_icon(assets.Icons.TreeRpv)
    raise NotImplementedError(f"Unsupported icon for {wt}")

NodeSerializableType = Literal['watchable', 'folder']
class NodeSerializableData(TypedDict):
    """A serializable dict that represent a tree node"""
    type:NodeSerializableType
    text: str
    fqn:Optional[str]
    

class WatchableItemSerializableData(NodeSerializableData):
    """A serializable dict that represent a Watchable tree node (leaf node)"""
    pass

class FolderItemSerializableData(NodeSerializableData):
    """A serializable dict that represent a Folder tree node"""
    pass


class BaseWatchableRegistryTreeStandardItem(QStandardItem):
    """An extension of QT QStandardItem meant to represent either a folder or a watchable
    
    :param fqn: An optional Fully Qualified Name that point to the relevant element in the Watchable Registry
    
    """
    _fqn:Optional[str]
    _loaded:bool

    def __init__(self, fqn:Optional[str], *args:Any, **kwargs:Any):
        self._fqn = fqn
        self._loaded = False
        super().__init__(*args, **kwargs)

    def to_serialized_data(self) -> NodeSerializableData:
        raise NotImplementedError(f"Cannot serialize node of type {self.__class__.__name__}")

    def set_loaded(self) -> None:
        """Mark this node as loaded. USed for (lazy loading)"""
        self._loaded = True
    
    def is_loaded(self) -> bool:
        """Tells if this node has been loaded (lazy loading)"""
        return self._loaded

    @property
    def fqn(self) -> Optional[str]:
        """Returns the WatchableRegistry Fully Qualified Name if available"""
        return self._fqn


class FolderStandardItem(BaseWatchableRegistryTreeStandardItem):
    """A tree model QStandardItem that represent a folder
    
    :param text: The text to display in the view
    :param fqn: An optional Fully Qualified Name that point to the relevant element in the Watchable Registry
    
    """
    _NODE_TYPE:NodeSerializableType='folder'
      # fqn is optional for folders. They might be created by the user

    def __init__(self, text:str, fqn:Optional[str]=None):
        folder_icon = assets.load_icon(assets.Icons.TreeFolder)
        super().__init__(fqn, folder_icon, text)
        self.setDropEnabled(True)
    
    def to_serialized_data(self) -> FolderItemSerializableData:
        """Create a serializable version of this node (using a dict). Used for Drag&Drop"""
        return {
            'type' : self._NODE_TYPE,
            'text' : self.text(),
            'fqn' : self._fqn
        }

    @classmethod
    def from_serializable_data(cls, data:FolderItemSerializableData) -> "FolderStandardItem":
        """Loads from a serializable dict. Used for Drag&Drop"""
        assert data['type'] == cls._NODE_TYPE
        return FolderStandardItem(
            text=data['text'],
            fqn=data['fqn']
        )

class WatchableStandardItem(BaseWatchableRegistryTreeStandardItem):
    """A tree model QStandardItem that represent a watchable (leaf node)
    
    :param watchable_type: The type of watchable
    :param text: The text to display in the view
    :param fqn: An optional Fully Qualified Name that point to the relevant element in the Watchable Registry
    
    """
    _NODE_TYPE:NodeSerializableType='watchable'

    def __init__(self, watchable_type:WatchableType, text:str, fqn:str):
        icon = get_watchable_icon(watchable_type)
        super().__init__(fqn, icon, text)
        self.setDropEnabled(False)

    @property
    def fqn(self) -> str:
        """Returns the WatchableRegistry Fully Qualified Name"""
        assert self._fqn is not None
        return self._fqn
    
    def to_serialized_data(self) -> WatchableItemSerializableData:
        """Create a serializable version of this node (using a dict). Used for Drag&Drop"""
        return {
            'type' : self._NODE_TYPE,
            'text' : self.text(),
            'fqn' : self.fqn
        }

    @classmethod
    def from_serializable_data(cls, data:WatchableItemSerializableData) -> "WatchableStandardItem":
        """Loads from a serializable dict. Used for Drag&Drop"""
        assert data['type'] == cls._NODE_TYPE
        assert data['fqn'] is not None
        prased = WatchableRegistry.parse_fqn(data['fqn'])
        
        return WatchableStandardItem(
            watchable_type=prased.watchable_type,
            text=data['text'], 
            fqn=data['fqn']
        ) 

def item_from_serializable_data(data:NodeSerializableData) -> BaseWatchableRegistryTreeStandardItem:
    if data['type'] == FolderStandardItem._NODE_TYPE:
        return FolderStandardItem.from_serializable_data(cast(FolderItemSerializableData, data))
    if data['type'] == WatchableStandardItem._NODE_TYPE:
        return WatchableStandardItem.from_serializable_data(cast(WatchableItemSerializableData, data))
    
    raise NotImplementedError(f"Cannot create an item from serializable data of type {data['type']}")

class WatchableTreeModel(QStandardItemModel):
    """Extension of the QT Standard Item Model to represent watchables in a tree. The generic model is specialized to get :
     - Automatic icon choice
     - Leaf nodes that cannot accept children
     - Autofill from the global watchable registry (with possible lazy loading)
    
    :param parent: The parent 
    :param watchable_registry: A reference to the WatchableRegistry object to feed from

    """
    _watchable_registry:WatchableRegistry

    def __init__(self, parent:Optional[QWidget], watchable_registry:WatchableRegistry) -> None:
        super().__init__(parent)
        self._watchable_registry = watchable_registry

    def get_watchable_columns(self,  watchable_config:Optional[WatchableConfiguration] = None) -> List[QStandardItem]:
        return []

    @classmethod
    def make_watchable_row_from_existing_item(cls,
                        item:WatchableStandardItem,
                        editable:bool, 
                        extra_columns:List[QStandardItem]=[]) -> List[QStandardItem]:
        """Makes a watchable row, i.e. a leaf node in the tree, from an already created first column

        :param item: The first column item
        :param editable: Makes the row editable by the user through the GUI
        :param extra_columns: Columns to add next to the first column

        :return: the list of items in the row
        """
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
        """Makes a watchable row, i.e. a leaf node in the tree

        :param name: The name displayed in the GUI
        :param watchable_type: The watchable type. Define the icon
        :param fqn: The path to the item in the :class:`WatchableRegistry<scrutiny.gui.core.watchable_registry.WatchableRegistry>`
        :param editable: Makes the row editable by the user through the GUI
        :param extra_columns: Columns to add next to the first column

        :return: the list of items in the row
        """
        item =  WatchableStandardItem(watchable_type, name, fqn)
        return cls.make_watchable_row_from_existing_item(item, editable, extra_columns)

        
    @classmethod
    def make_folder_row_existing_item(cls, item:FolderStandardItem, editable:bool) -> List[QStandardItem]:
        """Creates a folder row from an already existing first column
        
        :item: The first column item
        :editable: Makes the row editable by the user through the GUI
        """
        item.setEditable(editable)
        item.setDragEnabled(True)
        return [item]

    @classmethod
    def make_folder_row(cls,  name:str, fqn:Optional[str], editable:bool ) -> List[QStandardItem]:
        """Creates a folder row
        
        :param name: The name displayed in the GUI
        :param fqn: The path to the item in the :class:`WatchableRegistry<scrutiny.gui.core.watchable_registry.WatchableRegistry>`
        :editable: Makes the row editable by the user through the GUI
        """
        item =  FolderStandardItem(name, fqn)
        return cls.make_folder_row_existing_item(item, editable)
    
    def add_row_to_parent(self, parent:Optional[QStandardItem], row_index:int, row:Sequence[QStandardItem] ) -> None:
        """Add a row to a given parent or at the root if no parent is given
        
        :param parent: The parent of the row to be inserted or ``None`` if the row must be added at the root
        :param row_index: The index of the new row. -1 to append
        :param row: The list of Items that act as a row
        
        """
        row2 = list(row)    # Make a copy
        while len(row2) > 0 and row2[-1] is None:
            row2 = row2[:-1]  # insert row doesn't like trailing None, but sometime does. Mystery

        if parent is not None:
            if row_index != -1:
                parent.insertRow(row_index, row2)
            else:
                parent.appendRow(row2)
        else:
            if row_index != -1:
                self.insertRow(row_index, row2)
            else:
                self.appendRow(row2)
    
    def add_multiple_rows_to_parent(self, parent:Optional[QStandardItem], row_index:int, rows:Sequence[Sequence[QStandardItem]] ) -> None:
        """Add multiple rows to a given parent or at the root if no parent is given
        
        :param parent: The parent of the row to be inserted or ``None`` if the row must be added at the root
        :param row_index: The index of the new row. -1 to append
        :param rows: The list of rows
        
        """
        for row in rows:
            self.add_row_to_parent(parent, row_index, row)
            if row_index != -1:
                row_index += 1
    
    def moveRow(self, 
                source_parent_index: Union[QModelIndex, QPersistentModelIndex], 
                sourceRow: int, 
                destination_parent_index: Union[QModelIndex, QPersistentModelIndex], 
                destinationChild: int) -> bool:
        """Move a row from source to destination
        
        :param source_parent_index: An index pointing to the parent node. Invalid index if root
        :param sourceRow: The row index of the source under the parent
        :param destination_parent_index: An index pointing to the destination parent node. Invalid index if root
        :param destinationChild: The row number to insert the row under the new parent. -1 to append
        
        :return: ``True`` on success
        """


        destination_parent:Optional[QStandardItem] = None
        if destination_parent_index.isValid():
            destination_parent = self.itemFromIndex(destination_parent_index)  # get the item before we take a row, it can change it's position

        if source_parent_index == destination_parent_index:
            if destinationChild > sourceRow:
                destinationChild-=1

        row: Optional[List[QStandardItem]] = None
        if source_parent_index.isValid():
            if sourceRow >= 0:
                row = self.itemFromIndex(source_parent_index).takeRow(sourceRow)
        else:
            if sourceRow >= 0:
                row = self.takeRow(sourceRow)
                
        if row is not None:
            self.add_row_to_parent(destination_parent, destinationChild, row)
       
        return True

    def lazy_load(self, parent:BaseWatchableRegistryTreeStandardItem, watchable_type:WatchableType, path:str) -> None:
        """Lazy load a everything under a parent based on the content of the watchable registry
        
        :param parent: The parent containing the nodes to be loaded
        :param watchable_type: The type of watchable to query to WatchableRegistry
        :param path: The WatchableRegistry path
        
        """
        self.fill_from_index_recursive(parent, watchable_type, path, max_level=0)

    def fill_from_index_recursive(self, 
                                  parent:BaseWatchableRegistryTreeStandardItem, 
                                  watchable_type:WatchableType, 
                                  path:str,
                                  max_level:Optional[int]=None,
                                  keep_folder_fqn:bool=True,
                                  editable:bool=False,
                                  level:int=0
                                  ) -> None:
        """Fill the data model from folders and watchable based on the content of the WatchableRegistry
        
        :param parent: The node to fill
        :param watchable_type: The type of watchable of the parent to query the WatchableRegistry
        :param path: The WatchableRegistry path mapping to the parent.
        :param max_level: The maximum number of nested children. ``None`` for no limit
        :param keep_folder_fqn: Indicate if the Fully Qualified Name taken from  WatchableRegistry should be assigned to folder nodes created
        :param editable: Makes the new nodes editable by the GUI
        :param level: internal aprameter to keep track of recursion. The user should leave to default
        """
        parent.set_loaded()
        content = self._watchable_registry.read(watchable_type, path)
        if path.endswith('/'):
            path=path[:-1]

        if isinstance(content, WatchableRegistryNodeContent):  # Equivalent to a folder
            for name in content.subtree:
                subtree_path = f'{path}/{name}'
                folder_fqn:Optional[str] = None
                if keep_folder_fqn:
                    folder_fqn = self._watchable_registry.make_fqn(watchable_type, subtree_path)
                row = self.make_folder_row(
                    name=name,
                    fqn=folder_fqn,
                    editable=editable
                )
                parent.appendRow(row)

                if max_level is None or level < max_level:
                    self.fill_from_index_recursive(
                        parent = cast(BaseWatchableRegistryTreeStandardItem, row[0]), 
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
                    fqn = self._watchable_registry.make_fqn(watchable_type, watchable_path), 
                    editable=editable,
                    extra_columns=self.get_watchable_columns(watchable_config)
                )
                parent.appendRow(row)

    def remove_nested_indexes(self, indexes:Sequence[QModelIndex], columns_to_keep:List[int]=[0]) -> Set[QModelIndex]:
        """Takes a list of indexes and remove any indexes nested under another index part of the input
        
        :param indexes: The list of indexes to filter
        :param columns_to_keep: A list of column number to keep. Generally wants to leave at 0 since we put children only on column 0
        
        :return: A set of indexes that has no nested indexes
        """
        indexes_without_nested_values = set([index for index in indexes if index.column() in columns_to_keep])
        # If we have nested nodes, we only keep the parent.
        for index in list(indexes_without_nested_values):   # Make copy
            parent = index.parent()
            while parent.isValid():
                if parent in indexes_without_nested_values:
                    indexes_without_nested_values.remove(index)
                    break
                parent = parent.parent()
        
        return indexes_without_nested_values

    def make_watchable_list_dragdata_if_possible(self, 
                                             items:Iterable[Optional[BaseWatchableRegistryTreeStandardItem]],
                                             data_move:Optional[Any] = None
                                             ) -> Optional[ScrutinyDragData]:
        """Converts a list of tree nodes to a ScrutinyDragData that contains a list of watchable
        only if the given indexes points to watchables (leaf) nodes only. Return ``None`` if any of the element is not a watchable node
        
        :param items: The items to scan and embed in the drag data
        :param data_move: Additional data to attach to the ScrutinyDragData

        :return: A ScrutinyDragData containing the watchable list or ``None`` if any of the index pointed to something else than a watchable node
        
        """
        watchables_only = True
        for item in items:
            if item is None or not isinstance(item, WatchableStandardItem):
                watchables_only = False
                break

        if watchables_only:
            watchable_items = cast(List[WatchableStandardItem], items)
            return WatchableListDescriptor(
                data = [SingleWatchableDescriptor(text=item.text(), fqn=item.fqn) for item in watchable_items]
            ).to_drag_data(data_move=data_move)
        return None

class WatchableTreeWidget(QTreeView):
    """An extension of the QTreeView dedicated to display a tree of folders and watchables (leaf) nodes.
    
    :param parent: The parent
    :param model: The model to use. A WatchableTreeModel is required.
    """
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
        """Some convenient behavior. Ctrl to multiselect. Shift to select a range"""
        if event.key() == Qt.Key.Key_Control:
            self.setSelectionMode(self.SelectionMode.MultiSelection)
        elif event.key() == Qt.Key.Key_Shift:
            self.setSelectionMode(self.SelectionMode.ContiguousSelection)
        elif event.key() == Qt.Key.Key_Escape:
            self.clearSelection()
        else:
            return super().keyPressEvent(event)
    
    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Some convenient behavior. Ctrl to multiselect. Shift to select a range"""
        if event.key() == Qt.Key.Key_Control:
            if self.selectionMode() == self.SelectionMode.MultiSelection:
                self.setSelectionMode(self.SelectionMode.SingleSelection)
        elif event.key() == Qt.Key.Key_Shift:
            if self.selectionMode() == self.SelectionMode.ContiguousSelection:
                self.setSelectionMode(self.SelectionMode.SingleSelection)
        else:
            return super().keyReleaseEvent(event)
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            # This condition prevents to change the selection on a right click if it happens on an existing selection
            # Makes it easier to right click a multi-selection (no need to hold shift or control)
            index = self.indexAt(event.pos())
            if index.isValid() and index in self.selectedIndexes():
                return  # Don't change the selection
        return super().mousePressEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        # Needs to do that, other wise holding ctrl/shift and cliking outside of the tree will not detect the key release
        self.setSelectionMode(self.SelectionMode.SingleSelection)
        return super().focusOutEvent(event)
    
    def model(self) -> WatchableTreeModel:
        return self._model
    
    def set_row_color(self, index:QModelIndex, color:QColor) -> None:
        """Change the background color of a row"""
        item = self._model.itemFromIndex(index)
        for i in range(self._model.columnCount()):
            item = self._model.itemFromIndex(index.siblingAtColumn(i))
            if item is not None:
                item.setBackground(color)
        

    def is_visible(self, item:BaseWatchableRegistryTreeStandardItem) -> bool:
        """Tells if a node is visible, i.e. all parents are expanded.
        
        :item: The node to check
        :return: ``True`` if visible. ``False`` otherwise
        """

        visible = True
        parent = item.parent()
        while parent is not None:
            if isinstance(parent, FolderStandardItem) and not self.isExpanded(parent.index()):
                visible = False
            parent = parent.parent()
        return visible
