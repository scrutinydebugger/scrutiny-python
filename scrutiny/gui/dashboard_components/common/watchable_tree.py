__all__ = [
    'FolderStandardItem',
    'WatchableStandardItem',
    'BaseWatchableIndexTreeStandardItem',
    'WatchableTreeWidget',
]

from scrutiny.sdk import WatchableType, WatchableConfiguration
from PySide6.QtGui import  QStandardItem, QIcon, QKeyEvent, QStandardItemModel, QColor
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtWidgets import QTreeView, QWidget
from scrutiny.gui import assets
from typing import Any, List, Optional

def get_watchable_icon(wt:WatchableType) -> QIcon:
    if wt == WatchableType.Variable:
        return assets.load_icon(assets.Icons.TreeVar)
    if wt == WatchableType.Alias:
        return assets.load_icon(assets.Icons.TreeAlias)
    if wt == WatchableType.RuntimePublishedValue:
        return assets.load_icon(assets.Icons.TreeRpv)
    raise NotImplementedError(f"Unsupported icon for {wt}")

class BaseWatchableIndexTreeStandardItem(QStandardItem):
    _fqn:str

    def __init__(self, fqn:str, *args:Any, **kwargs:Any) -> None:
        self._fqn = fqn
        super().__init__(*args, **kwargs)

    @property
    def fqn(self) -> str:
        return self._fqn


class FolderStandardItem(BaseWatchableIndexTreeStandardItem):
    def __init__(self, text:str, fqn:str):
        folder_icon = assets.load_icon(assets.Icons.TreeFolder)
        super().__init__(fqn, folder_icon, text)
    

class WatchableStandardItem(BaseWatchableIndexTreeStandardItem):
    def __init__(self, watchable_type:WatchableType, text:str, fqn:str):
        icon = get_watchable_icon(watchable_type)
        super().__init__(fqn, icon, text)


class WatchableTreeWidget(QTreeView):
    _model:QStandardItemModel

    DEFAULT_ITEM0_WIDTH = 400
    DEFAULT_ITEM_WIDTH = 100

    def __init__(self, parent:Optional[QWidget]=None) -> None:
        super().__init__(parent)
        self._model = QStandardItemModel(self)
        self.setModel(self._model)
        self.setUniformRowHeights(True)   # Documentation says it helps performance
        self.setAnimated(False)
        self.header().setStretchLastSection(False)
    
    def set_header_labels(self, headers:List[str]) -> None:
        self._model.setColumnCount(len(headers))
        self._model.setHorizontalHeaderLabels(headers)
    
    def expand_first_column_to_content(self) -> None:
        """Resize the first column to content if it makes it grow."""
        header = self.header()
        original_sizes = [header.sectionSize(i) for i in range(self._model.columnCount())]
        header.resizeSections(header.ResizeMode.ResizeToContents)

        if header.sectionSize(0) < original_sizes[0]:
            header.resizeSection(0, original_sizes[0])

        for i in range(1, len(original_sizes)):
            header.resizeSection(i, original_sizes[i])

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Control:
            self.setSelectionMode(self.SelectionMode.MultiSelection)
        elif event.key() == Qt.Key.Key_Shift:
            self.setSelectionMode(self.SelectionMode.ContiguousSelection)
        else:
            return super().keyPressEvent(event)
    
    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Control:
            if self.selectionMode() == self.SelectionMode.MultiSelection:
                self.setSelectionMode(self.SelectionMode.SingleSelection)
        elif event.key() == Qt.Key.Key_Shift:
            if self.selectionMode() == self.SelectionMode.ContiguousSelection:
                self.setSelectionMode(self.SelectionMode.SingleSelection)
        else:
            return super().keyReleaseEvent(event)
    
    def get_model(self) -> QStandardItemModel:
        return self._model
    
    def set_row_color(self, index:QModelIndex, color:QColor) -> None:
        item = self._model.itemFromIndex(index)
        for i in range(self._model.columnCount()):
            item = self._model.itemFromIndex(index.siblingAtColumn(i))
            if item is not None:
                item.setBackground(color)
        

    def make_watchable_row(self, 
                          name:str, 
                          watchable_config:WatchableConfiguration, 
                          fqn:str, 
                          editable:bool, 
                          extra_columns:List[QStandardItem]=[]) -> List[QStandardItem]:
        
        item =  WatchableStandardItem(watchable_config.watchable_type, name, fqn)
        item.setEditable(editable)
        item.setDragEnabled(True)
        for col in extra_columns:
            col.setDragEnabled(True)
        return [item] + extra_columns
        

    def make_folder_row(self,  name:str, fqn:str, editable:bool ) -> List[QStandardItem]:
        item =  FolderStandardItem(name, fqn)
        item.setEditable(editable)
        item.setDragEnabled(True)
        return [item]

    