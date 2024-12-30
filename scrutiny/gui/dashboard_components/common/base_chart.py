#    base_chart.py
#        Some customized extensions of the QT Charts for the Scrutiny GUI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = [
    'ScrutinyLineSeries',
    'ScrutinyValueAxis'
]

from PySide6.QtCharts import QLineSeries, QValueAxis
from PySide6.QtCore import QObject

class ScrutinyLineSeries(QLineSeries):
    EMPHASIZED_WIDTH = 3
    NORMAL_WIDTH = 1 

    def __init__(self, parent:QObject) -> None:
        super().__init__(parent)

    def emphasize(self) -> None:
        pen = self.pen()
        pen.setWidth(self.EMPHASIZED_WIDTH)
        self.setPen(pen)
    
    def deemphasize(self) -> None:
        pen = self.pen()
        pen.setWidth(self.NORMAL_WIDTH)
        self.setPen(pen)

class ScrutinyValueAxis(QValueAxis):

    def __init__(self, parent:QObject) -> None:
        super().__init__(parent)

    def emphasize(self) -> None:
        font = self.titleFont()
        font.setBold(True)
        self.setTitleFont(font)
    
    def deemphasize(self) -> None:
        font = self.titleFont()
        font.setBold(False)
        self.setTitleFont(font)
