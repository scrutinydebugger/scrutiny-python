#    varlist_component.py
#        A component that shows the content of the watcahble index, a copy og what's available
#        on the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from typing import Dict, Any, List, cast, Optional, Sequence

from PySide6.QtWidgets import QVBoxLayout, QWidget
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtCore import QModelIndex, QMimeData

from scrutiny.gui import assets
from scrutiny.gui.core.watchable_index import   WatchableIndex
from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from scrutiny.gui.dashboard_components.common.scrutiny_drag_data import ScrutinyDragData, SingleWatchableDescriptor
from scrutiny.gui.dashboard_components.common.watchable_tree import (
    BaseWatchableIndexTreeStandardItem, 
    WatchableStandardItem,
    WatchableTreeModel, 
    NodeSerializableData,
    WatchableTreeWidget
    )

from scrutiny.sdk import WatchableType, WatchableConfiguration

class VarListComponentTreeModel(WatchableTreeModel):
    """An extension of the data model used by Watchable Trees dedicated for the Variable List Component
    Mainly handles drag&drop logic
    """

    def get_watchable_columns(self,  watchable_config:Optional[WatchableConfiguration]=None) -> List[QStandardItem]:
        if watchable_config is None:
            return []
        typecol = QStandardItem(watchable_config.datatype.name)
        typecol.setEditable(False)
        if watchable_config.enum is not None:
            enumcol = QStandardItem(watchable_config.enum.name)
            enumcol.setEditable(False)
            return [ typecol, enumcol ]
        else:
            return [ typecol]

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        indexes_without_nested_values = self.remove_nested_indexes(indexes)
        data:Optional[QMimeData] = None

        # There is a special case for single watchables. They can be dropped in outside of trees, 
        # We prioritize them.
        if len(indexes_without_nested_values) == 1:
            single_item = cast(BaseWatchableIndexTreeStandardItem, self.itemFromIndex(list(indexes_without_nested_values)[0]))
            if single_item is not None:
                if isinstance(single_item, WatchableStandardItem):
                    data = SingleWatchableDescriptor(text=single_item.text(), fqn=single_item.fqn).to_mime()
        
        # We do not have a single element, resort to pass the tree data, 
        # Can only be dropped in a watch window
        if data is None:
            # Make a serialized version of the data that will be passed a text
            serializable_items:List[NodeSerializableData] = []
            
            for index in indexes_without_nested_values:
                item = self.itemFromIndex(index)
                if isinstance(item, BaseWatchableIndexTreeStandardItem): # Only keep column 0 
                    serializable_items.append(item.to_serialized_data())
            
            data = ScrutinyDragData(type=ScrutinyDragData.DataType.WatchableTreeNodesTiedToIndex, data_copy=serializable_items).to_mime()
            assert data is not None
        return data
    


class VarlistComponentTreeWidget(WatchableTreeWidget):
    def __init__(self, parent: QWidget, model:VarListComponentTreeModel) -> None:
        super().__init__(parent, model)
        self.set_header_labels(['', 'Type', 'Enum'])

class VarListComponent(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("treelist-96x128.png")
    _NAME = "Variable List"

    _tree:VarlistComponentTreeWidget
    _tree_model:VarListComponentTreeModel

    _var_folder:BaseWatchableIndexTreeStandardItem
    _alias_folder:BaseWatchableIndexTreeStandardItem
    _rpv_folder:BaseWatchableIndexTreeStandardItem
    _index_change_counters:Dict[WatchableType, int]

    def setup(self) -> None:
        layout = QVBoxLayout(self)

        self._tree_model = VarListComponentTreeModel(self, watchable_index=self.server_manager.index)
        self._tree = VarlistComponentTreeWidget(self, self._tree_model)
        
        var_row = self._tree_model.make_folder_row("Var", WatchableIndex.make_fqn(WatchableType.Variable, '/'), editable=False)
        alias_row = self._tree_model.make_folder_row("Alias", WatchableIndex.make_fqn(WatchableType.Alias, '/'), editable=False)
        rpv_row = self._tree_model.make_folder_row("RPV", WatchableIndex.make_fqn(WatchableType.RuntimePublishedValue, '/'), editable=False)

        self._tree.get_model().appendRow(var_row)
        self._tree.get_model().appendRow(alias_row)
        self._tree.get_model().appendRow(rpv_row)
        self._tree.setDragDropMode(self._tree.DragDropMode.DragOnly)

        self._var_folder = cast(BaseWatchableIndexTreeStandardItem, var_row[0])
        self._alias_folder = cast(BaseWatchableIndexTreeStandardItem, alias_row[0])
        self._rpv_folder = cast(BaseWatchableIndexTreeStandardItem, rpv_row[0])
        
        layout.addWidget(self._tree)

        self.reload_model([WatchableType.RuntimePublishedValue, WatchableType.Alias, WatchableType.Variable])
        self._index_change_counters = self.server_manager.index.get_change_counters()

        self.server_manager.signals.index_changed.connect(self.index_changed_slot)
        self._tree.expanded.connect(self.node_expanded_slot)
        
    
    def node_expanded_slot(self, index:QModelIndex) -> None:
        #Lazy loading implementation
        item = cast(BaseWatchableIndexTreeStandardItem, cast(QStandardItemModel, index.model()).itemFromIndex(index))
        for row in range(item.rowCount()):
            child = cast(BaseWatchableIndexTreeStandardItem, item.child(row, 0))
            if not child.is_loaded():
                fqn = child.fqn
                assert fqn is not None  # All data is coming from the index, so it has an Fully Qualified Name
                parsed_fqn = WatchableIndex.parse_fqn(fqn)
                self._tree_model.lazy_load(child, parsed_fqn.watchable_type, parsed_fqn.path)
        
        self._tree.expand_first_column_to_content()

    
    def index_changed_slot(self) -> None:
        index_change_counters = self.server_manager.index.get_change_counters()
        # Identify all the types that changed since the last model update
        types_to_reload = []
        for wt, count in index_change_counters.items():
            if count != self._index_change_counters[wt]:
                types_to_reload.append(wt)
        self.reload_model(types_to_reload)
        self._index_change_counters = index_change_counters


    def reload_model(self, watchable_types:List[WatchableType]) -> None:
        # reload first level with max_level=0 as we do lazy loading
        if WatchableType.RuntimePublishedValue in watchable_types:
            self._rpv_folder.removeRows(0, self._rpv_folder.rowCount())
            self._tree_model.lazy_load(self._rpv_folder, WatchableType.RuntimePublishedValue, '/')
        
        if WatchableType.Alias in watchable_types:
            self._alias_folder.removeRows(0, self._alias_folder.rowCount())
            self._tree_model.lazy_load(self._alias_folder, WatchableType.Alias, '/')
        
        if WatchableType.Variable in watchable_types:
            self._var_folder.removeRows(0, self._var_folder.rowCount())
            self._tree_model.lazy_load(self._var_folder, WatchableType.Variable, '/')
        



    def teardown(self) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        return {}

    def load_state(self, state: Dict[Any, Any]) -> None:
        pass
