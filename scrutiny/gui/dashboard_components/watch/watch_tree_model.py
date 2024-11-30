__all__ = ['WatchComponentTreeModel']

import logging
import functools

from PySide6.QtCore import QMimeData, QModelIndex, QPersistentModelIndex, Qt, QModelIndex
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QStandardItem

from scrutiny.gui.dashboard_components.common.scrutiny_drag_data import ScrutinyDragData, SingleWatchableDescriptor
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.gui.dashboard_components.common.watchable_tree import (
    WatchableTreeModel, 
    NodeSerializableData, 
    FolderStandardItem,
    WatchableStandardItem,
    BaseWatchableRegistryTreeStandardItem,
    item_from_serializable_data
)

from typing import List, Union, Optional, cast, Sequence, TypedDict, Generator, Iterable

class SerializableItemIndexDescriptor(TypedDict):
    path:List[int]
    object_id:int

class SerializableTreeDescriptor(TypedDict):
    node:NodeSerializableData
    sortkey:int
    children:List["SerializableTreeDescriptor"]


class WatchComponentTreeModel(WatchableTreeModel):
    """An extension of the data model used by Watchable Trees dedicated for the Watch Component
    Mainly handles drag&drop logic
    """
    logger:logging.Logger

    def __init__(self, parent: Optional[QWidget], watchable_registry: WatchableRegistry) -> None:
        super().__init__(parent, watchable_registry)
        self._dragged_item_list = None
        self.logger = logging.getLogger(self.__class__.__name__)

    def _check_support_drag_data(self, drag_data:Optional[ScrutinyDragData], action:Qt.DropAction) -> bool:
        if drag_data is None:
            return False
        
        # Deny unsupported data type 
        if drag_data.type == ScrutinyDragData.DataType.WatchableTreeNodes:
            if action not in [ Qt.DropAction.MoveAction, Qt.DropAction.CopyAction ]:
                return False
        elif drag_data.type == ScrutinyDragData.DataType.WatchableTreeNodesTiedToIndex:
            if action not in [ Qt.DropAction.CopyAction ]:
                return False
        elif drag_data.type == ScrutinyDragData.DataType.SingleWatchable:
            if action not in [Qt.DropAction.MoveAction, Qt.DropAction.CopyAction ]:
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
    
    def _make_path_list(self, item:QStandardItem) -> List[int]:
        path_list:List[int] = [item.row()]
        index = item.index()
        while index.parent().isValid():
            path_list.insert(0, index.parent().row())
            index = index.parent()
        return path_list
        
    def _make_serializable_item_index_descriptor(self, item:Optional[BaseWatchableRegistryTreeStandardItem]) -> SerializableItemIndexDescriptor:
        if item is None:
            return {
                'path' : [],
                'object_id' : 0
            }

        return {
            'path' : self._make_path_list(item),
            'object_id' : id(item)
        }
    
    def sort_items_by_path(self, items:List[BaseWatchableRegistryTreeStandardItem], top_to_bottom:bool=True) -> None:
        mult = 1 if top_to_bottom else -1
        def sort_compare(item1:QStandardItem, item2:QStandardItem) -> int:
            path1 = self._make_path_list(item1)
            path2 = self._make_path_list(item2)
            len1 = len(path1)
            len2 = len(path2)
            if len1 < len2:
                return -1 * mult
            elif len1 > len2:
                return 1 * mult
            else:
                for i in range(len1):
                    if path1[i] < path2[i]:
                        return -1
                    elif path1[i] > path2[i]:
                        return 1
                return 0
             
        items.sort(key=functools.cmp_to_key(sort_compare))
    
    def _make_serializable_tree_descriptor(self, top_level_item:BaseWatchableRegistryTreeStandardItem, sortkey:int=0) -> SerializableTreeDescriptor:
        assert top_level_item is not None
       
        dict_out : SerializableTreeDescriptor = {
            'node' : top_level_item.to_serialized_data(),
            'sortkey' : sortkey,
            'children' : []
        }

        for row_index in range(top_level_item.rowCount()):
            child = cast(BaseWatchableRegistryTreeStandardItem, top_level_item.child(row_index, 0))
            dict_out['children'].append(self._make_serializable_tree_descriptor(child, sortkey=row_index))

        return dict_out

    
    def _get_item_from_serializable_index_descriptor(self, data:SerializableItemIndexDescriptor) -> Optional[BaseWatchableRegistryTreeStandardItem]:
        assert 'path' in data
        assert 'object_id' in data
        path  = data['path']
        object_id = data['object_id']
        if len(path) == 0 or object_id == 0:
            return None
        item = cast(BaseWatchableRegistryTreeStandardItem, self.item(path[0], 0))
        if item is None:
            return None
        for row_index in path[1:]:
            item = cast(BaseWatchableRegistryTreeStandardItem, item.child(row_index, 0))
            if item is None:
                return None
        if id(item) != object_id:
            return None
        return item

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        
        def get_items(indexes:Iterable[QModelIndex]) -> Generator[BaseWatchableRegistryTreeStandardItem, None, None]:
            for index in indexes:
                if index.column() == 0:
                    yield cast(BaseWatchableRegistryTreeStandardItem, self.itemFromIndex(index))

        top_level_items = [item for item in get_items(self.remove_nested_indexes(indexes))]
        self.sort_items_by_path(top_level_items, top_to_bottom=True)
        move_data = [self._make_serializable_item_index_descriptor(item) for item in top_level_items]
        
        drag_data:Optional[ScrutinyDragData] = None

        # First check if we can encode as a single Watchable because this is the most widely supported format
        items_col0 = [item for item in get_items(indexes)]
        if len(items_col0) == 1:
            single_item = items_col0[0]
            if single_item is not None:
                if isinstance(single_item, WatchableStandardItem):
                    drag_data = SingleWatchableDescriptor(
                        text=single_item.text(), 
                        fqn=single_item.fqn
                        ).to_drag_data(data_move=move_data)

        
        # We have a tree or many elements, propagate as such
        if drag_data is None:
            serializable_tree_descriptors:List[SerializableTreeDescriptor] = []
            for i in range(len(top_level_items)):
                item = top_level_items[i]
                serializable_tree_descriptors.append(self._make_serializable_tree_descriptor(item, sortkey=i))

            drag_data = ScrutinyDragData(
                type=ScrutinyDragData.DataType.WatchableTreeNodes, 
                data_copy= serializable_tree_descriptors,
                data_move = move_data 
            )
        
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
        drag_data = ScrutinyDragData.from_mime(mime_data)
        
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
        
        drag_data = ScrutinyDragData.from_mime(mime_data)
        if not self._check_support_drag_data(drag_data, action):
            return False
        assert drag_data is not None

        log_prefix = f"Drop [{drag_data.type.name}]"
        if drag_data.type == ScrutinyDragData.DataType.WatchableTreeNodesTiedToIndex:
            if action == Qt.DropAction.CopyAction:
                self.logger.debug(f"{log_prefix}: Varlist data with {len(drag_data.data_copy)} nodes")
                return self.handle_drop_varlist_copy(parent, row_index, cast(List[NodeSerializableData], drag_data.data_copy))
            else:
                return False

        elif drag_data.type == ScrutinyDragData.DataType.WatchableTreeNodes:
            if action == Qt.DropAction.MoveAction:
                self.logger.debug(f"{log_prefix}: Watch internal move with {len(drag_data.data_move)} nodes")
                return self.handle_internal_move(parent, row_index, cast(List[SerializableItemIndexDescriptor], drag_data.data_move))
            elif action == Qt.DropAction.CopyAction:
                self.logger.debug(f"{log_prefix}: Watch external copy with {len(drag_data.data_copy)} nodes")
                self.handle_tree_drop(parent, row_index, cast(List[SerializableTreeDescriptor], drag_data.data_copy))
            else:
                return False
            
        elif drag_data.type == ScrutinyDragData.DataType.SingleWatchable:
            if action == Qt.DropAction.MoveAction:
                self.logger.debug(f"{log_prefix}: Watch internal move with single element")
                return self.handle_internal_move(parent, row_index, cast(List[SerializableItemIndexDescriptor], drag_data.data_move))
            elif action == Qt.DropAction.CopyAction:
                self.logger.debug(f"{log_prefix}: Watch external copy with single element")
                single_element = SingleWatchableDescriptor.from_drag_data(drag_data)
                if single_element is None:
                    return False
                self.handle_single_element_drop(parent, row_index,  single_element)
            else:
                return False
            
        return False

    def handle_drop_varlist_copy(self, 
                            parent_index: Union[QModelIndex, QPersistentModelIndex],
                            row_index:int,
                            data:List[NodeSerializableData]) -> bool:
        """Handle a drop coming from a varlist component. The data is a list of nodes, no nesting. Each node has a Fully qualified Name that points
        to the watchable registry"""
        try:
            assert isinstance(data, list)
            for node in data:
                assert 'type' in node
                assert 'display_text' in node
                assert 'fqn' in node
                assert node['fqn'] is not None  # Varlist component guarantees a FQN
                parsed_fqn = self._watchable_registry.parse_fqn(node['fqn'])

                if node['type'] == 'folder':
                    folder_row = self.make_folder_row(node['display_text'], fqn=None, editable=True)
                    first_col = cast(BaseWatchableRegistryTreeStandardItem, folder_row[0])
                    self.add_row_to_parent(self.itemFromIndex(parent_index), row_index, folder_row)
                    self.fill_from_index_recursive(first_col, parsed_fqn.watchable_type, parsed_fqn.path, keep_folder_fqn=False, editable=True) 
                    
                elif node['type'] == 'watchable':
                    watchable_row = self.make_watchable_row(node['display_text'], watchable_type=parsed_fqn.watchable_type, fqn=node['fqn'], editable=True)
                    self.add_row_to_parent(self.itemFromIndex(parent_index), row_index, watchable_row)
                else:
                    pass    # Silently ignore
                
        except AssertionError:
            return False
        
        return True

    def moveRow(self, 
                source_parent_index: Union[QModelIndex, QPersistentModelIndex], 
                sourceRow: int, 
                destination_parent_index: Union[QModelIndex, QPersistentModelIndex], 
                destinationChild: int) -> bool:
        
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

    def handle_internal_move(self,
                            dest_parent_index: Union[QModelIndex, QPersistentModelIndex],
                            dest_row_index:int,
                            data:List[SerializableItemIndexDescriptor]) -> bool:
        try:
            items = [self._get_item_from_serializable_index_descriptor(descriptor) for descriptor in data]
            if dest_row_index > 0:
                if dest_parent_index.isValid():
                    previous_item = self.itemFromIndex(dest_parent_index).child(dest_row_index-1, 0)
                else:
                    previous_item = self.item(dest_row_index-1, 0)
            insert_offset = 0        
            for item in items:
                if item is not None:
                    source_parent_index = QModelIndex()
                    if item.parent():
                        source_parent_index = item.parent().index()
                    if dest_row_index == -1:
                        new_dest_row_index = -1
                    elif dest_row_index == 0:
                        new_dest_row_index = insert_offset
                    else:
                        new_dest_row_index = previous_item.row() + 1 + insert_offset
                    self.moveRow(
                        source_parent_index,
                        item.row(),
                        dest_parent_index,
                        new_dest_row_index
                    )
                    insert_offset+=1
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
                                  parent:Optional[BaseWatchableRegistryTreeStandardItem],
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
        
            self.add_row_to_parent(parent, row_index, row)

            for child in sorted(descriptor['children'], key=lambda x:x['sortkey']):
                fill_from_tree_recursive(
                    parent = item,
                    row_index=-1,   # Append. List is sorted
                    descriptor=child
                )
        
        try:
            for descriptor in data:
                if dest_parent_index.isValid():
                    dest_parent_item = cast(BaseWatchableRegistryTreeStandardItem, self.itemFromIndex(dest_parent_index))
                    fill_from_tree_recursive(dest_parent_item, dest_row_index, descriptor)
                else:
                    fill_from_tree_recursive(None, dest_row_index, descriptor)
                
                if dest_row_index != -1:
                    dest_row_index+=1
        except AssertionError:
            return False
        return True

                
    def handle_single_element_drop(self,
                        dest_parent_index: Union[QModelIndex, QPersistentModelIndex],
                        dest_row_index:int,
                        descriptor:SingleWatchableDescriptor) -> bool:
        
        dest_parent = self.itemFromIndex(dest_parent_index)
        watchable_type = WatchableRegistry.parse_fqn(descriptor.fqn).watchable_type
        row = self.make_watchable_row(
            watchable_type=watchable_type,
            name = descriptor.text,
            fqn=descriptor.fqn,
            editable=True,
            extra_columns=self.get_watchable_columns()
        )

        self.add_row_to_parent(dest_parent, dest_row_index, row)
        return True
