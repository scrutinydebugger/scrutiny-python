#    watch_tree_model.py
#        The data model used by the Watch component treeview
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['WatchComponentTreeModel', 'WatchComponentTreeWidget', 'ValueStandardItem']

import logging
import enum

from PySide6.QtCore import QMimeData, QModelIndex, QPersistentModelIndex, Qt,  Signal, QPoint, QObject
from PySide6.QtWidgets import QWidget, QMenu, QAbstractItemDelegate
from PySide6.QtGui import QStandardItem,QPalette, QContextMenuEvent, QDragMoveEvent, QDropEvent, QDragEnterEvent, QKeyEvent, QStandardItem, QAction

from scrutiny.sdk.definitions import WatchableConfiguration
from scrutiny.gui.core.scrutiny_drag_data import ScrutinyDragData, WatchableListDescriptor
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.gui.widgets.watchable_tree import (
    WatchableTreeWidget,
    WatchableTreeModel, 
    NodeSerializableData, 
    FolderStandardItem,
    WatchableStandardItem,
    BaseWatchableRegistryTreeStandardItem,
    item_from_serializable_data
)
from scrutiny.gui.widgets.base_tree import SerializableItemIndexDescriptor
from scrutiny.gui import assets
from scrutiny.tools.global_counters import global_i64_counter
from scrutiny.tools.typing import *


AVAILABLE_DATA_ROLE = Qt.ItemDataRole.UserRole+1
WATCHER_ID_ROLE = Qt.ItemDataRole.UserRole+2

class ValueStandardItem(QStandardItem):
    pass

class SerializableTreeDescriptor(TypedDict):
    """A serializable description of a node (not the path to it). Used to describe a tree when doing a copy"""
    node:NodeSerializableData
    sortkey:int
    children:List["SerializableTreeDescriptor"]


class WatchComponentTreeWidget(WatchableTreeWidget):
    NEW_FOLDER_DEFAULT_NAME = "New Folder"

    class _Signals(QObject):
        value_written = Signal(str, str)    # fqn, value

    signals:_Signals

    def __init__(self, parent: QWidget, model:"WatchComponentTreeModel") -> None:
        super().__init__(parent, model)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(self.DragDropMode.DragDrop)
        self.set_header_labels(['', 'Value'])
        self.signals = self._Signals()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        context_menu = QMenu(self)
        selected_indexes_no_nested = self.model().remove_nested_indexes(self.selectedIndexes())
        nesting_col = self.model().nesting_col()
        selected_items_no_nested = [self.model().itemFromIndex(index) for index in selected_indexes_no_nested if index.column()==nesting_col]

        parent, insert_row = self._find_new_folder_position_from_position(event.pos())
        
        def new_folder_action_slot() -> None:
            self._new_folder(self.NEW_FOLDER_DEFAULT_NAME, parent, insert_row)
        
        def remove_actionslot() -> None:
            for item in selected_items_no_nested:
                self.model().removeRow(item.row(), item.index().parent())
        
        new_folder_action = context_menu.addAction(assets.load_tiny_icon(assets.Icons.Folder), "New Folder")
        new_folder_action.triggered.connect(new_folder_action_slot)
        
        remove_action = context_menu.addAction(assets.load_tiny_icon(assets.Icons.RedX), "Remove")
        remove_action.setEnabled( len(selected_items_no_nested) > 0 )
        remove_action.triggered.connect(remove_actionslot)
        
        self.display_context_menu(context_menu, event.pos())
        event.accept()
        
    def display_context_menu(self, menu:QMenu, pos:QPoint) -> None:
        """Display a menu at given relative position, and make sure it goes below the cursor to mimic what most people are used to"""
        actions = menu.actions()
        at: Optional[QAction] = None
        if len(actions) > 0:
            pos += QPoint(0, menu.actionGeometry(actions[0]).height())
            at = actions[0]
        menu.popup(self.mapToGlobal(pos), at)
        
    def model(self) -> "WatchComponentTreeModel":
        return cast(WatchComponentTreeModel, super().model())

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            model = self.model()
            indexes_without_nested_values = model.remove_nested_indexes(self.selectedIndexes()) # Avoid errors when parent is deleted before children
            items = [model.itemFromIndex(index) for index in  indexes_without_nested_values]
            for item in items:
                if item is not None:
                    parent_index=QModelIndex() # Invalid index
                    if item.parent():
                        parent_index = item.parent().index()
                    model.removeRow(item.row(), parent_index)

        elif event.key() in [Qt.Key.Key_Enter, Qt.Key.Key_Return] and self.state() != self.State.EditingState:
            nesting_col = self.model().nesting_col()
            selected_index_nesting_col = [idx for idx in self.selectedIndexes() if idx.column() == nesting_col]
            if len(selected_index_nesting_col) == 1:
                model = self.model()
                item = model.itemFromIndex(selected_index_nesting_col[0])
                if isinstance(item,WatchableStandardItem):
                    value_item = model.get_value_item(item)
                    self.setCurrentIndex(value_item.index())
                    self.edit(value_item.index())
                    
        elif event.key() == Qt.Key.Key_N and event.modifiers() == Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier:
            parent, insert_row = self._find_new_folder_position_from_selection()
            self._new_folder(self.NEW_FOLDER_DEFAULT_NAME, parent, insert_row)
        else:
            super().keyPressEvent(event)
        
    def _find_new_folder_position_from_selection(self) -> Tuple[Optional[QStandardItem], int]:
        # Used by keyboard shortcut
        model = self.model()
        nesting_col = self.model().nesting_col()
        selected_list = [index for index in self.selectedIndexes() if index.column() == nesting_col]
        selected_index = QModelIndex()
        insert_row = -1
        parent:Optional[QStandardItem] = None
        if len(selected_list) > 0:
            selected_index = selected_list[0]

        if selected_index.isValid():
            selected_item = model.itemFromIndex(selected_index)
            if isinstance(selected_item, WatchableStandardItem):
                insert_row = selected_item.row()
                parent = selected_item.parent()
            elif isinstance(selected_item, FolderStandardItem):
                insert_row = -1
                parent = selected_item
            else:
                raise NotImplementedError(f"Unknown item type for {selected_item}")

        return parent, insert_row

    def _find_new_folder_position_from_position(self, position:QPoint) -> Tuple[Optional[QStandardItem], int]:
        # Used by right-click
        index = self.indexAt(position)
        if not index.isValid():
            return None, -1
        model = self.model()
        item = model.itemFromIndex(index)
        assert item is not None

        if isinstance(item, FolderStandardItem):
            return item, -1
        parent_index = index.parent()
        if not parent_index.isValid():
            return None, index.row()
        return model.itemFromIndex(parent_index), index.row()

    def _new_folder(self, name:str, parent:Optional[QStandardItem], insert_row:int) -> None:
        model = self.model()
        new_row = model.make_folder_row(name, fqn=None, editable=True)
        model.add_row_to_parent(parent, insert_row, new_row)
        if parent is not None:
            self.expand(parent.index()) 
        self.edit(new_row[0].index())

    def _set_drag_and_drop_action(self, event:Union[QDragEnterEvent, QDragMoveEvent, QDropEvent]) -> None:
        if event.source() is self:
            event.setDropAction(Qt.DropAction.MoveAction)
        else:
            event.setDropAction(Qt.DropAction.CopyAction)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        self._set_drag_and_drop_action(event)
        super().dragEnterEvent(event)
        event.accept()
        
    def dragMoveEvent(self, event: QDragMoveEvent) -> None:        
        self._set_drag_and_drop_action(event)
        return super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_drag_and_drop_action(event)
        return super().dropEvent(event)    

    def map_to_watchable_node(self, 
                            callback:Callable[[WatchableStandardItem, bool], None],
                            parent:Optional[BaseWatchableRegistryTreeStandardItem]=None
                            ) -> None:
        """Apply a callback to every watchable row in the tree and tells if it is visible to the user"""

        model = self.model()
        nesting_col = model.nesting_col()
        def recurse(item:QStandardItem, content_visible:bool) -> None:
            if isinstance(item, WatchableStandardItem):
                callback(item, content_visible)
            elif isinstance(item, FolderStandardItem):
                for i in range(item.rowCount()):
                    recurse(item.child(i,nesting_col), content_visible and self.isExpanded(item.index()))
            else:
                raise NotImplementedError(f"Unsupported item type: {item}")
        
        if parent is not None:
            recurse(parent, self.is_visible(parent))
        else:   # Root node. Iter all root items
            for i in range(model.rowCount()):
                recurse(model.item(i, nesting_col), True)
    
    def closeEditor(self, editor:QWidget, hint:QAbstractItemDelegate.EndEditHint) -> None:
        """Called when the user finishes editing a value. Press enter or blur focus"""
        item_written = self._model.itemFromIndex(self.currentIndex())
        model = self.model()
        nesting_col = model.nesting_col()
        if isinstance(item_written, ValueStandardItem):
            watchable_item = model.itemFromIndex(item_written.index().siblingAtColumn(nesting_col))
            if isinstance(watchable_item, WatchableStandardItem):   # paranoid check. Should never be false. Folders have no Value column
                fqn = watchable_item.fqn
                value = item_written.text()
                self.signals.value_written.emit(fqn, value)

        # Make arrow navigation easier because elements are nested on columns 0. 
        # If current index is at another column, we can't go up in the tree witht he keyboard
        self.setCurrentIndex(self.currentIndex().siblingAtColumn(nesting_col))
        
        return super().closeEditor(editor, hint)



class WatchComponentTreeModel(WatchableTreeModel):
    """An extension of the data model used by Watchable Trees dedicated for the Watch Component
    Mainly handles drag&drop logic
    """

    class Column(enum.Enum):
        # Item is always 0.
        VALUE = 1

    logger:logging.Logger
    _available_palette:QPalette
    _unavailable_palette:QPalette

    def __init__(self, 
                 parent: QWidget, 
                 watchable_registry: WatchableRegistry, 
                 available_palette:Optional[QPalette]=None, 
                 unavailable_palette:Optional[QPalette]=None) -> None:
        super().__init__(parent, watchable_registry)
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if available_palette is not None:
            self._available_palette = available_palette
        else:
            self._available_palette = QPalette()
            self._available_palette.setCurrentColorGroup(QPalette.ColorGroup.Active)

        if unavailable_palette is not None:
            self._unavailable_palette = unavailable_palette
        else:
            self._unavailable_palette = QPalette()
            self._unavailable_palette.setCurrentColorGroup(QPalette.ColorGroup.Disabled)

    def _assign_unique_watcher_id(self, item:WatchableStandardItem) -> None:
        watcher_id = global_i64_counter()
        item.setData(watcher_id, WATCHER_ID_ROLE)
    
    def get_watcher_id(self, item:WatchableStandardItem) -> int:
        uid = item.data(WATCHER_ID_ROLE)
        assert uid is not None
        return cast(int, uid)

    def watchable_item_created(self, item:WatchableStandardItem) -> None:
        self._assign_unique_watcher_id(item)
        return super().watchable_item_created(item)

    def itemFromIndex(self, index:Union[QModelIndex, QPersistentModelIndex]) -> BaseWatchableRegistryTreeStandardItem:
        return cast(BaseWatchableRegistryTreeStandardItem, super().itemFromIndex(index))
    
    def get_watchable_columns(self, watchable_config: Optional[WatchableConfiguration] = None) -> List[QStandardItem]:
        return [ValueStandardItem()]

    def _check_support_drag_data(self, drag_data:Optional[ScrutinyDragData], action:Qt.DropAction) -> bool:
        """Tells if a drop would be supported
        
        :param drag_data: The data to be dropped
        :param action: The drag&drop action
        :return: ``True`` if drop is supported/allowed
        """
        if drag_data is None:
            return False
        # Deny unsupported data type 
        if drag_data.type == ScrutinyDragData.DataType.WatchableFullTree:
            if action not in [ Qt.DropAction.MoveAction, Qt.DropAction.CopyAction ]:
                return False
        elif drag_data.type == ScrutinyDragData.DataType.WatchableTreeNodesTiedToRegistry:
            if action not in [ Qt.DropAction.CopyAction ]:
                return False
        elif drag_data.type == ScrutinyDragData.DataType.WatchableList:
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
    

    def _make_serializable_tree_descriptor(self, top_level_item:BaseWatchableRegistryTreeStandardItem, sortkey:int=0) -> SerializableTreeDescriptor:
        """Generate a serializable description of a tree without references"""
        assert top_level_item is not None
       
        dict_out : SerializableTreeDescriptor = {
            'node' : top_level_item.to_serialized_data(),
            'sortkey' : sortkey,
            'children' : []
        }

        nesting_col = self.nesting_col()
        for row_index in range(top_level_item.rowCount()):
            child = cast(BaseWatchableRegistryTreeStandardItem, top_level_item.child(row_index, nesting_col))
            dict_out['children'].append(self._make_serializable_tree_descriptor(child, sortkey=row_index))

        return dict_out


    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        """Generate the mimeData when a drag&drop starts"""
        
        nesting_col = self.nesting_col()
        def get_items(indexes:Iterable[QModelIndex]) -> Generator[BaseWatchableRegistryTreeStandardItem, None, None]:
            for index in indexes:
                if index.column() == nesting_col:
                    item = self.itemFromIndex(index)
                    assert item is not None
                    yield item

        top_level_items = [item for item in get_items(self.remove_nested_indexes(indexes))]

        self.sort_items_by_path(top_level_items, top_to_bottom=True)
        move_data = [self.make_serializable_item_index_descriptor(item) for item in top_level_items]
        drag_data =  self.make_watchable_list_dragdata_if_possible(top_level_items, data_move=move_data)
        
        # We have a tree or many elements, propagate as such
        if drag_data is None:
            serializable_tree_descriptors:List[SerializableTreeDescriptor] = []
            for i in range(len(top_level_items)):
                item = top_level_items[i]
                serializable_tree_descriptors.append(self._make_serializable_tree_descriptor(item, sortkey=i))

            drag_data = ScrutinyDragData(
                type=ScrutinyDragData.DataType.WatchableFullTree, 
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
        """ Tells QT if a dragged data can be dropped on the actual location """
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
        """React to a drop event and insert the dropped data to the specified location"""
        # We can only drop on root or on a folder
        if parent.isValid():
            if not isinstance(self.itemFromIndex(parent), FolderStandardItem):
                return False
        
        drag_data = ScrutinyDragData.from_mime(mime_data)
        if not self._check_support_drag_data(drag_data, action):
            return False
        assert drag_data is not None

        log_prefix = f"Drop [{drag_data.type.name}]"
        if drag_data.type == ScrutinyDragData.DataType.WatchableTreeNodesTiedToRegistry:
            if action == Qt.DropAction.CopyAction:
                self.logger.debug(f"{log_prefix}: Varlist data with {len(drag_data.data_copy)} nodes")
                return self._handle_drop_varlist_copy(parent, row_index, cast(List[NodeSerializableData], drag_data.data_copy))
            else:
                return False

        elif drag_data.type == ScrutinyDragData.DataType.WatchableFullTree:
            if action == Qt.DropAction.MoveAction:
                self.logger.debug(f"{log_prefix}: Watch internal move with {len(drag_data.data_move)} nodes")
                return self.handle_internal_move(parent, row_index, cast(List[SerializableItemIndexDescriptor], drag_data.data_move))
            elif action == Qt.DropAction.CopyAction:
                self.logger.debug(f"{log_prefix}: Watch external copy with {len(drag_data.data_copy)} nodes")
                return self._handle_tree_drop(parent, row_index, cast(List[SerializableTreeDescriptor], drag_data.data_copy))
            else:
                return False
            
        elif drag_data.type == ScrutinyDragData.DataType.WatchableList:
            if action == Qt.DropAction.MoveAction:
                self.logger.debug(f"{log_prefix}: Watch internal move with single element")
                return self.handle_internal_move(parent, row_index, cast(List[SerializableItemIndexDescriptor], drag_data.data_move))
            elif action == Qt.DropAction.CopyAction:
                self.logger.debug(f"{log_prefix}: Watch external copy with single element")
                watchable_elements = WatchableListDescriptor.from_drag_data(drag_data)
                if watchable_elements is None:
                    return False
                return self._handle_watchable_list_element_drop(parent, row_index,  watchable_elements)
            else:
                return False
            
        return False

    def _handle_drop_varlist_copy(self, 
                            parent_index: Union[QModelIndex, QPersistentModelIndex],
                            row_index:int,
                            data:List[NodeSerializableData]) -> bool:
        """Handle a drop coming from a varlist component. The data is a list of nodes, no nesting. Each node has a Fully qualified Name that points
        to the watchable registry"""#
        try:
            assert isinstance(data, list)
            for node in data:
                assert 'type' in node
                assert 'text' in node
                assert 'fqn' in node
                assert node['fqn'] is not None  # Varlist component guarantees a FQN
                parsed_fqn = WatchableRegistry.FQN.parse(node['fqn'])
                
                parent = self.itemFromIndex(parent_index)
                if node['type'] == 'folder':
                    folder_row = self.make_folder_row(node['text'], fqn=None, editable=True)
                    first_col = cast(BaseWatchableRegistryTreeStandardItem, folder_row[0])
                    self.add_row_to_parent(parent, row_index, folder_row)
                    self.fill_from_index_recursive(first_col, parsed_fqn.watchable_type, parsed_fqn.path, keep_folder_fqn=False, editable=True) 
                    for item in self.get_all_watchable_items(parent):
                        self.update_availability(item)
                    
                elif node['type'] == 'watchable':
                    watchable_row = self.make_watchable_row(node['text'], watchable_type=parsed_fqn.watchable_type, fqn=node['fqn'], editable=True)
                    self.add_row_to_parent(parent, row_index, watchable_row)

                    main_item = watchable_row[self.nesting_col()]
                    assert isinstance(main_item, WatchableStandardItem)
                    self.update_availability(main_item)
                else:
                    pass    # Silently ignore

                
            
            

        except AssertionError:
            return False
        
        return True

    
    
    def _handle_tree_drop(self, 
                        dest_parent_index: Union[QModelIndex, QPersistentModelIndex],
                        dest_row_index:int,
                        data:List[SerializableTreeDescriptor]) -> bool:
        """Handle the insertion of multiple tree nodes coming from a drag&drop.
        Only comes from a watch component (this one or another one)
        
        :param dest_parent_index: The new parent index. invalid index when root
        :param dest_row_index: The row index under the new parent. -1 to append
        :param data: List of tree description. no reference, a full copy of the tree
        
        :return: ``True`` On success
        """
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
                self._assign_unique_watcher_id(item)
                row = self.make_watchable_row_from_existing_item(item, editable=True, extra_columns=self.get_watchable_columns())
            else:
                raise NotImplementedError("Unsupported item type")
        
            self.add_row_to_parent(parent, row_index, row)
            if isinstance(item, WatchableStandardItem):
                self.update_availability(item)

            for child in sorted(descriptor['children'], key=lambda x:x['sortkey']):
                fill_from_tree_recursive(
                    parent = item,
                    row_index=-1,   # Append. List is sorted
                    descriptor=child
                )
        
        try:
            for descriptor in data:
                if dest_parent_index.isValid():
                    dest_parent_item =  self.itemFromIndex(dest_parent_index)
                    fill_from_tree_recursive(dest_parent_item, dest_row_index, descriptor)
                else:
                    fill_from_tree_recursive(None, dest_row_index, descriptor)
                
                if dest_row_index != -1:
                    dest_row_index+=1
        except AssertionError:
            return False
        return True
             
    def _handle_watchable_list_element_drop(self,
                        dest_parent_index: Union[QModelIndex, QPersistentModelIndex],
                        dest_row_index:int,
                        descriptors:WatchableListDescriptor) -> bool:
        """Handle the insertion of multiple watchable (leaf) nodes from a drag&drop.
        This can come from anywhere in the application, not necessarily from this component
        
        :param dest_parent_index: The new parent index. invalid index when root
        :param dest_row_index: The row index under the new parent. -1 to append
        :param descriptors: List of watchable nodes with a reference to their WatchableRegistry location
        
        :return: ``True`` On success
        """
        dest_parent = self.itemFromIndex(dest_parent_index)
        rows:List[List[QStandardItem]] = []
        for descriptor in descriptors.data:
            watchable_type = WatchableRegistry.FQN.parse(descriptor.fqn).watchable_type
            row = self.make_watchable_row(
                watchable_type=watchable_type,
                name = descriptor.text,
                fqn=descriptor.fqn,
                editable=True,
                extra_columns=self.get_watchable_columns()
            )
            rows.append(row)

        self.add_multiple_rows_to_parent(dest_parent, dest_row_index, rows)
        for row in rows:
            main_item = row[self.nesting_col()]
            assert isinstance(main_item, WatchableStandardItem)
            self.update_availability(main_item)

        return True

    def get_all_watchable_items(self, parent:Optional[BaseWatchableRegistryTreeStandardItem]=None) -> Generator[WatchableStandardItem, None, None]:
        """Return every elements in the tree that points to a watchable item in the registry"""
        def recurse(parent:QStandardItem) -> Generator[WatchableStandardItem, None, None]:
            for i in range(parent.rowCount()):
                child = parent.child(i, 0)
                if isinstance(child, FolderStandardItem):
                    yield from recurse(child)
                elif isinstance(child, WatchableStandardItem):
                    yield child
                else:
                    raise NotImplementedError(f"Unsupported item type: {child}")
        
        if parent is None:
            nesting_col = self.nesting_col()
            for i in range(self.rowCount()):
                child = self.item(i, nesting_col)
                if isinstance(child, FolderStandardItem):
                    yield from recurse(child)
                elif isinstance(child, WatchableStandardItem):
                    yield child
                else:
                    raise NotImplementedError(f"Unsupported item type: {child}")
        else:
            recurse(parent)
            
    def update_availability(self, watchable:WatchableStandardItem) -> None:
        """Change the availability of an item based on its availibility in the registry. 
        When the watchable refered by an element is not in the registry, becomes "unavailable" (grayed out).
        """
        if self._watchable_registry.is_watchable_fqn(watchable.fqn):
            self.set_available(watchable)
        else:
            self.set_unavailable(watchable)
        
    def set_unavailable(self, arg_item:WatchableStandardItem) -> None:
        """Make an item in the tree unavailable (grayed out)"""
        background_color = self._unavailable_palette.color(QPalette.ColorRole.Base)
        forground_color = self._unavailable_palette.color(QPalette.ColorRole.Text)
        for i in range(self.columnCount()):
            item = self.itemFromIndex(arg_item.index().siblingAtColumn(i))
            if item is not None:
                item.setData(False, AVAILABLE_DATA_ROLE)
                item.setBackground(background_color)
                item.setForeground(forground_color)
                if isinstance(item, ValueStandardItem):
                    item.setEditable(False)
                    item.setText('N/A')
    
    def set_available(self, arg_item:WatchableStandardItem) -> None:
        """Make an item in the tree available (normal color)"""
        background_color = self._available_palette.color(QPalette.ColorRole.Base)
        forground_color = self._available_palette.color(QPalette.ColorRole.Text)
        for i in range(self.columnCount()):
            item = self.itemFromIndex(arg_item.index().siblingAtColumn(i))
            if item is not None:
                item.setData(True, AVAILABLE_DATA_ROLE)
                item.setBackground(background_color)
                item.setForeground(forground_color)
                if isinstance(item, ValueStandardItem):
                    item.setEditable(True)
    
    def is_available(self, arg_item:WatchableStandardItem) -> bool:
        v = cast(Optional[bool], arg_item.data(AVAILABLE_DATA_ROLE))
        if v == True:
            return True
        return False

    def get_value_item(self, item:WatchableStandardItem) -> ValueStandardItem:
        o = self.itemFromIndex(item.index().siblingAtColumn(self.value_col()))
        assert isinstance(o, ValueStandardItem)
        return o

    def value_col(self) -> int:
        return self.get_column_index(self.Column.VALUE)    

    def get_column_index(self, col:Column) -> int:
        # Indirection layer to make it easier to enable column reorder
        return col.value
