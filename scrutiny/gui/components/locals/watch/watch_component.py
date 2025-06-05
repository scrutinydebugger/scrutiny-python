#    watch_component.py
#        A component to look at the value of watchable items broadcast by the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['WatchComponent']

import logging

from PySide6.QtCore import QModelIndex, Qt, QModelIndex, Signal
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtGui import QIcon

from scrutiny import sdk
from scrutiny.gui import assets
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui.widgets.watchable_tree import FolderItemSerializableData, WatchableItemSerializableData
from scrutiny.gui.core.server_manager import ValueUpdate
from scrutiny.gui.core.watchable_registry import WatchableRegistryNodeNotFoundError, WatcherNotFoundError
from scrutiny.gui.components.locals.base_local_component import ScrutinyGUIBaseLocalComponent
from scrutiny.gui.widgets.watchable_tree import WatchableTreeWidget, WatchableStandardItem, FolderStandardItem, BaseWatchableRegistryTreeStandardItem
from scrutiny.gui.components.locals.watch.watch_tree_model import WatchComponentTreeModel, ValueStandardItem, WatchComponentTreeWidget, SerializableTreeDescriptor
from scrutiny import tools

from scrutiny.tools.typing import *


class State:
    TYPE_WATCHABLE = 'w'
    TYPE_FOLDER = 'f'

    # I don't know why, but mypy doesn't understand that this is a literal without a Literal[] type hint
    # Could not reproduce in a different file... possibly a mypy bug ?
    KEY_TYPE: Literal['type'] = 'type'
    KEY_TEXT: Literal['txt'] = 'txt'
    KEY_FQN: Literal['fqn'] = 'fqn'
    KEY_CHILDREN: Literal['children'] = 'children'
    KEY_EXPANDED: Literal['expand'] = 'expand'

    class Folder(TypedDict):
        type: str
        txt: str
        expand: bool
        children: List[Union["State.Watchable", "State.Folder"]]

    class Watchable(TypedDict):
        type: str
        fqn: str
        txt: str


class WatchComponent(ScrutinyGUIBaseLocalComponent):
    instance_name: str

    _NAME = "Watch Window"
    _TYPE_ID = "watch"

    _tree: WatchComponentTreeWidget
    _tree_model: WatchComponentTreeModel
    _teared_down: bool

    expand_if_needed = Signal()

    @classmethod
    def get_icon(cls) -> QIcon:
        return scrutiny_get_theme().load_medium_icon(assets.Icons.Watch)

    def setup(self) -> None:
        self._tree_model = WatchComponentTreeModel(self, watchable_registry=self.watchable_registry)
        self._tree = WatchComponentTreeWidget(self, self._tree_model)
        self._teared_down = False

        layout = QVBoxLayout(self)
        layout.addWidget(self._tree)

        self.expand_if_needed.connect(self._tree.expand_first_column_to_content, Qt.ConnectionType.QueuedConnection)

        self._tree.expanded.connect(self._node_expanded_slot)
        self._tree.collapsed.connect(self._node_collapsed_slot)

        self.server_manager.signals.registry_changed.connect(self._registry_changed_slot)

        self._tree_model.rowsInserted.connect(self._row_inserted_slot)
        self._tree_model.rowsAboutToBeRemoved.connect(self._row_about_to_be_removed_slot)
        self._tree_model.rowsMoved.connect(self._row_moved_slot)
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
        def _get_children_recursive(parent: Optional[FolderStandardItem] = None) -> Generator[Union[State.Folder, State.Watchable], None, None]:
            row_count = self._tree_model.rowCount() if parent is None else parent.rowCount()
            parent_index = QModelIndex() if parent is None else parent.index()

            for i in range(row_count):
                item = self._get_item(parent_index, i)
                if isinstance(item, WatchableStandardItem):
                    yield cast(State.Watchable, {
                        State.KEY_TYPE: State.TYPE_WATCHABLE,
                        State.KEY_TEXT: item.text(),
                        State.KEY_FQN: item.fqn
                    })
                elif isinstance(item, FolderStandardItem):
                    yield cast(State.Folder, {
                        State.KEY_TYPE: State.TYPE_FOLDER,
                        State.KEY_TEXT: item.text(),
                        State.KEY_EXPANDED: self._tree.isExpanded(item.index()),
                        State.KEY_CHILDREN: list(_get_children_recursive(item))
                    })

        # Compute columns order for the state
        logical_col_map = self.get_column_logical_indexes_by_name()
        visual_cols = [(self._tree.header().visualIndex(v), k) for k, v in logical_col_map.items()]
        visual_cols.sort(key=lambda x: x[0])
        cols = [x[1] for x in visual_cols]

        return {
            'root': list(_get_children_recursive()),
            'cols': cols
        }

    def load_state(self, state: Dict[Any, Any]) -> bool:
        # In order to reload a state, we convert the state data into the same data structure that a drag & drop produces
        # then we reuse the same entry point to the tree model to reload it.
        fully_loaded = True
        self._tree_model.removeRows(0, self._tree_model.rowCount())

        try:
            if 'root' not in state:
                raise KeyError("Missing root key")

            if not isinstance(state['root'], list):
                raise KeyError("Invalid root key")

            serialized_data: List[SerializableTreeDescriptor] = []
            for state_item in state['root']:
                serialized_data.append(self._state_node_to_dnd_serializable_node_recursive(state_item))

            self._tree_model.load_serialized_tree_descriptor(
                dest_parent_index=QModelIndex(),    # root
                dest_row_index=-1,                  # append
                data=serialized_data
            )
        except Exception as e:
            fully_loaded = False
            self.logger.warning(f'Invalid state to reload. {e}')

        self.update_all_watchable_state()

        # Reorder the columns order
        cols = state.get('cols', [])
        visual_dst = 1
        logical_col_map = self.get_column_logical_indexes_by_name()
        for i in range(len(cols)):
            col = cols[i]
            if col in logical_col_map:
                logical_src = logical_col_map[col]
            else:
                continue

            self._tree.header().moveSection(self._tree.header().visualIndex(logical_src), visual_dst)
            visual_dst += 1

        return fully_loaded

    def visibilityChanged(self, visible: bool) -> None:
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

    def get_column_logical_indexes_by_name(self) -> Dict[str, int]:
        """Return a map of the columns index identified by a name that can be serialized for state save/reload"""
        return {
            'value': self._tree_model.value_col(),
            'type': self._tree_model.datatype_col(),
            'enum': self._tree_model.enum_col(),
        }

    def column_count(self) -> int:
        """Return the number of columns"""
        return self._tree_model.columnCount()

    def _state_node_to_dnd_serializable_node_recursive(self, state_item: Union[State.Folder, State.Watchable], level: int = 0) -> SerializableTreeDescriptor:
        """Convert a node form the state dict to a serializable node used whil drag&dropping """
        if State.KEY_TYPE not in state_item:
            raise ValueError(f"Missing key {State.KEY_TYPE} on node")

        # The output node
        serializable_item: SerializableTreeDescriptor = {
            'node': '',    # type: ignore
            'sortkey': level,
            'children': []
        }

        # ============= Folder ============
        if state_item[State.KEY_TYPE] == State.TYPE_FOLDER:
            state_item = cast(State.Folder, state_item)
            for k1 in [State.KEY_TEXT]:
                if k1 not in state_item:
                    raise KeyError(f"Missing key {k1} on node")
            expanded = state_item.get(State.KEY_EXPANDED, False)
            if not isinstance(expanded, bool):
                expanded = False

            serializable_folder: FolderItemSerializableData = {
                'text': state_item[State.KEY_TEXT],
                'expanded': expanded,
                'fqn': None,
                'type': FolderStandardItem.serialized_node_type(),
            }

            serializable_item['node'] = serializable_folder

            for child_state_item in state_item.get(State.KEY_CHILDREN, []):
                serializable_item['children'].append(self._state_node_to_dnd_serializable_node_recursive(child_state_item, level + 1))

        # ============ Watchable ===========
        elif state_item[State.KEY_TYPE] == State.TYPE_WATCHABLE:
            state_item = cast(State.Watchable, state_item)
            for k2 in [State.KEY_TEXT, State.KEY_FQN]:
                if k2 not in state_item:
                    raise KeyError(f"Missing key {k2} on node")

            serializable_watcahble: WatchableItemSerializableData = {
                'text': state_item[State.KEY_TEXT],
                'fqn': state_item[State.KEY_FQN],
                'type': WatchableStandardItem.serialized_node_type()
            }

            serializable_item['node'] = serializable_watcahble

        else:
            raise ValueError(f"Unsupported node type : {state_item[State.KEY_TYPE]}")

        return serializable_item

    def _get_item(self, parent: QModelIndex, row_index: int) -> Optional[BaseWatchableRegistryTreeStandardItem]:
        """Get the item pointed by the index and the row (column is assumed 0). Handles the no-parent case

        :parent: The parent index. Invalid index for root.
        :row_index: The row number of the item

        :return: The item or ``None`` if not available
        """
        nesting_col = self._tree_model.nesting_col()
        if not parent.isValid():
            return cast(Optional[BaseWatchableRegistryTreeStandardItem], self._tree_model.item(row_index, nesting_col))

        return cast(Optional[BaseWatchableRegistryTreeStandardItem], self._tree_model.itemFromIndex(parent).child(row_index, nesting_col))

    def _registry_changed_slot(self) -> None:
        self._resubscribe_all_rows_as_watcher()
        self.update_all_watchable_state()

    def _register_watcher_for_row(self, item: WatchableStandardItem) -> None:
        """Take the given row and create a watcher on the registry for the row"""
        value_item = self._tree_model.get_value_item(item)

        def update_val_closure(watcher_id: Union[str, int], vals: List[ValueUpdate]) -> None:
            self._update_val_callback(value_item, watcher_id, vals)

        def unwatch_closure(watcher_id: Union[str, int], server_path: str, watchable_config: sdk.WatchableConfiguration) -> None:
            pass

        watcher_id = self._get_watcher_id(item)
        self.watchable_registry.register_watcher(watcher_id, update_val_closure, unwatch_closure, ignore_duplicate=True)

    def _row_inserted_slot(self, parent: QModelIndex, row_index: int, col_index: int) -> None:
        # This slots is called for every row inserted when new rows. Only parent when existing row
        def func(item: WatchableStandardItem, visible: bool) -> None:
            self._register_watcher_for_row(item)
            if visible:
                self._watch_item(item)

        item_inserted = self._get_item(parent, row_index)
        self._tree.map_to_watchable_node(func, item_inserted)
        if isinstance(item_inserted, FolderStandardItem):
            if item_inserted.is_expanded():
                self._tree.expand(item_inserted.index())

    def _row_about_to_be_removed_slot(self, parent: QModelIndex, first_row_index: int, last_row_index: int) -> None:
        # This slot is called only on the node removed, not on the children.
        def func(item: WatchableStandardItem, visible: bool) -> None:
            watcher_id = self._get_watcher_id(item)
            try:
                # Unregistering causes an unwatch of all watched items.
                # In this component, each watcher has a single watched item
                self.watchable_registry.unregister_watcher(watcher_id)
            except WatcherNotFoundError:
                # Should not happen (hopefully). The registry is expected to keep the watchers even after a clear
                self.logger.error(f"Tried to unregister watcher {watcher_id}, but was not registered")

        for row_index in range(first_row_index, last_row_index + 1):
            item_removed = self._get_item(parent, row_index)
            self._tree.map_to_watchable_node(func, parent=item_removed)

    def _node_expanded_slot(self, index: QModelIndex) -> None:
        # Added at the end of the event loop because it is a queuedConnection
        # Expanding with star requires that
        self.expand_if_needed.emit()
        self.update_all_watchable_state(start_node=self._tree_model.itemFromIndex(index.siblingAtColumn(self._tree_model.nesting_col())))

    def _node_collapsed_slot(self, index: QModelIndex) -> None:
        self.update_all_watchable_state(start_node=self._tree_model.itemFromIndex(index.siblingAtColumn(self._tree_model.nesting_col())))

    def _row_moved_slot(self, src_parent: QModelIndex, src_row: int, src_col: int, dest_parent: QModelIndex, dst_row: int) -> None:
        self.update_all_watchable_state(start_node=self._tree_model.itemFromIndex(dest_parent.siblingAtColumn(self._tree_model.nesting_col())))

    def _watch_item(self, item: WatchableStandardItem) -> None:
        """Internal function registering a tree line from the watchable registry"""
        watcher_id = self._get_watcher_id(item)
        if self.logger.isEnabledFor(logging.DEBUG):  # pragma: no cover
            self.logger.debug(f"Watching item {item.fqn} (watcher ID = {watcher_id})")
        try:
            self.watchable_registry.watch_fqn(watcher_id, item.fqn)
        except WatchableRegistryNodeNotFoundError:
            # we tolerate because we could simply try to watch to see if the watchable is available.
            # It might not if the server is gone or presently downloading data
            self.logger.debug(f"Cannot watch {item.fqn}. Does not exist")

    def _unwatch_item(self, item: WatchableStandardItem, quiet: bool = True) -> None:
        """Internal function unregistering a tree line from the watchable registry"""
        watcher_id = self._get_watcher_id(item)
        if self.logger.isEnabledFor(logging.DEBUG):  # pragma: no cover
            self.logger.debug(f"Unwatching item {item.fqn} (watcher ID = {watcher_id})")
        try:
            self.watchable_registry.unwatch_fqn(watcher_id, item.fqn)
        except WatchableRegistryNodeNotFoundError:
            # We tolerate because a race condition could cause this if the server dies while the GUI is working
            # Should not happen normally
            self.logger.debug(f"Cannot unwatch {item.fqn}. Does not exist")
            if not quiet:
                raise

    def _get_watcher_id(self, item: WatchableStandardItem) -> int:
        return self._tree_model.get_watcher_id(item)

    def _resubscribe_all_rows_as_watcher(self) -> None:
        """Iterate all watchable row in the tree and (re)subscribe them as watchers"""
        def subscribe_func(item: WatchableStandardItem, visible: bool) -> None:
            self._register_watcher_for_row(item)
        self._tree.map_to_watchable_node(subscribe_func)

    def update_all_watchable_state(self, start_node: Optional[BaseWatchableRegistryTreeStandardItem] = None) -> None:
        """Make a watchable row watch or unwatch the item they refer to based on their visibility to the user"""
        def update_func(item: WatchableStandardItem, visible: bool) -> None:
            if visible:
                self._watch_item(item)
            else:
                self._unwatch_item(item)
            self._tree_model.update_row_state(item)

        self._tree.map_to_watchable_node(update_func, start_node)

    def _update_val_callback(self, item: ValueStandardItem, watcher_id: Union[str, int], vals: List[ValueUpdate]) -> None:
        """The function called when we receive value updates from the server"""
        assert len(vals) > 0
        can_update = True
        nesting_col = self._tree_model.nesting_col()
        if self._tree.state() == WatchableTreeWidget.State.EditingState:
            if item.index().siblingAtColumn(nesting_col) == self._tree.currentIndex().siblingAtColumn(nesting_col):
                can_update = False  # Don't change the content. The user is writing something

        if can_update:
            item.set_value(vals[-1].value)

    def _value_written_slot(self, fqn: str, value: Union[str, int, float, bool]) -> None:
        """The QT slot called when the user input a new value in a value field"""
        def ui_callback(exception: Optional[Exception]) -> None:
            if exception is not None:
                self.logger.warning(f"Failed to write {fqn}. {exception}")
                self.logger.debug(tools.format_exception(exception))

        if not isinstance(value, (int, float, bool, str)):
            raise ValueError(f"Cannot write the value of {fqn}. Value is of the wrong type: {value.__class__.__name__}")
        # No need to parse strings. The server auto-converts
        # Supports : Number as strings. Hexadecimal with 0x prefix, true/false, etc.
        self.server_manager.qt_write_watchable_value(fqn, value, ui_callback)
