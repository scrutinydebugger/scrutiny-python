#    varlist_component.py
#        A component that shows the content of the watcahble index, a copy og what's available
#        on the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from typing import Dict, Any, List, cast, Optional

from PySide6.QtWidgets import QVBoxLayout, QHeaderView
from PySide6.QtGui import QStandardItem, QColor, QStandardItemModel
from PySide6.QtCore import QModelIndex, Qt

from scrutiny.gui import assets
from scrutiny.gui.core.watchable_index import ParsedFullyQualifiedName, WatchableIndexNodeContent
from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from scrutiny.gui.dashboard_components.common.watchable_tree import BaseWatchableIndexTreeStandardItem, WatchableTreeWidget

from scrutiny.sdk import WatchableType, WatchableConfiguration

LOADED_ROLE = Qt.ItemDataRole.UserRole + 1

class VarListComponent(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("treelist-96x128.png")
    _NAME = "Variable List"

    _HEADERS = ['', 'Type', 'Enum']
    _tree:WatchableTreeWidget

    _var_folder:QStandardItem
    _alias_folder:QStandardItem
    _rpv_folder:QStandardItem
    _index_change_counters:Dict[WatchableType, int]


    def make_fqn(self, watchable_type:WatchableType, path:str) -> str:
        return self.server_manager.index.make_fqn(watchable_type, path)
    
    def parse_fqn(self, fqn:str) -> ParsedFullyQualifiedName:
        return self.server_manager.index.parse_fqn(fqn)


    def setup(self) -> None:
        layout = QVBoxLayout(self)

        self._tree = WatchableTreeWidget(self)
        
        var_row = self._tree.make_folder_row("Var", self.make_fqn(WatchableType.Variable, '/'), editable=False)
        alias_row = self._tree.make_folder_row("Alias", self.make_fqn(WatchableType.Alias, '/'), editable=False)
        rpv_row = self._tree.make_folder_row("RPV", self.make_fqn(WatchableType.RuntimePublishedValue, '/'), editable=False)

        self._tree.get_model().appendRow(var_row)
        self._tree.get_model().appendRow(alias_row)
        self._tree.get_model().appendRow(rpv_row)
        self._tree.set_header_labels(self._HEADERS)

        self._var_folder = var_row[0]
        self._alias_folder = alias_row[0]
        self._rpv_folder = rpv_row[0]
        
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
            if not child.data(LOADED_ROLE):
                parsed_fqn = self.parse_fqn(child.fqn)
                self.add_items_recursive(child, parsed_fqn.watchable_type, parsed_fqn.path, max_level=0)
        

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
            self.add_items_recursive(self._rpv_folder, WatchableType.RuntimePublishedValue, '/', max_level=0)
        
        if WatchableType.Alias in watchable_types:
            self._alias_folder.removeRows(0, self._alias_folder.rowCount())
            self.add_items_recursive(self._alias_folder, WatchableType.Alias, '/', max_level=0)
        
        if WatchableType.Variable in watchable_types:
            self._var_folder.removeRows(0, self._var_folder.rowCount())
            self.add_items_recursive(self._var_folder, WatchableType.Variable, '/', max_level=0)
        
    def get_watchable_columns(self,  watchable_config:WatchableConfiguration) -> List[QStandardItem]:
        typecol = QStandardItem(watchable_config.datatype.name)
        typecol.setEditable(False)
        if watchable_config.enum is not None:
            enumcol = QStandardItem(watchable_config.enum.name)
            enumcol.setEditable(False)
            return [ typecol, enumcol ]
        else:
            return [ typecol]
        
    
    def add_items_recursive(self, parent:QStandardItem, watchable_type:WatchableType, path:str, max_level:Optional[int]=None, level:int=0) -> None:
        parent.setData(True, LOADED_ROLE)
        content = self.server_manager.index.read(watchable_type, path)
        if path.endswith('/'):
            path=path[:-1]

        if isinstance(content, WatchableIndexNodeContent):
            for name in content.subtree:
                subtree_path = f'{path}/{name}'
                row = self._tree.make_folder_row(
                    name=name,
                    fqn=self.make_fqn(watchable_type, subtree_path),
                    editable=False
                )
                parent.appendRow(row)

                if max_level is None or level < max_level:
                    self.add_items_recursive(row[0], watchable_type, subtree_path, max_level=max_level, level=level+1)
            
            for name, watchable_config in content.watchables.items():
                watchable_path = f'{path}/{name}'
                row = self._tree.make_watchable_row(
                    name = name, 
                    watchable_config = watchable_config, 
                    fqn = self.make_fqn(watchable_type, watchable_path), 
                    editable=False,
                    extra_columns=self.get_watchable_columns(watchable_config)
                )
                parent.appendRow(row)


    def teardown(self) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        return {}

    def load_state(self, state: Dict[Any, Any]) -> None:
        pass
