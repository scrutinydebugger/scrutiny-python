#    varlist_component.py
#        A component that shows the content of the watcahble index, a copy og what's available
#        on the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from typing import Dict, Any, List

from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon

from scrutiny.gui import assets
from scrutiny.gui.widgets.multiselect_treeview import MultiSelectTreeView
from scrutiny.gui.core.watchable_index import WatchableIndexNodeContent
from scrutiny.sdk import WatchableType, WatchableConfiguration


        
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

        self.FOLDER_ICON = QIcon(assets.load_pixmap("folder-16x16.png"))
        self.VAR_ICON = QIcon(assets.load_pixmap("var-16x16.png"))
        self.RPV_ICON = QIcon(assets.load_pixmap("rpv-16x16.png"))
        self.ALIAS_ICON = QIcon(assets.load_pixmap("alias-16x16.png"))

    def get_watchable_icon(self, wt:WatchableType) -> QIcon:
        if wt == WatchableType.Variable:
            return self.VAR_ICON
        if wt == WatchableType.Alias:
            return self.ALIAS_ICON
        if wt == WatchableType.RuntimePublishedValue:
            return self.RPV_ICON
        raise NotImplementedError(f"Unsupported icon for {wt}")

    def make_folder_item(self, name:str, fqn:str) -> QStandardItem:
        item =  QStandardItem(self.FOLDER_ICON, name)
        item.setData(fqn)
        item.setEditable(False)
        item.setDragEnabled(True)
        return item

    def make_watchable_item(self, name:str, watchable:WatchableConfiguration, fqn:str) -> QStandardItem:
        item =  QStandardItem(self.get_watchable_icon(watchable.watchable_type), name)
        item.setData(fqn)
        item.setEditable(False)
        item.setDragEnabled(True)
        return item

    def setup(self) -> None:
        layout = QVBoxLayout(self)

        self._model = QStandardItemModel(0, 3, self)
        
        self._var_folder = self.make_folder_item("Var", self.server_manager.index.make_fqn(WatchableType.Variable, '/'))
        self._alias_folder = self.make_folder_item("Alias", self.server_manager.index.make_fqn(WatchableType.Alias, '/'))
        self._rpv_folder = self.make_folder_item("RPV", self.server_manager.index.make_fqn(WatchableType.RuntimePublishedValue, '/'))

        self._model.appendRow(self._var_folder)
        self._model.appendRow(self._alias_folder)
        self._model.appendRow(self._rpv_folder)
        self._treeview = MultiSelectTreeView()
        self._treeview.setUniformRowHeights(True)   # Doc says it helps performance
        self._treeview.setAnimated(False)
        
        self._treeview.setModel(self._model)
        layout.addWidget(self._treeview)

        self.reload_model([WatchableType.RuntimePublishedValue, WatchableType.Alias, WatchableType.Variable])
        self._index_change_counters = self.server_manager.index.get_change_counters()

        self.server_manager.signals.index_changed.connect(self.index_changed_slot)
    
    def index_changed_slot(self) -> None:
        index_change_counters = self.server_manager.index.get_change_counters()
        types_to_reload = []
        for wt, count in index_change_counters.items():
            if count != self._index_change_counters[wt]:
                types_to_reload.append(wt)
        self.reload_model(types_to_reload)
        self._index_change_counters = index_change_counters



    def reload_model(self, watchable_types:List[WatchableType]) -> None:
        if WatchableType.RuntimePublishedValue in watchable_types:
            self._rpv_folder.removeRows(0, self._rpv_folder.rowCount())
            self.add_items_recursive(self._rpv_folder, WatchableType.RuntimePublishedValue, '/')
        
        if WatchableType.Alias in watchable_types:
            self._alias_folder.removeRows(0, self._alias_folder.rowCount())
            self.add_items_recursive(self._alias_folder, WatchableType.Alias, '/')
        
        if WatchableType.Variable in watchable_types:
            self._var_folder.removeRows(0, self._var_folder.rowCount())
            self.add_items_recursive(self._var_folder, WatchableType.Variable, '/')

    
    def add_items_recursive(self, parent:QStandardItem, watchable_type:WatchableType, path:str) -> None:
        
        content = self.server_manager.index.read(watchable_type, path)

        if isinstance(content, WatchableIndexNodeContent):
            for name in content.subtree:
                row = self.make_folder_item(name, path)
                parent.appendRow(row)
                self.add_items_recursive(row, watchable_type, path + '/' + name)
            
            for name, watchable_config in content.watchables.items():
                item = self.make_watchable_item(name, watchable_config, self.server_manager.index.make_fqn(watchable_type, path))
                parent.appendRow([item, QStandardItem(watchable_config.datatype.name)])

    def teardown(self) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        raise NotImplementedError()

    def load_state(self, state: Dict[Any, Any]) -> None:
        raise NotImplementedError()
