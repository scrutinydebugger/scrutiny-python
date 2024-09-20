from qtpy.QtWidgets import QCommonStyle, QWidget, QStyleOption, QStyle
from qtpy.QtGui import QPainter, QColor, QBrush


class DiagnosticStyle(QCommonStyle):
    def drawControl(self, element:QStyle.ControlElement, opt:QStyleOption, painter:QPainter, widget:QWidget):
        QCommonStyle.drawControl(self, element, opt, painter, widget)

        painter.setPen(QColor("red"))
        painter.drawRect(widget.rect())
