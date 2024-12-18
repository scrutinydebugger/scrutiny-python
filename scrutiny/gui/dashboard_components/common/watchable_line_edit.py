#    watchable_line_edit.py
#        A QLineEdit that can accept textual input or drag&drop of a single watchable element
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QLineEdit

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
