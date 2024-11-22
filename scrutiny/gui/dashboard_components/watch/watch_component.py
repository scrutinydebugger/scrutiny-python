#    watch_component.py
#        A component to look at the value of watchable items broadcast by the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from typing import Dict, Any

from PySide6.QtWidgets import QVBoxLayout, QLabel

from scrutiny.gui import assets
from scrutiny.gui.core.watchable_index import ParsedFullyQualifiedName
from scrutiny.gui.widgets.multiselect_treeview import MultiSelectTreeView
from scrutiny.gui.core.watchable_index import WatchableIndexNodeContent
from scrutiny.sdk import WatchableType, WatchableConfiguration
from scrutiny.gui.dashboard_components.common.watchable_tree import FolderStandardItem, WatchableStandardItem, BaseWatchableIndexTreeStandardItem
from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon


class WatchComponent(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("eye-96x128.png")
    _NAME = "Watch Window"

    _HEADERS = ['', 'Value']
    _model : QStandardItemModel
    _treeview:MultiSelectTreeView

    def setup(self) -> None:
        self._model = QStandardItemModel(0, len(self._HEADERS), self)
        self._model.setHorizontalHeaderLabels(self._HEADERS)
        self._treeview = MultiSelectTreeView()
        self._treeview.setUniformRowHeights(True)   # Documentation says it helps performance
        self._treeview.setAnimated(False)
        self._treeview.setModel(self._model)

        layout = QVBoxLayout(self)
        layout.addWidget(self._treeview)
        

    def teardown(self) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        raise NotImplementedError()

    def load_state(self, state: Dict[Any, Any]) -> None:
        raise NotImplementedError()
