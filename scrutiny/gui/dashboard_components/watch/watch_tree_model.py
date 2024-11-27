__all__ = ['WatchComponentTreeModel']

import logging

from PySide6.QtCore import QMimeData, QModelIndex, QPersistentModelIndex, Qt, QModelIndex
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QStandardItem

from scrutiny.gui.core.watchable_index import WatchableIndex
from scrutiny.gui.dashboard_components.common.watchable_tree import (
    WatchableTreeModel, 
    NodeSerializableData, 
    FolderStandardItem,
    WatchableStandardItem,
    BaseWatchableIndexTreeStandardItem,
    TreeDragData,
    item_from_serializable_data
)
from typing import List, Union, Optional, cast, Sequence, TypedDict, Generator, Iterable

class SerializableItemIndexDescriptor(TypedDict):
    path:List[int]
    object_id:int

class SerializableTreeDescriptor(TypedDict):
    node:NodeSerializableData
    children:List["SerializableTreeDescriptor"]


class WatchComponentTreeModel(WatchableTreeModel):
    """An extension of the data model used by Watchable Trees dedicated for the Watch Component
    Mainly handles drag&drop logic
    """
    logger:logging.Logger

    def __init__(self, parent: Optional[QWidget], watchable_index: WatchableIndex) -> None:
        super().__init__(parent, watchable_index)
        self._dragged_item_list = None
        self.logger = logging.getLogger(self.__class__.__name__)

    def _check_support_drag_data(self, drag_data:Optional[TreeDragData], action:Qt.DropAction) -> bool:
        if drag_data is None:
            return False
        
        # Deny unsupported data type 
        if drag_data.type == TreeDragData.DataType.WatchableTreeNodes:
            if action not in [ Qt.DropAction.MoveAction, Qt.DropAction.CopyAction ]:
                return False
        elif drag_data.type == TreeDragData.DataType.WatchableTreeNodesTiedToIndex:
            if action not in [ Qt.DropAction.CopyAction ]:
                return False
        else:
            return False
        
        # Make sure we have data for the right action
        if action == Qt.DropAction.MoveAction:
            if drag_data.data_move is None:
                return False
        elif action == Qt.DropAction.CopyAction:
            if drag_data.data_copy is None:
                return False
        
        return True
    
        
    def _make_serializable_item_index_descriptor(self, item:Optional[BaseWatchableIndexTreeStandardItem]) -> SerializableItemIndexDescriptor:
        if item is None:
            return {
                'path' : [],
                'object_id' : 0
            }
        path_list:List[int] = [item.row()]
        index = item.index()
        while index.parent().isValid():
            path_list.insert(0, index.parent().row())
            index = index.parent()
        return {
            'path' : path_list,
            'object_id' : id(item)
        }
    
    def _make_serializable_tree_descriptor(self, top_level_item:BaseWatchableIndexTreeStandardItem) -> SerializableTreeDescriptor:
        assert top_level_item is not None
       
        dict_out : SerializableTreeDescriptor = {
            'node' : top_level_item.to_serialized_data(),
            'children' : []
        }

        for row_index in range(top_level_item.rowCount()):
            child = cast(BaseWatchableIndexTreeStandardItem, top_level_item.child(row_index, 0))
            dict_out['children'].append(self._make_serializable_tree_descriptor(child))

        return dict_out

    
    def _get_item_from_serializable_index_descriptor(self, data:SerializableItemIndexDescriptor) -> Optional[BaseWatchableIndexTreeStandardItem]:
        assert 'path' in data
        assert 'object_id' in data
        path  = data['path']
        object_id = data['object_id']
        if len(path) == 0 or object_id == 0:
            return None
        item = cast(BaseWatchableIndexTreeStandardItem, self.item(path[0], 0))
        if item is None:
            return None
        for row_index in path[1:]:
            item = cast(BaseWatchableIndexTreeStandardItem, item.child(row_index, 0))
            if item is None:
                return None
        if id(item) != object_id:
            return None
        return item

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        
        def get_items(indexes:Iterable[QModelIndex]) -> Generator[BaseWatchableIndexTreeStandardItem, None, None]:
            for index in indexes:
                if index.column() == 0:
                    yield cast(BaseWatchableIndexTreeStandardItem, self.itemFromIndex(index))
        
        serializable_item_descriptors = [self._make_serializable_item_index_descriptor(item) for item in get_items(indexes)]
        top_level_indexes = self.remove_nested_indexes(indexes)
        serializable_tree_descriptors = [self._make_serializable_tree_descriptor(item) for item in get_items(top_level_indexes)]

        drag_data = TreeDragData(
            type=TreeDragData.DataType.WatchableTreeNodes, 
            data_copy= serializable_tree_descriptors,
            data_move = serializable_item_descriptors )
        mime_data = drag_data.to_mime()
        assert mime_data is not None

        return mime_data

    def canDropMimeData(self, 
                        mime_data: QMimeData, 
                        action: Qt.DropAction, 
                        row_index: int, 
                        column_index: int, 
                        parent: Union[QModelIndex, QPersistentModelIndex]
                        ) -> bool:
        drag_data = TreeDragData.from_mime(mime_data)
        
        if not self._check_support_drag_data(drag_data, action):
            return False
        assert drag_data is not None
        
        # We do not allow dropping on watchables (leaf nodes)
        if parent.isValid() :
            if not isinstance(self.itemFromIndex(parent), FolderStandardItem):
                return False
        return True

    def dropMimeData(self, 
                     mime_data: QMimeData, 
                     action: Qt.DropAction, 
                     row_index: int, 
                     column_index: int, 
                     parent: Union[QModelIndex, QPersistentModelIndex]
                     ) -> bool:

        # We can only drop on root or on a folder
        if parent.isValid():
            if not isinstance(self.itemFromIndex(parent), FolderStandardItem):
                return False
        
        drag_data = TreeDragData.from_mime(mime_data)
        if not self._check_support_drag_data(drag_data, action):
            return False
        assert drag_data is not None

        if drag_data.type == TreeDragData.DataType.WatchableTreeNodesTiedToIndex:
            if action == Qt.DropAction.CopyAction:
                self.logger.debug(f"Drop: Varlist data with {len(drag_data.data_copy)} nodes")
                return self.handle_drop_varlist_copy(parent, row_index, cast(List[NodeSerializableData], drag_data.data_copy))
            else:
                return False

        elif drag_data.type == TreeDragData.DataType.WatchableTreeNodes:
            if action == Qt.DropAction.MoveAction:
                self.logger.debug(f"Drop: Watch internal move with {len(drag_data.data_move)} nodes")
                return self.handle_internal_move(parent, row_index, cast(List[SerializableItemIndexDescriptor], drag_data.data_move))
            elif action == Qt.DropAction.CopyAction:
                self.logger.debug(f"Drop: Watch external copy with {len(drag_data.data_copy)} nodes")
                self.handle_tree_drop(parent, row_index, cast(List[SerializableTreeDescriptor], drag_data.data_copy))
            else:
                return False
            
        return False
        


    def handle_drop_varlist_copy(self, 
                            parent_index: Union[QModelIndex, QPersistentModelIndex],
                            row_index:int,
                            data:List[NodeSerializableData]) -> bool:
        try:
            assert isinstance(data, list)
            for node in data:
                assert 'type' in node
                assert 'display_text' in node
                assert 'fqn' in node
                assert node['fqn'] is not None  # Varlist component guarantees a FQN
                parsed_fqn = self._watchable_index.parse_fqn(node['fqn'])

                if node['type'] == 'folder':
                    folder_row = self.make_folder_row(node['display_text'], fqn=None, editable=True)
                    first_col = cast(BaseWatchableIndexTreeStandardItem, folder_row[0])
                    self.add_row(parent_index, row_index, folder_row)
                    self.fill_from_index_recursive(first_col, parsed_fqn.watchable_type, parsed_fqn.path, keep_folder_fqn=False, editable=True) 
                    
                elif node['type'] == 'watchable':
                    watchable_row = self.make_watchable_row(node['display_text'], watchable_type=parsed_fqn.watchable_type, fqn=node['fqn'], editable=True)
                    self.add_row(parent_index, row_index, watchable_row)
                else:
                    pass    # Silently ignore
        except AssertionError:
            return False
        
        return True

    def moveRow(self, 
                sourceParent: Union[QModelIndex, QPersistentModelIndex], 
                sourceRow: int, 
                destinationParent: Union[QModelIndex, QPersistentModelIndex], 
                destinationChild: int) -> bool:
        
        destination_parent:Optional[QStandardItem] = None
        if destinationParent.isValid():
            destination_parent = self.itemFromIndex(destinationParent)  # get the item before we take a row, it can change it's position

        row: Optional[List[QStandardItem]] = None
        if sourceParent.isValid():
            if sourceRow >= 0:
                row = self.itemFromIndex(sourceParent).takeRow(sourceRow)
        else:
            if sourceRow >= 0:
                row = self.takeRow(sourceRow)
        
        if row is not None:
            if destination_parent is not None:
                if destinationChild == -1:
                    destination_parent.appendRow(row)
                else:
                    destination_parent.insertRow(destinationChild, row)
            else:
                if destinationChild == -1:
                    self.appendRow(row)
                else:
                    self.insertRow(destinationChild, row)
        return True

    def handle_internal_move(self,
                            dest_parent_index: Union[QModelIndex, QPersistentModelIndex],
                            dest_row_index:int,
                            data:List[SerializableItemIndexDescriptor]) -> bool:
        try:
            items = [self._get_item_from_serializable_index_descriptor(descriptor) for descriptor in data]
            for item in items:
                if item is not None:
                    source_parent_index = QModelIndex()
                    if item.parent():
                        source_parent_index = item.parent().index()
                    self.moveRow(
                        source_parent_index,
                        item.row(),
                        dest_parent_index,
                        dest_row_index
                    )
                else:
                    self.logger.error("Item to be moved cannot be found. Ignoring")

        except AssertionError:
            return False
        return True
    
    def handle_tree_drop(self,
                        dest_parent_index: Union[QModelIndex, QPersistentModelIndex],
                        dest_row_index:int,
                        data:List[SerializableTreeDescriptor]) -> bool:
        
        def fill_from_tree_recursive( 
                                  parent:Optional[BaseWatchableIndexTreeStandardItem],
                                  row_index:int, 
                                  descriptor:SerializableTreeDescriptor 
                                  ) -> None:
            assert 'node' in descriptor
            assert 'children' in descriptor

            if parent is not None:
                parent.set_loaded()
            item = item_from_serializable_data(descriptor['node'])
            if isinstance(item, FolderStandardItem):
                row = self.make_folder_row_existing_item(item, editable=True)
            elif isinstance(item, WatchableStandardItem):
                row = self.make_watchable_row_from_existing_item(item, editable=True, extra_columns=self.get_watchable_columns())
            else:
                raise NotImplementedError("Unsupported item type")
            
            if parent is not None:
                if row_index != -1:
                    parent.insertRow(row_index, row)
                else:
                    parent.appendRow(row)
            else:
                if row_index != -1:
                    self.insertRow(row_index, row)
                else:
                    self.appendRow(row)

            for child in descriptor['children']:
                fill_from_tree_recursive(
                    parent = item,
                    row_index=-1,
                    descriptor=child
                )
        
        try:
            for descriptor in data:
                if dest_parent_index.isValid():
                    dest_parent_item = cast(BaseWatchableIndexTreeStandardItem, self.itemFromIndex(dest_parent_index))
                    fill_from_tree_recursive(dest_parent_item, dest_row_index, descriptor)
                else:
                    fill_from_tree_recursive(None, dest_row_index, descriptor)
                
                if dest_row_index != -1:
                    dest_row_index+=1
        except AssertionError:
            return False
        return True

                

        
