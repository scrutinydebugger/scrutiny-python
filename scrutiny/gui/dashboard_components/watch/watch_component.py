#    watch_component.py
#        A component to look at the value of watchable items broadcast by the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger


from PySide6.QtCore import QModelIndex, Qt, QModelIndex, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget
from PySide6.QtGui import QDragMoveEvent, QDropEvent, QDragEnterEvent, QKeyEvent

from scrutiny.gui import assets
from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from scrutiny.gui.dashboard_components.common.watchable_tree import WatchableTreeWidget
from scrutiny.gui.dashboard_components.watch.watch_tree_model import WatchComponentTreeModel

from typing import Dict, Any, Union, cast

class WatchComponentTreeWidget(WatchableTreeWidget):

    def __init__(self, parent: QWidget, model:WatchComponentTreeModel) -> None:
        super().__init__(parent, model)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(self.DragDropMode.DragDrop)
        self.set_header_labels(['', 'Value'])
        

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            model = cast(WatchComponentTreeModel, self.model())
            indexes_without_nested_values = model.remove_nested_indexes(self.selectedIndexes()) # Avoid errors when parent is deleted before children
            items = [model.itemFromIndex(index) for index in  indexes_without_nested_values]
            for item in items:
                if item is not None:
                    parent_index=QModelIndex() # Invalid index
                    if item.parent():
                        parent_index = item.parent().index()
                    model.removeRow(item.row(), parent_index)
        else:
            super().keyPressEvent(event)



    def _set_drag_and_drop_action(self, event:Union[QDragEnterEvent, QDragMoveEvent, QDropEvent]) -> None:
        if event.source() is self:
            event.setDropAction(Qt.DropAction.MoveAction)
        else:
            event.setDropAction(Qt.DropAction.CopyAction)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        self._set_drag_and_drop_action(event)
        super().dragEnterEvent(event)
        event.accept()
        

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        self._set_drag_and_drop_action(event)
        return super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_drag_and_drop_action(event)
        return super().dropEvent(event)
    
        

class WatchComponent(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("eye-96x128.png")
    _NAME = "Watch Window"

    _tree:WatchComponentTreeWidget
    _tree_model:WatchComponentTreeModel

    expand_if_needed = Signal()

    def setup(self) -> None:
        self._tree_model = WatchComponentTreeModel(self, watchable_index=self.server_manager.index)
        self._tree = WatchComponentTreeWidget(self, self._tree_model)

        layout = QVBoxLayout(self)
        layout.addWidget(self._tree)

        self._tree.expanded.connect(self.node_expanded_slot)
        self.expand_if_needed.connect(self._tree.expand_first_column_to_content, Qt.ConnectionType.QueuedConnection)
    
    def node_expanded_slot(self) -> None:
        # Added at the end of the event loop because it is a queuedConnection
        # Expanding with star requires that
        self.expand_if_needed.emit()
    
        
    def teardown(self) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        raise NotImplementedError()

    def load_state(self, state: Dict[Any, Any]) -> None:
        raise NotImplementedError()
