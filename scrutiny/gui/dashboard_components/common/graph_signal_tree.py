#    graph_signal_tree.py
#        The widget that allow the user to define a graph axis/signals using a 2 level tree.
#        First level for axes, Second level for watchables
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = [
    'AxisStandardItem',
    'ChartSignalStandardItem',
    'GraphSignalModel',
    'GraphSignalTree',
    'AxisContent'
]

from dataclasses import dataclass

from PySide6.QtWidgets import QWidget, QMenu
from PySide6.QtGui import ( QStandardItem, QDropEvent, QDragEnterEvent, QDragMoveEvent, QDragEnterEvent, 
                           QDragMoveEvent, QContextMenuEvent, QAction, QKeyEvent, QColor, QPixmap
                           )
from PySide6.QtCore import QMimeData, QModelIndex, Qt, QPersistentModelIndex, QPoint
from PySide6.QtCharts import QLineSeries, QAbstractSeries

from scrutiny.gui import assets
from scrutiny.gui.core.scrutiny_drag_data import ScrutinyDragData, WatchableListDescriptor, SingleWatchableDescriptor
from scrutiny.gui.dashboard_components.common.watchable_tree import WatchableStandardItem, get_watchable_icon
from scrutiny.gui.dashboard_components.common.base_tree import BaseTreeModel, BaseTreeView, SerializableItemIndexDescriptor


from typing import Optional, List, Union, Sequence, cast, Any


class AxisStandardItem(QStandardItem):
    def __init__(self, name:str):
        axis_icon = assets.load_icon(assets.Icons.GraphAxis)
        super().__init__(axis_icon, name)
        self.setDropEnabled(True)
        self.setDragEnabled(False)

class ChartSignalStandardItem(WatchableStandardItem):
    _chart_series:Optional[QLineSeries] = None

    def __init__(self, *args:Any, **kwargs:Any):
        super().__init__(*args, **kwargs)
        self._chart_series = None

    def _assert_series_set(self) -> None:
        if self._chart_series is None:
            raise RuntimeError("A serie smust be attached first")

    def attach_series(self, series:QLineSeries) -> None:
        if not isinstance(series, QAbstractSeries):
            raise ValueError("A chart series must be given")
        self._chart_series = series
        self.change_icon_to_series_color()

    def detach_series(self) -> None:
        self._assert_series_set()
        self._chart_series = None
        self.reload_watchable_icon()

    def series_attached(self) -> bool:
        return self._chart_series is not None

    def series(self) -> QLineSeries:
        self._assert_series_set()
        assert self._chart_series is not None   # for mypy
        return self._chart_series
    
    def change_icon_to_series_color(self) -> None:
        LINE_WIDTH = 12
        LINE_HEIGHT = 5
        color = self.series().color()
        new_pix = QPixmap(LINE_WIDTH, LINE_HEIGHT)
        new_pix.fill(color)
        self.setIcon(new_pix)

    def reload_watchable_icon(self) -> None:
        self.setIcon(get_watchable_icon(self.watchable_type))

    def hide_series(self) -> None:
        series = self.series()
        series.hide()
        font = self.font()
        font.setStrikeOut(True)
        self.setFont(font)

    def show_series(self) -> None:
        series = self.series()
        series.show()
        font = self.font()
        font.setStrikeOut(False)
        self.setFont(font)

    def series_visible(self) -> bool:
        series = self.series()
        return series.isVisible()


@dataclass
class AxisContent:
    axis_name:str
    signal_items:List[ChartSignalStandardItem]

class GraphSignalModel(BaseTreeModel):

    def __init__(self, parent:QWidget) -> None:
        super().__init__(parent, nesting_col= self.axis_col())
        self.setColumnCount(2)

    def make_axis_row(self, axis_name:str) -> List[AxisStandardItem]:
        axis_item = AxisStandardItem(axis_name)
        return [axis_item]

    def axis_col(self) -> int:
        return 0
    
    def watchable_col(self) -> int:
        return 0
    
    def value_col(self) -> int:
        return 1
    
    def get_watchable_row_from_dragged_watchable_desc(self, watchable_desc:SingleWatchableDescriptor) -> List[QStandardItem]:
        watchable_item = ChartSignalStandardItem.from_drag_watchable_descriptor(watchable_desc)
        watchable_item.setEditable(True)
        watchable_item.setDragEnabled(True)

        value_item=QStandardItem()
        value_item.setEditable(False)

        return [watchable_item, value_item]
 
    def _validate_drag_data(self, drag_data:Optional[ScrutinyDragData], action:Qt.DropAction) -> bool:
        
        if drag_data is None:
            return False
        
        if drag_data.type != ScrutinyDragData.DataType.WatchableList:
            return False
        
        if action not in [ Qt.DropAction.CopyAction,  Qt.DropAction.MoveAction]:
            return False
        
        if action == Qt.DropAction.CopyAction:
            if drag_data.data_copy is None:
                return False
        
        if action == Qt.DropAction.MoveAction:
            if drag_data.data_move is None:
                return False
            
        return True
            
    def _get_last_axisor_create(self) -> AxisStandardItem:
        if self.rowCount() == 0:
            self.add_axis("Axis 1")

        axis_item = self.item(self.rowCount()-1, self.axis_col())
        assert isinstance(axis_item, AxisStandardItem)
        return axis_item
    
    def add_axis(self, name:str) -> None:
        self.appendRow(self.make_axis_row(name))

    def mimeData(self, indexes:Sequence[QModelIndex]) -> QMimeData:
        item_list:List[WatchableStandardItem] = []
        for index in indexes:
            if index.isValid() and index.column() == self.watchable_col():
                item = self.itemFromIndex(index)
                if isinstance(item, WatchableStandardItem):
                    item_list.append(item)


        self.sort_items_by_path(item_list, top_to_bottom=True)
        item_descriptors:List[SingleWatchableDescriptor] = []
        for item in item_list:
            item_descriptors.append(SingleWatchableDescriptor(
                fqn=item.fqn,
                text=item.text()
            ))
        move_data = [self.make_serializable_item_index_descriptor(item) for item in item_list]
        drag_data = WatchableListDescriptor(item_descriptors).to_drag_data(move_data)

        mime_data = drag_data.to_mime()
        assert mime_data is not None
        return mime_data
    
    def canDropMimeData(self, mime_data: QMimeData, 
                        action: Qt.DropAction, 
                        row_index: int, 
                        column_index: int, 
                        parent: Union[QModelIndex, QPersistentModelIndex]
                        ) -> bool:
        
        drag_data = ScrutinyDragData.from_mime(mime_data)

        if not self._validate_drag_data(drag_data, action):
            return False

        if parent.isValid():
            parent_item = self.itemFromIndex(parent)
            if not isinstance(parent_item, AxisStandardItem):
                return False
            
        return True
    
    def dropMimeData(self, 
                     mime_data: QMimeData, 
                     action: Qt.DropAction, 
                     row_index: int, 
                     column_index: int, 
                     parent: Union[QModelIndex, QPersistentModelIndex]
                     ) -> bool:
        drag_data = ScrutinyDragData.from_mime(mime_data)
        if not self._validate_drag_data(drag_data, action):
            return False
        assert drag_data is not None
        
        parent_item = self.itemFromIndex(parent)
        del parent
        last_axis = self._get_last_axisor_create()

        if parent_item is None:
            parent_item = last_axis
            row_index = -1
        
        if not isinstance(parent_item, AxisStandardItem):
            return False
        
        if action == Qt.DropAction.CopyAction:
            watchable_list = WatchableListDescriptor.from_drag_data(drag_data)
            if watchable_list is None:
                return False
            
            for watchable_desc in watchable_list.data:
                row = self.get_watchable_row_from_dragged_watchable_desc(watchable_desc)
                if row_index == -1:
                    parent_item.appendRow(row)
                else:
                    parent_item.insertRow(row_index, row)
        
        elif action == Qt.DropAction.MoveAction:
            self.handle_internal_move(parent_item.index(), row_index, cast(List[SerializableItemIndexDescriptor], drag_data.data_move))
        return True

    def get_signals(self) -> List[AxisContent]:
        outlist:List[AxisContent] = [] 

        for i in range(self.rowCount()):
            axis_item = self.item(i, self.axis_col())
            assert isinstance(axis_item, AxisStandardItem)
            
            if axis_item.rowCount() == 0:
                continue
            axis = AxisContent(axis_name=axis_item.text(), signal_items=[])

            for i in range(axis_item.rowCount()):
                watchable_item = axis_item.child(i, self.watchable_col())
                assert isinstance(watchable_item, ChartSignalStandardItem)
                axis.signal_items.append(watchable_item)
            outlist.append(axis)
        return outlist
    
    def reload_original_icons(self) -> None:
        for axis_index in range(self.rowCount()):
            axis = self.item(axis_index, self.axis_col())
            for signal_index in range(axis.rowCount()):
                signal_item = axis.child(signal_index, self.watchable_col())
                assert isinstance(signal_item, ChartSignalStandardItem)
                signal_item.reload_watchable_icon()

class GraphSignalTree(BaseTreeView):
    _locked:bool

    def model(self) -> GraphSignalModel:
        return cast(GraphSignalModel, super().model())

    def __init__(self, parent:QWidget) -> None:
        super().__init__(parent)
        self._locked = False

        self.setModel(GraphSignalModel(self))
        self.model().add_axis("Axis 1")
        self.setUniformRowHeights(True)   # Documentation says it helps performance
        self.setAnimated(False)
        self.header().setStretchLastSection(True)
        self.header().setVisible(False)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(self.DragDropMode.DragDrop)

    def rowsInserted(self, parent:Union[QModelIndex, QPersistentModelIndex], start:int, end:int) -> None:
        if parent.isValid():
            self.expand(parent)
        super().rowsInserted(parent, start, end)
        self.resizeColumnToContents(0)
    
    def rowsRemoved(self, parent:Union[QModelIndex, QPersistentModelIndex], first:int, last:int) -> None:
        super().rowsRemoved(parent, first, last)
        self.resizeColumnToContents(0)
    
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

    
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        context_menu = QMenu(self)
        selected_indexes_no_nested = self.model().remove_nested_indexes(self.selectedIndexes())
        nesting_col = self.model().nesting_col()
        selected_items_no_nested = [self.model().itemFromIndex(index) for index in selected_indexes_no_nested if index.column()==nesting_col]
        
        def new_axis_action_slot() -> None:
            self.model().appendRow(self.model().make_axis_row("New Axis"))
        
        def remove_action_slot() -> None:
            for item in selected_items_no_nested:
                self.model().removeRow(item.row(), item.index().parent())
        
        new_axis_action = context_menu.addAction(assets.load_icon(assets.Icons.GraphAxis), "New Axis")
        new_axis_action.triggered.connect(new_axis_action_slot)

        indexes = self.selectedIndexes()

        items = [self.model().itemFromIndex(index) for index in indexes if index.isValid()]
        signals_with_series = [item for item in items if isinstance(item, ChartSignalStandardItem) and item.series_attached() ]

        if len(signals_with_series) > 0:
            all_visible = True
            for item in signals_with_series:
                if not item.series_visible():
                    all_visible = False
            
            if all_visible:
                show_hide_action = context_menu.addAction(assets.load_icon(assets.Icons.Hide), "Hide")
                def hide_action_slot() -> None:
                    for item in signals_with_series:
                        item.hide_series()
                show_hide_action.triggered.connect(hide_action_slot)
            else:
                show_hide_action = context_menu.addAction(assets.load_icon(assets.Icons.Show), "Show")
                def show_action_slot() -> None:
                    for item in signals_with_series:
                        item.show_series()
                show_hide_action.triggered.connect(show_action_slot)
        
        remove_action = context_menu.addAction(assets.load_icon(assets.Icons.RedX), "Remove")
        remove_action.setEnabled( len(selected_items_no_nested) > 0 )
        remove_action.triggered.connect(remove_action_slot)

        if self._locked:
            new_axis_action.setDisabled(True)
            remove_action.setDisabled(True)
        
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


    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete and not self._locked:
            model = self.model()
            indexes_without_nested_values = model.remove_nested_indexes(self.selectedIndexes()) # Avoid errors when parent is deleted before children
            items = [model.itemFromIndex(index) for index in  indexes_without_nested_values]
            for item in items:
                if item is not None:
                    model.removeRow(item.row(), item.index().parent())
        else:
            return super().keyPressEvent(event)
        
    def get_signals(self) -> List[AxisContent]:
        return self.model().get_signals()

    def lock(self) -> None:
        self.setDragDropMode(self.DragDropMode.NoDragDrop)
        self._locked = True
    
    def unlock(self) -> None:
        self.setDragDropMode(self.DragDropMode.DragDrop)
        self._locked = False

    def reload_original_icons(self) -> None:
        self.model().reload_original_icons()


        
