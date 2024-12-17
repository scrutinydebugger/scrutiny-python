#    watch_component.py
#        A component to look at the value of watchable items broadcast by the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = [
    'WatchComponentTreeWidget',
    'WatchComponent'
]

from PySide6.QtCore import QModelIndex, Qt, QModelIndex, Signal, QPoint
from PySide6.QtWidgets import QVBoxLayout, QWidget, QMenu
from PySide6.QtGui import QContextMenuEvent, QDragMoveEvent, QDropEvent, QDragEnterEvent, QKeyEvent, QStandardItem, QAction

from scrutiny.gui import assets
from scrutiny.gui.core.watchable_registry import WatchableRegistryNodeNotFoundError, WatcherNotFoundError
from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from scrutiny.gui.dashboard_components.common.watchable_tree import WatchableTreeWidget, WatchableStandardItem, FolderStandardItem, BaseWatchableRegistryTreeStandardItem
from scrutiny.gui.dashboard_components.watch.watch_tree_model import WatchComponentTreeModel, ValueStandardItem

from scrutiny.gui.core.server_manager import ValueUpdate

from typing import Dict, Any, Union, cast, Optional, Tuple, Callable, List

class WatchComponentTreeWidget(WatchableTreeWidget):
    NEW_FOLDER_DEFAULT_NAME = "New Folder"

    def __init__(self, parent: QWidget, model:WatchComponentTreeModel) -> None:
        super().__init__(parent, model)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(self.DragDropMode.DragDrop)
        self.set_header_labels(['', 'Value'])

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        context_menu = QMenu(self)
        selected_indexes_no_nested = self.model().remove_nested_indexes(self.selectedIndexes())
        selected_items_no_nested = [self.model().itemFromIndex(index) for index in selected_indexes_no_nested if index.column()==0]

        parent, insert_row = self._find_new_folder_position_from_position(event.pos())
        
        def new_folder_action_slot() -> None:
            self._new_folder(self.NEW_FOLDER_DEFAULT_NAME, parent, insert_row)
        
        def remove_actionslot() -> None:
            for item in selected_items_no_nested:
                self.model().removeRow(item.row(), item.index().parent())
        
        new_folder_action = context_menu.addAction(assets.load_icon(assets.Icons.TreeFolder), "New Folder")
        new_folder_action.triggered.connect(new_folder_action_slot)
        
        remove_action = context_menu.addAction(assets.load_icon(assets.Icons.RedX), "Remove")
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
        
    def model(self) -> WatchComponentTreeModel:
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
        elif event.key() == Qt.Key.Key_N and event.modifiers() == Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier:
            parent, insert_row = self._find_new_folder_position_from_selection()
            self._new_folder(self.NEW_FOLDER_DEFAULT_NAME, parent, insert_row)
        else:
            super().keyPressEvent(event)
        
    

    def _find_new_folder_position_from_selection(self) -> Tuple[Optional[QStandardItem], int]:
        # USed by keyboard shortcut
        model = self.model()
        selected_list = [index for index in self.selectedIndexes() if index.column() == 0]
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
        def recurse(item:QStandardItem, content_visible:bool) -> None:
            if isinstance(item, WatchableStandardItem):
                callback(item, content_visible)
            elif isinstance(item, FolderStandardItem):
                for i in range(item.rowCount()):
                    recurse(item.child(i,0), content_visible and self.isExpanded(item.index()))
            else:
                raise NotImplementedError(f"Unsupported item type: {item}")
        
        if parent is not None:
            recurse(parent, self.is_visible(parent))
        else:   # Root node. Iter all root items
            for i in range(model.rowCount()):
                recurse(model.item(i, 0), True)
    
class WatchComponent(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("eye-96x128.png")
    _NAME = "Watch Window"

    _tree:WatchComponentTreeWidget
    _tree_model:WatchComponentTreeModel

    expand_if_needed = Signal()

    def setup(self) -> None:
        self._tree_model = WatchComponentTreeModel(self, watchable_registry=self.server_manager.registry)
        self._tree = WatchComponentTreeWidget(self, self._tree_model)

        layout = QVBoxLayout(self)
        layout.addWidget(self._tree)

        self.expand_if_needed.connect(self._tree.expand_first_column_to_content, Qt.ConnectionType.QueuedConnection)
        
        self._tree.expanded.connect(self.node_expanded_slot)
        self._tree.collapsed.connect(self.node_collapsed_slot)
        self.server_manager.signals.registry_changed.connect(self.update_all_watchable_state)

        self._tree_model.rowsInserted.connect(self.row_inserted_slot)
        self._tree_model.rowsAboutToBeRemoved.connect(self.row_about_to_be_removed_slot)
        self._tree_model.rowsMoved.connect(self.row_moved_slot)
    
        self.update_all_watchable_state()
    
    def _get_item(self, parent:QModelIndex, row_index:int) -> Optional[BaseWatchableRegistryTreeStandardItem]:
        """Get the item pointed by the index and the row (column is assumed 0). Handles the no-parent case
        
        :parent: The parent index. Invalid index for root.
        :row_index: The row number of the item

        :return: The item or ``None`` if not available
        """
        if not parent.isValid():
            return cast(Optional[BaseWatchableRegistryTreeStandardItem], self._tree_model.item(row_index, 0))
        
        return cast(Optional[BaseWatchableRegistryTreeStandardItem], self._tree_model.itemFromIndex(parent).child(row_index, 0))

    
    def row_inserted_slot(self, parent:QModelIndex, row_index:int, col_index:int) -> None:
        # This slots is called for every row inserted, even if nested
        item_inserted = self._get_item(parent, row_index)
        if isinstance(item_inserted, WatchableStandardItem):
            value_item = self._get_value_item(item_inserted)
            def callback_closure(watcher_id:Union[str, int], vals:List[ValueUpdate]) -> None:
                return self.update_val_callback(value_item, watcher_id, vals )
            watcher_id = self._get_watcher_id(item_inserted)
            self.server_manager.registry.register_watcher(watcher_id, callback_closure, override=True)

            if self._tree.is_visible(item_inserted):
                self._watch_item(item_inserted)

    def row_about_to_be_removed_slot(self, parent:QModelIndex, row_index:int, col_index:int) -> None:
        # This slot is called only on the node removed, not on the children.
        def func (item:WatchableStandardItem, visible:bool) -> None:
            watcher_id = self._get_watcher_id(item)
            try:
                # Unregistering causes an unwatch of all watched items. 
                # In this component, each watcher has a single watched item
                self.server_manager.registry.unregister_watcher(watcher_id)
            except WatcherNotFoundError:
                # Should not happen (hopefully)
                self.logger.error(f"Tried to unregister watcher {watcher_id}, but was not registered")
        
        item_removed = self._get_item(parent, row_index)
        self._tree.map_to_watchable_node(func, parent=item_removed)
        
    def node_expanded_slot(self, index:QModelIndex) -> None:
        # Added at the end of the event loop because it is a queuedConnection
        # Expanding with star requires that
        self.expand_if_needed.emit()
        self.update_all_watchable_state(start_node=self._tree_model.itemFromIndex(index))

    def node_collapsed_slot(self, index:QModelIndex) -> None:
        self.update_all_watchable_state(start_node=self._tree_model.itemFromIndex(index))
    
    def row_moved_slot(self, src_parent:QModelIndex, src_row:int, src_col:int, dest_parent:QModelIndex, dst_row:int) -> None:
        self.update_all_watchable_state(start_node=self._tree_model.itemFromIndex(dest_parent))
    
    def _get_value_item(self, item:WatchableStandardItem) -> ValueStandardItem:
        # TODO : Can we do better than a hard coded index? What if the column can be reordered (possible with an option)
        o = cast(ValueStandardItem, self._tree_model.itemFromIndex(item.index().siblingAtColumn(1)))
        assert o is not None
        return o

    def visibilityChanged(self, visible:bool) -> None:
        """Called when the dashboard component is either hidden or showed"""
        if visible:
            self.update_all_watchable_state()
        else:
            for item in self._tree_model.get_all_watchable_items():
                self._unwatch_item(item)
    
    def _watch_item(self, item:WatchableStandardItem) -> None:
        watcher_id = self._get_watcher_id(item)
        try:
            self.server_manager.registry.watch_fqn(watcher_id, item.fqn)
        except WatchableRegistryNodeNotFoundError:
            # we tolerate because a race condition could cause this if the server dies while the GUI is working
            # Should not happen normally
            self.logger.debug(f"Cannot watch {item.fqn}. Does not exist")
    
    def _unwatch_item(self, item:WatchableStandardItem, quiet:bool=True) -> None:
        watcher_id = self._get_watcher_id(item)
        try:
            self.server_manager.registry.unwatch_fqn(watcher_id, item.fqn)
        except WatchableRegistryNodeNotFoundError:
            # We tolerate because a race condition could cause this if the server dies while the GUI is working
            # Should not happen normally
            self.logger.debug(f"Cannot unwatch {item.fqn}. Does not exist")
            if not quiet:
                raise
    
    def _get_watcher_id(self, item:WatchableStandardItem) -> int:
        return self._tree_model.get_watcher_id(item)
    
    def update_all_watchable_state(self, start_node:Optional[BaseWatchableRegistryTreeStandardItem]=None) -> None:
        def update_func(item:WatchableStandardItem, visible:bool) -> None:
            if visible :
                self._watch_item(item)
            else:
                self._unwatch_item(item)
            self._tree_model.update_availability(item)

        self._tree.map_to_watchable_node(update_func, start_node)

    def update_val_callback(self, item:ValueStandardItem, watcher_id:Union[str, int], vals:List[ValueUpdate]) -> None:
        assert len(vals) > 0
        item.setText(str(vals[-1].value))

    def teardown(self) -> None:
        for item in self._tree_model.get_all_watchable_items():
            self._unwatch_item(item)

    def get_state(self) -> Dict[Any, Any]:
        raise NotImplementedError()

    def load_state(self, state: Dict[Any, Any]) -> None:
        raise NotImplementedError()
