
__all__ = ['ChartCenterMessageIcon']

from PySide6.QtGui import QPainter, QFontMetrics, QFont, QColor, QIcon
from PySide6.QtWidgets import ( QWidget, QGraphicsItem, QStyleOptionGraphicsItem)
from PySide6.QtCore import Qt, QRectF, QRect
from scrutiny.tools.typing import *
from scrutiny.gui import assets

class ChartCenterMessageIcon(QGraphicsItem):
    _bounding_box:QRectF
    _text_rect:QRectF
    _font:QFont
    _text:str
    _icon:Optional[QIcon]

    def __init__(self, parent:Optional[QGraphicsItem]) -> None:
        super().__init__(parent)
        self._bounding_box = QRectF()
        self._text_rect = QRectF()
        self._font  = QFont()
        self._text = ""
        self._icon = None
        self.setZValue(11)

    def set(self, icon:assets.Icons, text:str) -> None:
        self._icon = assets.load_icon(icon, assets.IconFormat.Large)
        self._text = text
        self._compute_geometry()
        self.show()

    def _compute_geometry(self) -> None:
        self.prepareGeometryChange()
        metrics = QFontMetrics(self._font)
        self._text_rect = QRectF(metrics.boundingRect(QRect(0, 0, 200, 100), Qt.AlignmentFlag.AlignLeft, self._text))
        self._bounding_box = QRectF(self._text_rect.adjusted(0,0,0,0))

    def boundingRect(self) -> QRectF:
        return self._bounding_box

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget]=None) -> None:
        painter.fillRect(self._text_rect, QColor(0xC8, 0xE8, 0xFF, 50))
        painter.setPen(QColor(0,0,0))
        painter.drawText(self._text_rect, self._text)
