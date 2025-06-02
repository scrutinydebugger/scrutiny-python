#    graph_statistics.py
#        A statistic overlay that can be displayed on the top of a graph
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['GraphStatistics']

from PySide6.QtGui import QPainter, QFontMetrics, QFont, QColor
from PySide6.QtWidgets import (QWidget, QGraphicsItem, QStyleOptionGraphicsItem)
from PySide6.QtCore import Qt, QRectF, QRect
from scrutiny.tools.profiling import VariableRateExponentialAverager
from scrutiny.tools.typing import *
from scrutiny.gui.themes import scrutiny_get_theme


class GraphStatistics:
    class Overlay(QGraphicsItem):
        _stats: "GraphStatistics"
        _bounding_box: QRectF
        _text_rect: QRectF
        _font: QFont
        _text_color: QColor
        _text: str

        def __init__(self, parent: Optional[QGraphicsItem], stats: "GraphStatistics") -> None:
            super().__init__(parent)
            self._stats = stats
            self._bounding_box = QRectF()
            self._text_rect = QRectF()
            self._font = QFont()
            self._text_color = scrutiny_get_theme().palette().text().color()
            self._text = ""
            self.setZValue(11)

        def update_content(self) -> None:
            self._make_text()
            self._compute_geometry()

        def _make_text(self) -> None:
            refresh_rate_str = "N/A"
            if self._stats.repaint_rate.is_enabled():
                refresh_rate_str = "%0.1f/sec" % self._stats.repaint_rate.get_value()
            opengl_enabled_str = "Enabled" if self._stats.opengl else "Disabled"
            lines = [
                "Decimation: %0.1fx" % self._stats.decimation_factor,
                "Visible points: %d/%d" % (self._stats.visible_points, self._stats.total_points),
                "OpenGL: %s" % opengl_enabled_str,
                "Refresh rate: %s" % refresh_rate_str
            ]
            self._text = '\n'.join(lines)

        def _compute_geometry(self) -> None:
            self.prepareGeometryChange()
            metrics = QFontMetrics(self._font)
            self._text_rect = QRectF(metrics.boundingRect(QRect(0, 0, 200, 100), Qt.AlignmentFlag.AlignLeft, self._text))
            self._bounding_box = QRectF(self._text_rect.adjusted(0, 0, 0, 0))

        def boundingRect(self) -> QRectF:
            return self._bounding_box

        def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
            painter.fillRect(self._text_rect, QColor(0xC8, 0xE8, 0xFF, 50))
            painter.setPen(self._text_color)
            painter.drawText(self._text_rect, self._text)

    visible_points: int
    """Number of points drawn on the chart"""
    total_points: int
    """Number of points stored in memory that could go on the graph (does not include points so old that they get removed)"""
    decimation_factor: float
    """Ratio of visible points/total points"""
    opengl: bool
    """Says if OpenGL is activated"""
    repaint_rate: VariableRateExponentialAverager
    """Estimated repaint rate in number of repaint/sec"""
    _overlay: Overlay
    """The GraphicItem overlay being displayed on top of the chart"""
    _allow_show_overlay: bool
    """A flag enabling/disabling the overlay"""

    def __init__(self, draw_zone: Optional[QGraphicsItem] = None) -> None:
        self._allow_show_overlay = True
        self._overlay = self.Overlay(draw_zone, self)
        self.repaint_rate = VariableRateExponentialAverager(time_estimation_window=0.2, tau=1, near_zero=0.01)
        self.clear()

    def clear(self) -> None:
        self.opengl = False
        self.visible_points = 0
        self.total_points = 0
        self.decimation_factor = 1

    def show_overlay(self) -> None:
        if self._allow_show_overlay:
            self._overlay.show()
            self._overlay.update_content()

    def hide_overlay(self) -> None:
        self._overlay.hide()

    def update_overlay(self) -> None:
        self._overlay.update_content()

    def overlay(self) -> Overlay:
        return self._overlay

    def allow_overlay(self) -> None:
        self._allow_show_overlay = True
        self.show_overlay()

    def disallow_overlay(self) -> None:
        self._allow_show_overlay = False
        self.hide_overlay()

    def is_overlay_allowed(self) -> bool:
        return self._allow_show_overlay
