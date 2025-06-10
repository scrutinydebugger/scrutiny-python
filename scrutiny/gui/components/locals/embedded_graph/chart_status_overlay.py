#    chart_status_overlay.py
#        An overlay that can be applied on a chart to display a message with an icon. USed
#        to display errors and loading messages
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['ChartStatusOverlay']

from PySide6.QtGui import QPainter, QFontMetrics, QFont, QColor, QPixmap
from PySide6.QtWidgets import (QWidget, QGraphicsItem, QStyleOptionGraphicsItem)
from PySide6.QtCore import Qt, QRectF, QRect, QPointF, QSize
from scrutiny.tools.typing import *
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui import assets


class ChartStatusOverlay(QGraphicsItem):
    MARGIN = 20
    ICON_MAX_SIZE = QSize(128, 128)

    _bounding_box: QRectF
    _text_rect: QRectF
    _text_color: QColor
    _icon_rect: Optional[QRectF]
    _font: QFont
    _text: str
    _icon: Optional[QPixmap]
    _icon_resized: Optional[QPixmap]

    def __init__(self, parent: Optional[QGraphicsItem]) -> None:
        super().__init__(parent)
        self._bounding_box = QRectF()
        self._text_rect = QRectF()
        self._icon_rect = None
        self._font = QFont()
        self._font.setPixelSize(20)
        self._text_color = scrutiny_get_theme().palette().text().color()
        self._text = ""
        self._icon = None
        self._icon_resized = None
        self.setZValue(11)

    def set_font_size(self, pixel_size: int) -> None:
        self.prepareGeometryChange()
        self._font.setPixelSize(pixel_size)

    def set(self, icon: Optional[assets.Icons], text: str) -> None:
        self._icon_resized = None
        if icon is not None:
            self._icon = scrutiny_get_theme().load_large_icon_as_pixmap(icon)
        else:
            self._icon = None
        self._text = text
        self._compute_geometry()

    def _compute_geometry(self) -> None:
        self.prepareGeometryChange()
        parent = self.parentItem()
        assert parent is not None
        parent_rect = parent.boundingRect()

        # Compute icon and text rect relative to the parent
        max_w = float(max(parent_rect.width() - 2 * self.MARGIN, 0))
        max_h = float(max(parent_rect.height() - 2 * self.MARGIN, 0))
        metrics = QFontMetrics(self._font)
        text_h = float(metrics.height() * 3)    # Allow 3 lines max
        icon_max_h = max(max_h - text_h, 0)

        self._icon_rect = None
        self._icon_resized = None
        if self._icon is not None:
            icon_ratio = self._icon.width() / self._icon.height()
            max_size = self.ICON_MAX_SIZE

            # Clip both dimensions.
            icon_h = min(max_size.height(), icon_max_h)
            icon_w = min(max_size.width(), max_w)
            if icon_h > 0 and icon_w > 0:   # Display only if displayable
                # Scale the image if necessary.
                # If one of the side has been clipped, the other will be reduced.
                # If no side has been clipped, the icon should stay the same size.
                max_size_ratio = icon_w / icon_h
                if icon_ratio > max_size_ratio:
                    icon_h = icon_w / icon_ratio
                else:
                    icon_w = icon_ratio * icon_h

                # Center everything and create a rectangle for the paint() method
                icon_x = parent_rect.width() / 2 - icon_w / 2
                icon_y = parent_rect.height() / 2 - icon_h / 2
                self._icon_rect = QRectF(icon_x, icon_y, icon_w, icon_h)
                self._icon_resized = self._icon.scaled(self._icon_rect.size().toSize())

        self._text_rect = QRectF(metrics.boundingRect(
            QRect(0, 0, int(max_w), int(text_h)),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            self._text)
        )
        if self._icon_rect is not None:
            text_y = self._icon_rect.bottom()
        else:
            text_y = parent_rect.height() / 2 - self._text_rect.height() / 2
        offset_x = (parent_rect.width() - max_w) / 2
        self._text_rect.adjust(offset_x, text_y, offset_x, text_y)

        # Translate everything to the smallest bounding box possible.
        bounding_box = QRectF(self._text_rect)
        if self._icon_rect is not None:
            bounding_box.setLeft(min(self._text_rect.left(), self._icon_rect.left()))
            bounding_box.setTop(min(self._text_rect.top(), self._icon_rect.top()))
            bounding_box.setRight(max(self._text_rect.right(), self._icon_rect.right()))
            bounding_box.setBottom(max(self._text_rect.bottom(), self._icon_rect.bottom()))

        x = bounding_box.left()
        y = bounding_box.top()
        self._text_rect.adjust(-x, -y, -x, -y)
        if self._icon_rect is not None:
            self._icon_rect.adjust(-x, -y, -x, -y)

        self.setPos(bounding_box.topLeft())
        self._bounding_box = QRectF(QPointF(0, 0), bounding_box.size())

    def boundingRect(self) -> QRectF:
        return self._bounding_box

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
        if self._icon_resized is not None:
            assert self._icon_rect is not None
            painter.drawPixmap(self._icon_rect.topLeft(), self._icon_resized)
        painter.setPen(self._text_color)
        painter.setFont(self._font)
        painter.drawText(self._text_rect, self._text)

    def adjust_sizes(self) -> None:
        """Recompute the position of the overlay elements and update the content"""
        self._compute_geometry()
