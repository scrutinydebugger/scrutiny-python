#    varlist_component.py
#        A component that shows the content of the watcahble index, a copy og what's available
#        on the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from typing import Dict, Any, List, cast, Optional

from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon
from PySide6.QtCore import QModelIndex, Qt

from scrutiny.gui.core.watchable_index import ParsedFullyQualifiedName
from scrutiny.gui import assets
from scrutiny.gui.widgets.multiselect_treeview import MultiSelectTreeView
from scrutiny.gui.core.watchable_index import WatchableIndexNodeContent
from scrutiny.sdk import WatchableType, WatchableConfiguration
from scrutiny.gui.dashboard_components.common.tree_items import FolderStandardItem, WatchableStandardItem, StandardItemWithFQN

LOADED_ROLE = Qt.ItemDataRole.UserRole + 1

class VarListComponent(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("treelist-96x128.png")
    _NAME = "Variable List"

    _model : QStandardItemModel
    _treeview:MultiSelectTreeView

    _var_folder:QStandardItem
    _alias_folder:QStandardItem
    _rpv_folder:QStandardItem
    _index_change_counters:Dict[WatchableType, int]

    FOLDER_ICON:QIcon
    VAR_ICON:QIcon
    RPV_ICON:QIcon
    ALIAS_ICON:QIcon

    def __init__(self, *args:Any, **kwargs:Any) -> None:
        super().__init__(*args, **kwargs)

        self.FOLDER_ICON =assets.load_icon(assets.Icons.TreeFolder)
        self.VAR_ICON =assets.load_icon(assets.Icons.TreeVar)
        self.RPV_ICON =assets.load_icon(assets.Icons.TreeRpv)
        self.ALIAS_ICON =assets.load_icon(assets.Icons.TreeAlias)

    def make_fqn(self, watchable_type:WatchableType, path:str) -> str:
        return self.server_manager.index.make_fqn(watchable_type, path)
    
    def parse_fqn(self, fqn:str) -> ParsedFullyQualifiedName:
        return self.server_manager.index.parse_fqn(fqn)

    def make_folder_item(self, name:str, fqn:str) -> QStandardItem:
        item =  FolderStandardItem(name, fqn)
        item.setEditable(False)
        item.setDragEnabled(True)
        return item

    def make_watchable_item(self, name:str, watchable:WatchableConfiguration, fqn:str) -> QStandardItem:
        item =  WatchableStandardItem(watchable.watchable_type, name, fqn)
        item.setEditable(False)
        item.setDragEnabled(True)
        return item

    def setup(self) -> None:
        layout = QVBoxLayout(self)

        self._model = QStandardItemModel(0, 3, self)
        
        self._var_folder = self.make_folder_item("Var", self.make_fqn(WatchableType.Variable, '/'))
        self._alias_folder = self.make_folder_item("Alias", self.make_fqn(WatchableType.Alias, '/'))
        self._rpv_folder = self.make_folder_item("RPV", self.make_fqn(WatchableType.RuntimePublishedValue, '/'))

        self._model.appendRow(self._var_folder)
        self._model.appendRow(self._alias_folder)
        self._model.appendRow(self._rpv_folder)
        self._model.setHorizontalHeaderLabels(['', 'Type', 'Enum'])
        self._treeview = MultiSelectTreeView()
        self._treeview.setUniformRowHeights(True)   # Documentation says it helps performance
        self._treeview.setAnimated(False)
        
        self._treeview.setModel(self._model)
        layout.addWidget(self._treeview)

        self.reload_model([WatchableType.RuntimePublishedValue, WatchableType.Alias, WatchableType.Variable])
        self._index_change_counters = self.server_manager.index.get_change_counters()

        self.server_manager.signals.index_changed.connect(self.index_changed_slot)
        self._treeview.expanded.connect(self.node_expanded_slot)
        
    
    def node_expanded_slot(self, index:QModelIndex):
        #Lazy loading implementation
        item = cast(StandardItemWithFQN, index.model().itemFromIndex(index))
        for row in range(item.rowCount()):
            child = cast(StandardItemWithFQN, item.child(row, 0))
            if not child.data(LOADED_ROLE):
                parsed_fqn = self.parse_fqn(child.fqn)
                self.add_items_recursive(child, parsed_fqn.watchable_type, parsed_fqn.path, max_level=0)

    
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
        if WatchableType.RuntimePublishedValue in watchable_types:
            self._rpv_folder.removeRows(0, self._rpv_folder.rowCount())
            # max_level=0 has we do lazy laoding
            self.add_items_recursive(self._rpv_folder, WatchableType.RuntimePublishedValue, '/', max_level=0)
        
        if WatchableType.Alias in watchable_types:
            self._alias_folder.removeRows(0, self._alias_folder.rowCount())
            # max_level=0 has we do lazy laoding
            self.add_items_recursive(self._alias_folder, WatchableType.Alias, '/', max_level=0)
        
        if WatchableType.Variable in watchable_types:
            self._var_folder.removeRows(0, self._var_folder.rowCount())
            # max_level=0 has we do lazy laoding
            self.add_items_recursive(self._var_folder, WatchableType.Variable, '/', max_level=0)

    def make_watchable_row(self, item:QStandardItem, watchable_config:WatchableConfiguration) -> List[QStandardItem]:
        typecol = QStandardItem(watchable_config.datatype.name)
        typecol.setEditable(False)
        if watchable_config.enum is not None:
            enumcol = QStandardItem(watchable_config.enum.name)
            enumcol.setEditable(False)
            return (item, typecol, enumcol)
        else:
            return (item, typecol)
    
    def add_items_recursive(self, parent:QStandardItem, watchable_type:WatchableType, path:str, max_level:Optional[int]=None, level:int=0) -> None:
        parent.setData(True, LOADED_ROLE)
        content = self.server_manager.index.read(watchable_type, path)
        if path.endswith('/'):
            path=path[:-1]

        if isinstance(content, WatchableIndexNodeContent):
            for name in content.subtree:
                subtree_path = f'{path}/{name}'
                row = self.make_folder_item(name, self.make_fqn(watchable_type, subtree_path))
                parent.appendRow(row)
                if max_level is None or level < max_level:
                    self.add_items_recursive(row, watchable_type, subtree_path, max_level=max_level, level=level+1)
            
            for name, watchable_config in content.watchables.items():
                wathcable_path = f'{path}/{name}'
                item = self.make_watchable_item(name, watchable_config, self.make_fqn(watchable_type, wathcable_path))
                parent.appendRow(self.make_watchable_row(item, watchable_config))

    def teardown(self) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        return {}

    def load_state(self, state: Dict[Any, Any]) -> None:
        pass
