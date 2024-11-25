#    watch_component.py
#        A component to look at the value of watchable items broadcast by the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from typing import Dict, Any, List, Union, Optional, cast, Sequence

from PySide6.QtCore import QMimeData, QModelIndex, QPersistentModelIndex, Qt, QByteArray
from PySide6.QtWidgets import QVBoxLayout, QWidget
from PySide6.QtGui import QDragMoveEvent, QDropEvent, QDragEnterEvent, QKeyEvent, QStandardItem

from scrutiny.gui import assets
from scrutiny.gui.core.watchable_index import WatchableIndexError
from scrutiny.gui.dashboard_components.common.watchable_tree import WatchableTreeWidget, WatchableTreeModel, NodeSerializableData, FolderStandardItem
import json


class WatchComponentTreeModel(WatchableTreeModel):
    """An extension of the data model used by Watchable Trees dedicated for the Watch Component
    Mainly handles drag&drop logic
    """

    def read_mime_data(self, data: QMimeData) -> Optional[NodeSerializableData]:
        if not data.hasText():
            return None
        mimestr = data.data('text/plain').toStdString()
        try:
            decoded =  json.loads(mimestr)
            if 'source' not in decoded:
                return None
            if 'data' not in decoded:
                return None
            
            return decoded
        except json.JSONDecodeError:
            return None

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        serializable_data = {
            'source' : 'watch',
            'data' : {}
        }    

        data = QMimeData()
        data.setData("text/plain", QByteArray.fromStdString(json.dumps(serializable_data)))
        return data

    def canDropMimeData(self, mime_data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: QModelIndex | QPersistentModelIndex) -> bool:
        print(f"canDropMimeData {action}")
        data = self.read_mime_data(mime_data)
        if data is None:
            print("bad mime")
            return False
        
        if parent.isValid():
            if not isinstance(self.itemFromIndex(parent), FolderStandardItem):
                print("Bad parent")
                return False
        
        return True

    def dropMimeData(self, mime_data: QMimeData, action: Qt.DropAction, row_index: int, column_index: int, parent: Union[QModelIndex, QPersistentModelIndex]) -> bool:
        print(f"dropMimeData {action}")
        
        
        # We can only drop on root or on a folder
        if parent.isValid():
            if not isinstance(self.itemFromIndex(parent), FolderStandardItem):
                return False
        
        data = self.read_mime_data(mime_data)
        if data is None:
            return False
        
        try:
            if 'source' in data:
                if data['source'] == 'varlist':
                    assert 'data' in data
                    self.handle_drop_varlist(action, parent, row_index, data['data'])
                elif data['source'] == 'watch':
                    pass
                else:
                    pass
        except AssertionError:
            return False

        return True
        
    def handle_drop_varlist(self, 
                            action: Qt.DropAction, 
                            parent_index: Union[QModelIndex, QPersistentModelIndex],
                            row_index:int,
                            data:List[NodeSerializableData]) -> None:
        assert isinstance(data, list)
        if action == Qt.DropAction.CopyAction:
            for node in data:
                assert 'type' in node
                assert 'display_text' in node
                assert 'fqn' in node
                assert node['fqn'] is not None  # Varlist component guarantees a FQN
                parsed_fqn = self._watchable_index.parse_fqn(node['fqn'])

                if node['type'] == 'folder':
                    folder_row = self.make_folder_row(node['display_text'], fqn=None, editable=True)
                    self.add_row(parent_index, row_index, folder_row)
                    self.fill_from_index_recursive(folder_row[0], parsed_fqn.watchable_type, parsed_fqn.path, keep_folder_fqn=False, editable=True) 
                    
                elif node['type'] == 'watchable':
                    watchable_row = self.make_watchable_row(node['display_text'], watchable_type=parsed_fqn.watchable_type, fqn=node['fqn'], editable=True)
                    self.add_row(parent_index, row_index, watchable_row)
                else:
                    pass    # Silently ignore

        else:
            print(f"unsupported action : {action}")

        return True

class WatchComponentTreeWidget(WatchableTreeWidget):
    def __init__(self, parent: Optional[QWidget], model:WatchComponentTreeModel) -> None:
        super().__init__(parent, model)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(self.DragDropMode.DragDrop)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            for index in self.selectedIndexes():
                item = cast(WatchComponentTreeModel, self.model()).itemFromIndex(index)
                if item is not None:
                    self.model().removeRow(item.row(), item.parent().index())
        else:
            super().keyPressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
       # event.acceptProposedAction()
        return super().dragEnterEvent(event)
    
    def dropEvent(self, event: QDropEvent) -> None:
        print(event.dropAction())
        return super().dropEvent(event)
        
    

class WatchComponent(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("eye-96x128.png")
    _NAME = "Watch Window"

    _HEADERS = ['', 'Value']
    _tree:WatchComponentTreeWidget
    _tree_model:WatchComponentTreeModel

    def setup(self) -> None:
        self._tree_model = WatchComponentTreeModel(self, watchable_index=self.server_manager.index)
        self._tree = WatchComponentTreeWidget(self, self._tree_model)

        layout = QVBoxLayout(self)
        layout.addWidget(self._tree)

        self._tree.expanded.connect(self.node_expanded_slot)
    
    def node_expanded_slot(self) -> None:
        self._tree.expand_first_column_to_content()
        
    def teardown(self) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        raise NotImplementedError()

    def load_state(self, state: Dict[Any, Any]) -> None:
        raise NotImplementedError()
