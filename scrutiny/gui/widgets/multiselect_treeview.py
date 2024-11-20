__all__ = ['MultiSelectTreeView']

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QTreeView

class MultiSelectTreeView(QTreeView):
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
