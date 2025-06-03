#    log_viewer.py
#        A widget for watching log lines
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['LogViewer']

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QWidget, QPlainTextEdit

from scrutiny.tools.typing import *


class LogViewer(QPlainTextEdit):
    """A read-only multiline text edit area that displays log lines """
    _log_lines: List[str]
    _max_lines: int

    def __init__(self, parent: QWidget, max_lines: int = 100) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self._log_lines = []
        self._max_lines = max_lines

    def add_lines(self, lines: List[str]) -> None:
        self._log_lines.extend(lines)
        if len(self._log_lines) > self._max_lines:
            self._log_lines = self._log_lines[-self._max_lines:]
        scrollbar = self.verticalScrollBar()
        previous_value = scrollbar.value()
        autoscroll = True if scrollbar.value() == scrollbar.maximum() else False

        self.setPlainText('\n'.join(self._log_lines))
        if autoscroll:
            scrollbar.setValue(scrollbar.maximum())
        else:
            scrollbar.setValue(previous_value)

    def add_line(self, line: str) -> None:
        self.add_lines([line])

    def sizeHint(self) -> QSize:
        return QSize(600, 300)
