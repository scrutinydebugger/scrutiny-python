#    varlist_component.py
#        A component that shows the content of the watchable registry, a copy og what's available
#        on the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = [
    'VarListComponentTreeModel',
    'VarlistComponentTreeWidget',
    'VarListComponent',
]

from PySide6.QtWidgets import QVBoxLayout, QWidget
from PySide6.QtGui import QStandardItem, QStandardItemModel, QIcon
from PySide6.QtCore import QModelIndex, QMimeData, Qt

from scrutiny.gui import assets
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.gui.core.scrutiny_drag_data import ScrutinyDragData
from scrutiny.gui.components.globals.base_global_component import ScrutinyGUIBaseGlobalComponent
from scrutiny.gui.widgets.watchable_tree import (
    BaseWatchableRegistryTreeStandardItem,
    WatchableTreeModel,
    NodeSerializableData,
    WatchableTreeWidget
)

from scrutiny.sdk import WatchableType, WatchableConfiguration
from scrutiny.tools.typing import *


class VarListComponentTreeModel(WatchableTreeModel):
    """An extension of the data model used by Watchable Trees dedicated for the Variable List Component
    Mainly handles drag&drop logic
    """

    def get_watchable_extra_columns(self, watchable_config: Optional[WatchableConfiguration] = None) -> List[QStandardItem]:
        """Define the columns to add for a watchable (leaf) row. Called by the parent class"""
        if watchable_config is None:
            return []
        typecol = QStandardItem(watchable_config.datatype.name)
        typecol.setEditable(False)
        if watchable_config.enum is not None:
            enumcol = QStandardItem(watchable_config.enum.name)
            enumcol.setEditable(False)
            return [typecol, enumcol]
        else:
            return [typecol]

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        """Generate the mimeData when a drag&drop starts"""

        indexes_without_nested_values = self.remove_nested_indexes(indexes)
        items = [cast(Optional[BaseWatchableRegistryTreeStandardItem], self.itemFromIndex(x)) for x in indexes_without_nested_values]

        # We first start use to most supported format of watchable list.
        drag_data = self.make_watchable_list_dragdata_if_possible(items)

        # If the item selection had folders in it, we can't make a WatchableList mime data.
        # Let's make a WatchableTreeNodesTiedToRegistry instead, can only be dropped in a watch window
        if drag_data is None:
            # Make a serialized version of the data that will be passed a text
            serializable_items: List[NodeSerializableData] = []

            for index in indexes_without_nested_values:
                item = self.itemFromIndex(index)
                if isinstance(item, BaseWatchableRegistryTreeStandardItem):  # Only keep column 0
                    serializable_items.append(item.to_serialized_data())

            drag_data = ScrutinyDragData(type=ScrutinyDragData.DataType.WatchableTreeNodesTiedToRegistry, data_copy=serializable_items)
        mime_data = drag_data.to_mime()

        assert mime_data is not None
        return mime_data

    def find_item_by_fqn(self, fqn: str) -> Optional[BaseWatchableRegistryTreeStandardItem]:
        """Find an item in the model using the Watchable registry.
        In this model, each node has a Fully Qualified Name defined and data is organized 
        following the registry structure.

        :param fqn: The Fully Qualified Name to search for

        :return:
        """

        # This method is mainly used by unit tests.
        # We do not expect the application to query this data model
        # with a WatchableRegistry path, it will query the registry directly.

        parsed = WatchableRegistry.FQN.parse(fqn)
        path_parts = WatchableRegistry.split_path(parsed.path)
        if len(path_parts) == 0:
            return None

        empty_fqn = WatchableRegistry.FQN.make(parsed.watchable_type, '')
        first_fqn = WatchableRegistry.FQN.extend(empty_fqn, [path_parts.pop(0)])

        def find_item_recursive(
                item: BaseWatchableRegistryTreeStandardItem,
                wanted_fqn: str,
                remaining_parts: List[str]) -> Optional[BaseWatchableRegistryTreeStandardItem]:

            for row_index in range(item.rowCount()):
                child = cast(Optional[BaseWatchableRegistryTreeStandardItem], item.child(row_index, 0))
                if child is None:
                    continue
                if child.fqn is None:
                    continue

                if WatchableRegistry.FQN.is_equal(child.fqn, wanted_fqn):
                    if len(remaining_parts) == 0:
                        return child
                    new_fqn = WatchableRegistry.FQN.extend(wanted_fqn, [remaining_parts.pop(0)])
                    return find_item_recursive(child, new_fqn, remaining_parts.copy())

            return None

        # For each row at the root, we launch the recursive function if the watchable type matches
        for i in range(self.rowCount()):
            start_node = cast(Optional[BaseWatchableRegistryTreeStandardItem], self.item(i, 0))
            if start_node is not None:
                if start_node.fqn is not None:
                    if WatchableRegistry.FQN.parse(start_node.fqn).watchable_type == parsed.watchable_type:
                        result = find_item_recursive(start_node, first_fqn, path_parts.copy())
                        if result is not None:
                            return result
        return None


class VarlistComponentTreeWidget(WatchableTreeWidget):
    def __init__(self, parent: QWidget, model: VarListComponentTreeModel) -> None:
        super().__init__(parent, model)
        self.set_header_labels(['', 'Type', 'Enum'])
        self.setDragDropMode(self.DragDropMode.DragOnly)
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)

    def model(self) -> VarListComponentTreeModel:
        return cast(VarListComponentTreeModel, super().model())


class VarListComponent(ScrutinyGUIBaseGlobalComponent):
    instance_name: str

    _NAME = "Variable List"
    _TYPE_ID = "varlist"

    _tree: VarlistComponentTreeWidget
    _tree_model: VarListComponentTreeModel

    _var_folder: BaseWatchableRegistryTreeStandardItem
    _alias_folder: BaseWatchableRegistryTreeStandardItem
    _rpv_folder: BaseWatchableRegistryTreeStandardItem
    _index_change_counters: Dict[WatchableType, int]

    @classmethod
    def get_icon(cls) -> QIcon:
        return scrutiny_get_theme().load_medium_icon(assets.Icons.VarList)

    def setup(self) -> None:
        layout = QVBoxLayout(self)

        self._tree_model = VarListComponentTreeModel(self, watchable_registry=self.watchable_registry)
        self._tree = VarlistComponentTreeWidget(self, self._tree_model)

        var_row = self._tree_model.make_folder_row("Var", WatchableRegistry.FQN.make(WatchableType.Variable, '/'), editable=False)
        alias_row = self._tree_model.make_folder_row("Alias", WatchableRegistry.FQN.make(WatchableType.Alias, '/'), editable=False)
        rpv_row = self._tree_model.make_folder_row("RPV", WatchableRegistry.FQN.make(WatchableType.RuntimePublishedValue, '/'), editable=False)

        self._tree.model().appendRow(var_row)
        self._tree.model().appendRow(alias_row)
        self._tree.model().appendRow(rpv_row)

        self._var_folder = cast(BaseWatchableRegistryTreeStandardItem, var_row[0])
        self._alias_folder = cast(BaseWatchableRegistryTreeStandardItem, alias_row[0])
        self._rpv_folder = cast(BaseWatchableRegistryTreeStandardItem, rpv_row[0])

        layout.addWidget(self._tree)

        self.reload_model([WatchableType.RuntimePublishedValue, WatchableType.Alias, WatchableType.Variable])
        self._index_change_counters = self.watchable_registry.get_change_counters()

        self.server_manager.signals.registry_changed.connect(self.registry_changed_slot)
        self._tree.expanded.connect(self.node_expanded_slot)

    def node_expanded_slot(self, index: QModelIndex) -> None:
        # Lazy loading implementation
        item = cast(BaseWatchableRegistryTreeStandardItem, cast(QStandardItemModel, index.model()).itemFromIndex(index))
        for row in range(item.rowCount()):
            child = cast(BaseWatchableRegistryTreeStandardItem, item.child(row, 0))
            if not child.is_loaded():
                fqn = child.fqn
                assert fqn is not None  # All data is coming from the index, so it has an Fully Qualified Name
                parsed_fqn = WatchableRegistry.FQN.parse(fqn)
                self._tree_model.lazy_load(child, parsed_fqn.watchable_type, parsed_fqn.path)

        self._tree.expand_first_column_to_content()

    def registry_changed_slot(self) -> None:
        """Called when the server manager finishes downloading the server watchable list and update the registry"""
        index_change_counters = self.watchable_registry.get_change_counters()
        # Identify all the types that changed since the last model update
        types_to_reload = []
        for wt, count in index_change_counters.items():
            if count != self._index_change_counters[wt]:
                types_to_reload.append(wt)
        self.reload_model(types_to_reload)
        self._index_change_counters = index_change_counters

    def reload_model(self, watchable_types: List[WatchableType]) -> None:
        """Fully reload to model

        :param watchable_types: The list of watchable types to reload
        """

        # reload first level with max_level=0 as we do lazy loading
        # Collapse root node to avoid lazy loading glitch that require to collapse/reexpand to load new data
        if WatchableType.RuntimePublishedValue in watchable_types:
            self._rpv_folder.removeRows(0, self._rpv_folder.rowCount())
            self._tree.collapse(self._rpv_folder.index())
            self._tree_model.lazy_load(self._rpv_folder, WatchableType.RuntimePublishedValue, '/')

        if WatchableType.Alias in watchable_types:
            self._alias_folder.removeRows(0, self._alias_folder.rowCount())
            self._tree.collapse(self._alias_folder.index())
            self._tree_model.lazy_load(self._alias_folder, WatchableType.Alias, '/')

        if WatchableType.Variable in watchable_types:
            self._var_folder.removeRows(0, self._var_folder.rowCount())
            self._tree.collapse(self._var_folder.index())
            self._tree_model.lazy_load(self._var_folder, WatchableType.Variable, '/')

    def teardown(self) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        return {}

    def load_state(self, state: Dict[Any, Any]) -> bool:
        return True
