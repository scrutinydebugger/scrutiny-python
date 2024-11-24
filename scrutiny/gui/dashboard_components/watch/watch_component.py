#    watch_component.py
#        A component to look at the value of watchable items broadcast by the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from typing import Dict, Any, List

from PySide6.QtWidgets import QVBoxLayout, QLabel, QWidget
from PySide6.QtGui import QDragMoveEvent, QDropEvent, QDragEnterEvent

from scrutiny.gui import assets
from scrutiny.gui.core.watchable_index import ParsedFullyQualifiedName
from scrutiny.gui.core.watchable_index import WatchableIndexNodeContent
from scrutiny.sdk import WatchableType, WatchableConfiguration
from scrutiny.gui.dashboard_components.common.watchable_tree import BaseWatchableIndexTreeStandardItem, WatchableTreeWidget
import json

class WatchComponentTreeWidget(WatchableTreeWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(self.DragDropMode.DragDrop)

    def dragEnterEvent(self, event:QDragEnterEvent) -> None:
        print(f"dragEnterEvent : {event}")
        event.acceptProposedAction()
        pass

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
       # print(f"dragMoveEvent : {event}")
        pass
        
    def dropEvent(self, event:QDropEvent) -> None:
        mimedata = event.mimeData()
        if not mimedata.hasText():
            event.ignore()
            return
        mimestr = event.mimeData().data('text/plain').toStdString()
        try:
            json_decoded = json.loads(mimestr)
        except json.JSONDecodeError:
            event.ignore()
            return 
        
        try:
            if 'source' in json_decoded:
                if json_decoded['source'] == 'varlist':
                    assert 'data' in json_decoded
                    self.handle_drop_varlist(event, json_decoded['data'])
                elif json_decoded['source'] == 'watch':
                    pass
                else:
                    pass
        except AssertionError:
            event.ignore()
            return


    def handle_drop_varlist(self, event:QDropEvent, data:List[BaseWatchableIndexTreeStandardItem]) -> None:
        assert isinstance(data, list)
        for serializable_item in data:
            print(serializable_item)

class WatchComponent(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("eye-96x128.png")
    _NAME = "Watch Window"

    _HEADERS = ['', 'Value']
    _tree:WatchComponentTreeWidget

    def setup(self) -> None:
        self._tree = WatchComponentTreeWidget()

        layout = QVBoxLayout(self)
        layout.addWidget(self._tree)
        
    def teardown(self) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        raise NotImplementedError()

    def load_state(self, state: Dict[Any, Any]) -> None:
        raise NotImplementedError()
