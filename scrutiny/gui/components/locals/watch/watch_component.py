#    watch_component.py
#        A component to look at the value of watchable items broadcast by the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = [
    'WatchComponent'
]
import logging

from PySide6.QtCore import QModelIndex, Qt, QModelIndex, Signal
from PySide6.QtWidgets import QVBoxLayout

from scrutiny import sdk
from scrutiny.gui import assets
from scrutiny.gui.core.server_manager import ValueUpdate
from scrutiny.gui.core.watchable_registry import WatchableRegistryNodeNotFoundError, WatcherNotFoundError
from scrutiny.gui.components.locals.base_local_component import ScrutinyGUIBaseLocalComponent
from scrutiny.gui.widgets.watchable_tree import WatchableTreeWidget, WatchableStandardItem, FolderStandardItem, BaseWatchableRegistryTreeStandardItem
from scrutiny.gui.components.locals.watch.watch_tree_model import WatchComponentTreeModel, ValueStandardItem, WatchComponentTreeWidget
from scrutiny.tools import format_exception

from scrutiny.tools.typing import *


class State:
    TYPE_WATCHABLE = 'w'
    TYPE_FOLDER = 'f'

    KEY_TYPE = 'type'
    KEY_TEXT = 'txt'
    KEY_FQN = 'fqn'
    KEY_WATCHABLE_TYPE = 'wtype'
    KEY_CHILDREN = 'children'
    KEY_EXPANDED = 'expand'

    class Folder(TypedDict):
        type:str
        children:List[Union["State.Watchable", "State.Folder" ]]

    class Watchable(TypedDict):
        type:str
        fqn:str
        text:str


class WatchComponent(ScrutinyGUIBaseLocalComponent):
    instance_name : str

    _ICON = assets.get("eye-96x128.png")
    _NAME = "Watch Window"
    _TYPE_ID = "watch"

    _tree:WatchComponentTreeWidget
    _tree_model:WatchComponentTreeModel
    _teared_down:bool

    expand_if_needed = Signal()

    def setup(self) -> None:
        self._tree_model = WatchComponentTreeModel(self, watchable_registry=self.watchable_registry)
        self._tree = WatchComponentTreeWidget(self, self._tree_model)
        self._teared_down = False

        layout = QVBoxLayout(self)
        layout.addWidget(self._tree)

        self.expand_if_needed.connect(self._tree.expand_first_column_to_content, Qt.ConnectionType.QueuedConnection)
        
        self._tree.expanded.connect(self.node_expanded_slot)
        self._tree.collapsed.connect(self.node_collapsed_slot)

        self.server_manager.signals.registry_changed.connect(self.registry_changed_slot)

        self._tree_model.rowsInserted.connect(self.row_inserted_slot)
        self._tree_model.rowsAboutToBeRemoved.connect(self.row_about_to_be_removed_slot)
        self._tree_model.rowsMoved.connect(self.row_moved_slot)
        self._tree.signals.value_written.connect(self._value_written_slot)
    
        self.update_all_watchable_state()
    
    def teardown(self) -> None:
        for item in self._tree_model.get_all_watchable_items():
            self._unwatch_item(item)
            watcher_id = self._get_watcher_id(item)
            try:
                self.watchable_registry.unregister_watcher(watcher_id)
            except WatcherNotFoundError:
                # Should not happen (hopefully). The registry is expected to keep the watchers even after a clear
                self.logger.error(f"Tried to unregister watcher {watcher_id}, but was not registered")
        self._teared_down = True


    def get_state(self) -> Dict[Any, Any]:
        def _get_children_recursive(parent:Optional[FolderStandardItem]=None) -> Generator[Union[State.Folder, State.Watchable], None, None]:
            row_count = self._tree_model.rowCount() if parent is None else parent.rowCount()
            parent_index = QModelIndex() if parent is None else parent.index()

            for i in range(row_count):
                item = self._get_item(parent_index, i)
                if isinstance(item, WatchableStandardItem):
                    yield cast(State.Watchable, {
                        State.KEY_TYPE : State.TYPE_WATCHABLE,
                        State.KEY_WATCHABLE_TYPE : item.watchable_type.to_str(),
                        State.KEY_TEXT : item.text(),
                        State.KEY_FQN : item.fqn
                    })
                elif isinstance(item, FolderStandardItem):
                    yield cast(State.Folder,{
                      State.KEY_TYPE : State.TYPE_FOLDER,
                      State.KEY_TEXT : item.text(),
                      State.KEY_EXPANDED : self._tree.isExpanded(item.index()),
                      State.KEY_CHILDREN : list(_get_children_recursive(item))  
                    })
        return {
            'root' : list(_get_children_recursive())
        }

    def load_state(self, state:Dict[Any, Any]) -> bool:
        return True
    
#    def load_state(self, state:Dict[Any, Any]) -> None:
#        # FIXME : Does not work properly.
#        
#        self._tree_model.clear()
#
#        def load_node_recursive(children_list:List[Union[State.Folder, State.Watchable]], parent_node:Optional[FolderStandardItem]=None) -> None:
#            if not isinstance(children_list, list):
#                raise ValueError("Children should be a list")
#
#            for child in children_list:
#                if State.KEY_TYPE not in child:
#                    raise ValueError(f"Missing key {State.KEY_TYPE} on node")
#                
#                # ============= Folder ============
#                if child[State.KEY_TYPE] == State.TYPE_FOLDER:
#                    for k in [State.KEY_TEXT]:
#                        if k not in child:
#                            raise KeyError(f"Missing key {k} on node")
#                    
#                    row = self._tree_model.make_folder_row(
#                        name = child[State.KEY_TEXT],
#                        fqn=None,
#                        editable = True
#                    )
#                    self._tree_model.add_row_to_parent(parent_node, -1, row)
#
#                    expanded = child.get(State.KEY_EXPANDED, False)
#                    new_parent_node = row[self._tree_model.nesting_col()]
#                    if expanded:
#                        self._tree.expand(new_parent_node.index())
#                    else:
#                        self._tree.collapse(new_parent_node.index())
#                    
#                    children = child.get(State.KEY_CHILDREN, [])
#                    load_node_recursive(children, new_parent_node)
#            
#                # ============ Watchable ===========
#                elif child[State.KEY_TYPE] == State.TYPE_WATCHABLE:
#                    for k in [State.KEY_TEXT, State.KEY_FQN, State.KEY_WATCHABLE_TYPE]:
#                        if k not in child:
#                            raise KeyError(f"Missing key {k} on node")
#                    
#                    row = self._tree_model.make_watchable_row(
#                        name = child[State.KEY_TEXT],
#                        editable = True,
#                        watchable_type = child[State.KEY_WATCHABLE_TYPE],
#                        fqn = child[State.KEY_FQN],
#                        extra_columns=self._tree_model.get_watchable_columns()  # Todo, should not have to pass this explicitly
#                    )
#                    self._tree_model.add_row_to_parent(parent_node, -1, row)
#                else:
#                    raise ValueError(f"Unsupported node type : {child[State.KEY_TYPE]}")
#
#        try:
#            if 'root' not in state:
#                raise KeyError("Missing root key")
#            load_node_recursive(state['root'])
#        except Exception as e:
#            self.logger.warning(f'Invalid state to reload. {e}')
#        
#        self.update_all_watchable_state()



    def _get_item(self, parent:QModelIndex, row_index:int) -> Optional[BaseWatchableRegistryTreeStandardItem]:
        """Get the item pointed by the index and the row (column is assumed 0). Handles the no-parent case
        
        :parent: The parent index. Invalid index for root.
        :row_index: The row number of the item

        :return: The item or ``None`` if not available
        """
        nesting_col = self._tree_model.nesting_col()
        if not parent.isValid():
            return cast(Optional[BaseWatchableRegistryTreeStandardItem], self._tree_model.item(row_index, nesting_col))
        
        return cast(Optional[BaseWatchableRegistryTreeStandardItem], self._tree_model.itemFromIndex(parent).child(row_index, nesting_col))

    def registry_changed_slot(self) -> None:
        self.resubscribe_all_rows_as_watcher()
        self.update_all_watchable_state()

    def _register_watcher_for_row(self, item:WatchableStandardItem)-> None:
        value_item = self._tree_model.get_value_item(item)
        def update_val_closure(watcher_id:Union[str, int], vals:List[ValueUpdate]) -> None:
            return self.update_val_callback(value_item, watcher_id, vals )
        
        def unwatch_closure(watcher_id:Union[str, int], server_path:str, watchable_config:sdk.WatchableConfiguration) -> None:
            pass
        
        watcher_id = self._get_watcher_id(item)
        self.watchable_registry.register_watcher(watcher_id, update_val_closure, unwatch_closure, ignore_duplicate=True)


    def row_inserted_slot(self, parent:QModelIndex, row_index:int, col_index:int) -> None:
        # This slots is called for every row inserted when new rows. Only parent when existing row

        def func (item:WatchableStandardItem, visible:bool) -> None:
            self._register_watcher_for_row(item)
            if visible:
                self._watch_item(item)

        item_inserted = self._get_item(parent, row_index)
        if isinstance(item_inserted, FolderStandardItem):
            if item_inserted.is_expanded():
                self._tree.expand(item_inserted.index())
        self._tree.map_to_watchable_node(func, item_inserted)

    
    def row_about_to_be_removed_slot(self, parent:QModelIndex, row_index:int, col_index:int) -> None:
        # This slot is called only on the node removed, not on the children.
        def func (item:WatchableStandardItem, visible:bool) -> None:
            watcher_id = self._get_watcher_id(item)
            try:
                # Unregistering causes an unwatch of all watched items. 
                # In this component, each watcher has a single watched item
                self.watchable_registry.unregister_watcher(watcher_id)
            except WatcherNotFoundError:
                # Should not happen (hopefully). The registry is expected to keep the watchers even after a clear
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

    def visibilityChanged(self, visible:bool) -> None:
        """Called when the dashboard component is either hidden or showed"""
        if self._teared_down:
            # We're dead. Nothing to do now. 
            # This is just the last callback telling that the dockpanel is not visible anymore before deletion
            return
        
        if visible:
            self.update_all_watchable_state()
        else:
            for item in self._tree_model.get_all_watchable_items():
                self._unwatch_item(item)
    
    def _watch_item(self, item:WatchableStandardItem) -> None:
        """Internal function registering a tree line from the watchable registry"""
        watcher_id = self._get_watcher_id(item)
        if self.logger.isEnabledFor(logging.DEBUG): #pragma: no cover
            self.logger.debug(f"Watching item {item.fqn} (watcher ID = {watcher_id})")
        try:
            self.watchable_registry.watch_fqn(watcher_id, item.fqn)
        except WatchableRegistryNodeNotFoundError:
            # we tolerate because a race condition could cause this if the server dies while the GUI is working
            # Should not happen normally
            self.logger.debug(f"Cannot watch {item.fqn}. Does not exist")
    
    def _unwatch_item(self, item:WatchableStandardItem, quiet:bool=True) -> None:
        """Internal function unregistering a tree line from the watchable registry"""
        watcher_id = self._get_watcher_id(item)
        if self.logger.isEnabledFor(logging.DEBUG): #pragma: no cover
            self.logger.debug(f"Unwatching item {item.fqn} (watcher ID = {watcher_id})")
        try:
            self.watchable_registry.unwatch_fqn(watcher_id, item.fqn)
        except WatchableRegistryNodeNotFoundError:
            # We tolerate because a race condition could cause this if the server dies while the GUI is working
            # Should not happen normally
            self.logger.debug(f"Cannot unwatch {item.fqn}. Does not exist")
            if not quiet:
                raise
    
    def _get_watcher_id(self, item:WatchableStandardItem) -> int:
        return self._tree_model.get_watcher_id(item)
    
    def resubscribe_all_rows_as_watcher(self) -> None:
        """Iterate all watchable row in the tree and (re)subscribe them as watchers"""
        def subscribe_func(item:WatchableStandardItem, visible:bool) -> None:
            self._register_watcher_for_row(item)
        self._tree.map_to_watchable_node(subscribe_func)

    def update_all_watchable_state(self, start_node:Optional[BaseWatchableRegistryTreeStandardItem]=None) -> None:
        """Make a watchable row watch or unwatch the item they refer to based on their visibility to the user"""
        def update_func(item:WatchableStandardItem, visible:bool) -> None:
            if visible :
                self._watch_item(item)
            else:
                self._unwatch_item(item)
            self._tree_model.update_availability(item)

        self._tree.map_to_watchable_node(update_func, start_node)

    def update_val_callback(self, item:ValueStandardItem, watcher_id:Union[str, int], vals:List[ValueUpdate]) -> None:
        """The function called when we receive value updates from the server"""
        assert len(vals) > 0
        can_update = True
        nesting_col = self._tree_model.nesting_col()
        if self._tree.state() == WatchableTreeWidget.State.EditingState:
            if item.index().siblingAtColumn(nesting_col) == self._tree.currentIndex().siblingAtColumn(nesting_col):
                can_update = False  # Don't change the content. The user is writing something
        
        if can_update:
            item.setText(str(vals[-1].value))

    def _value_written_slot(self, fqn:str, value:str) -> None:
        """The QT slot called when the user input a new value in a value field"""
        def ui_callback(exception:Optional[Exception]) -> None:
            if exception is not None:
                self.logger.warning(f"Failed to write {fqn}. {exception}")
                self.logger.debug(format_exception(exception))

        # No need to parse strings. The server auto-converts
        # Supports : Number as strings. Hexadecimal with 0x prefix, true/false, etc.
        self.server_manager.qt_write_watchable_value(fqn, value, ui_callback)
        