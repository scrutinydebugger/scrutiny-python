

from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QWidget, QLineEdit

from typing import Any

class WatchableLineEdit(QLineEdit):
    def __init__(self, *args:Any, **kwargs:Any) -> None:
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        print("dragEnterEvent")
        event.accept()

    def dropEvent(self, event:QDropEvent) -> None:
        print("dropEvent")
