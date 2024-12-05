#    watch_component.py
#        A component to look at the value of watchable items broadcast by the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = [
    'WatchComponentTreeWidget',
    'WatchComponent'
]

from PySide6.QtCore import QModelIndex, Qt, QModelIndex, Signal, QPoint
from PySide6.QtWidgets import QVBoxLayout, QWidget, QMenu
from PySide6.QtGui import QContextMenuEvent, QDragMoveEvent, QDropEvent, QDragEnterEvent, QKeyEvent, QStandardItem, QAction

from scrutiny.gui import assets
from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from scrutiny.gui.dashboard_components.common.watchable_tree import WatchableTreeWidget, WatchableStandardItem, FolderStandardItem
from scrutiny.gui.dashboard_components.watch.watch_tree_model import WatchComponentTreeModel

from typing import Dict, Any, Union, cast, Optional, Tuple

class WatchComponentTreeWidget(WatchableTreeWidget):
    NEW_FOLDER_DEFAULT_NAME = "New Folder"

    def __init__(self, parent: QWidget, model:WatchComponentTreeModel) -> None:
        super().__init__(parent, model)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(self.DragDropMode.DragDrop)
        self.set_header_labels(['', 'Value'])

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        context_menu = QMenu(self)
        selected_indexes_no_nested = self.model().remove_nested_indexes(self.selectedIndexes())
        selected_items_no_nested = [self.model().itemFromIndex(index) for index in selected_indexes_no_nested if index.column()==0]

        parent, insert_row = self._find_new_folder_position_from_position(event.pos())
        
        def new_folder_action_slot() -> None:
            self._new_folder(self.NEW_FOLDER_DEFAULT_NAME, parent, insert_row)
        
        def remove_actionslot() -> None:
            for item in selected_items_no_nested:
                self.model().removeRow(item.row(), item.index().parent())
        
        new_folder_action = context_menu.addAction(assets.load_icon(assets.Icons.TreeFolder), "New Folder")
        new_folder_action.triggered.connect(new_folder_action_slot)
        
        remove_action = context_menu.addAction(assets.load_icon(assets.Icons.RedX), "Remove")
        remove_action.setEnabled( len(selected_items_no_nested) > 0 )
        remove_action.triggered.connect(remove_actionslot)
        
        self.display_context_menu(context_menu, event.pos())
        event.accept()
        
    def display_context_menu(self, menu:QMenu, pos:QPoint) -> None:
        """Display a menu at given relative position, and make sure it goes below the cursor to mimic what most people are used to"""
        actions = menu.actions()
        at: Optional[QAction] = None
        if len(actions) > 0:
            pos += QPoint(0, menu.actionGeometry(actions[0]).height())
            at = actions[0]
        menu.popup(self.mapToGlobal(pos), at)
        
    def model(self) -> WatchComponentTreeModel:
        return cast(WatchComponentTreeModel, super().model())

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            model = self.model()
            indexes_without_nested_values = model.remove_nested_indexes(self.selectedIndexes()) # Avoid errors when parent is deleted before children
            items = [model.itemFromIndex(index) for index in  indexes_without_nested_values]
            for item in items:
                if item is not None:
                    parent_index=QModelIndex() # Invalid index
                    if item.parent():
                        parent_index = item.parent().index()
                    model.removeRow(item.row(), parent_index)
        elif event.key() == Qt.Key.Key_N and event.modifiers() == Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier:
            parent, insert_row = self._find_new_folder_position_from_selection()
            self._new_folder(self.NEW_FOLDER_DEFAULT_NAME, parent, insert_row)
        else:
            super().keyPressEvent(event)
        
    

    def _find_new_folder_position_from_selection(self) -> Tuple[Optional[QStandardItem], int]:
        # USed by keyboard shortcut
        model = self.model()
        selected_list = [index for index in self.selectedIndexes() if index.column() == 0]
        selected_index = QModelIndex()
        insert_row = -1
        parent:Optional[QStandardItem] = None
        if len(selected_list) > 0:
            selected_index = selected_list[0]

        if selected_index.isValid():
            selected_item = model.itemFromIndex(selected_index)
            if isinstance(selected_item, WatchableStandardItem):
                insert_row = selected_item.row()
                parent = selected_item.parent()
            elif isinstance(selected_item, FolderStandardItem):
                insert_row = -1
                parent = selected_item
            else:
                raise NotImplementedError(f"Unknown item type for {selected_item}")

        return parent, insert_row

    def _find_new_folder_position_from_position(self, position:QPoint) -> Tuple[Optional[QStandardItem], int]:
        # Used by right-click
        index = self.indexAt(position)
        if not index.isValid():
            return None, -1
        model = self.model()
        item = model.itemFromIndex(index)
        assert item is not None

        if isinstance(item, FolderStandardItem):
            return item, -1
        parent_index = index.parent()
        if not parent_index.isValid():
            return None, index.row()
        return model.itemFromIndex(parent_index), index.row()

    def _new_folder(self, name:str, parent:Optional[QStandardItem], insert_row:int) -> None:
        model = self.model()
        new_row = model.make_folder_row(name, fqn=None, editable=True)
        model.add_row_to_parent(parent, insert_row, new_row)
        if parent is not None:
            self.expand(parent.index()) 
        self.edit(new_row[0].index())

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
        self._tree_model = WatchComponentTreeModel(self, watchable_registry=self.server_manager.registry)
        self._tree = WatchComponentTreeWidget(self, self._tree_model)

        layout = QVBoxLayout(self)
        layout.addWidget(self._tree)

        self._tree.expanded.connect(self.node_expanded_slot)
        self.expand_if_needed.connect(self._tree.expand_first_column_to_content, Qt.ConnectionType.QueuedConnection)
        self.server_manager.signals.registry_changed.connect(self._tree_model.update_availability)

        self._tree_model.update_availability()
    
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
