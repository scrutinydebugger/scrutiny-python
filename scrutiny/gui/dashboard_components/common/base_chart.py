#    base_chart.py
#        Some customized extensions of the QT Charts for the Scrutiny GUI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = [
    'ScrutinyLineSeries',
    'ScrutinyValueAxis', 
    'ScrutinyValueAxisWithMinMax',
    'ScrutinyChart',
    'ScrutinyChartCallout',
    'ScrutinyChartView'
]

import enum
from pathlib import Path
import os
from bisect import bisect_left

from PySide6.QtCharts import QLineSeries, QValueAxis, QChart, QChartView
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget, QFileDialog, QMessageBox
from PySide6.QtGui import QFont, QPainter, QFontMetrics, QColor, QContextMenuEvent
from PySide6.QtCore import  QPointF, QRect, QRectF, Qt, QObject, Signal

from scrutiny import tools
from scrutiny.gui.themes import get_theme_prop, ScrutinyThemeProperties
from scrutiny.gui.tools.min_max import MinMax
from scrutiny.gui.core.preferences import gui_preferences

from typing import Any, Optional, Any


class ScrutinyLineSeries(QLineSeries):

    def emphasize(self) -> None:
        pen = self.pen()
        pen.setWidth(get_theme_prop(ScrutinyThemeProperties.CHART_EMPHASIZED_SERIES_WIDTH))
        self.setPen(pen)
    
    def deemphasize(self) -> None:
        pen = self.pen()
        pen.setWidth(get_theme_prop(ScrutinyThemeProperties.CHART_NORMAL_SERIES_WIDTH))
        self.setPen(pen)

    def search_closest_monotonic(self, xval:float) -> Optional[QPointF]:
        """Search for the closest point using the XAxis. Assume a monotonic X axis.
        If the values are not monotonic : undefined behavior"""
        points = self.points()
        if len(points) == 0:
            return None

        index = bisect_left(points, xval, key=lambda p:p.x())
        index = min(index, len(points)-1)
        p1 = points[index]
        if index == 0:
            return p1
        p2 = points[index-1]
        if abs(p1.x()-xval) <= abs(p2.x()-xval):
            return p1
        else:
            return p2

class ScrutinyValueAxis(QValueAxis):

    def emphasize(self) -> None:
        font = self.titleFont()
        font.setBold(True)
        self.setTitleFont(font)
    
    def deemphasize(self) -> None:
        font = self.titleFont()
        font.setBold(False)
        self.setTitleFont(font)

class ScrutinyValueAxisWithMinMax(ScrutinyValueAxis):
    _minmax:MinMax

    @tools.copy_type(ScrutinyValueAxis.__init__)
    def __init__(self, *args:Any, **kwargs:Any) -> None:
        super().__init__(*args, **kwargs)
        self._minmax = MinMax()

    def update_minmax(self, v:float) ->None:
        self._minmax.update(v)
    
    def clear_minmax(self) -> None:
        self._minmax.clear()

    def minval(self) -> Optional[float]:
        return self._minmax.min()
    
    def maxval(self) -> Optional[float]:
        return self._minmax.max()
    
    def set_minval(self, v:float) -> None:
        self._minmax.set_min(v)
    
    def set_maxval(self, v:float) -> None:
        self._minmax.set_max(v)
    
    def autoset_range(self, margin_ratio:float=0) -> None:
        margin_ratio = max(min(0.2, margin_ratio), 0)
        minv, maxv = self._minmax.min(), self._minmax.max()
        if minv is None or maxv is None:
            self.setRange(0,1)
            return
        span = maxv-minv
        if span == 0:
            self.setRange(minv-1, maxv+1)
        else:
            new_range_min = minv - span * margin_ratio
            new_range_max = maxv + span * margin_ratio
            self.setRange(new_range_min, new_range_max)

class ScrutinyChart(QChart):
    pass

class ScrutinyChartCallout(QGraphicsItem):

    CALLOUT_RECT_DIST = 10  # Distance between point marker and 
    PADDING = 5             # padding between text and callout border

    class DisplaySide(enum.Enum):
        Above = enum.auto()
        Below = enum.auto()


    _chart:ScrutinyChart
    _text:str
    _point_location_on_chart:QPointF
    _font:QFont
    _text_rect:QRectF
    _rect:QRectF
    _color:QColor
    _side:DisplaySide
    _marker_radius : int


    def __init__(self, chart:ScrutinyChart) -> None:
        super().__init__(chart)
        self._chart = chart
        self._text = ''
        self._point_location_on_chart = QPointF()
        self._font  = QFont()
        self._text_rect = QRectF()
        self._callout_rect = QRectF()
        self._bounding_box = QRectF()
        self._color = QColor()
        self._updown_side = self.DisplaySide.Above
        self._marker_radius = 0
        self.hide()
        self.setZValue(11)

    def _compute_geometry(self) -> None:

        self.prepareGeometryChange()
        metrics = QFontMetrics(self._font)
        self._text_rect = QRectF(metrics.boundingRect(QRect(0, 0, 150, 150), Qt.AlignmentFlag.AlignLeft, self._text))
        self._text_rect.translate(self.PADDING, self.PADDING)
        self._callout_rect = QRectF(self._text_rect.adjusted(-self.PADDING, -self.PADDING, self.PADDING, self.PADDING))
        self._marker_radius = get_theme_prop(ScrutinyThemeProperties.CHART_CALLOUT_MARKER_RADIUS)

        chart_h = self._chart.size().height()
        chart_w = self._chart.size().width()
        if self._point_location_on_chart.y() <= chart_h/3:
            self._updown_side = self.DisplaySide.Below
        elif self._point_location_on_chart.y() >= chart_h*2/3:
            self._updown_side = self.DisplaySide.Above
        else:
            pass    # Keep last. Makes an hysteresis
        
        callout_rect_origin = QPointF(self._point_location_on_chart)
        bounding_box_vertical_offset = self._marker_radius + self.CALLOUT_RECT_DIST
        if self._updown_side == self.DisplaySide.Above:
            callout_rect_origin -= QPointF(0, self._callout_rect.height() + self.CALLOUT_RECT_DIST)
            self._bounding_box = self._callout_rect.adjusted(0,0,0,bounding_box_vertical_offset)
        elif self._updown_side == self.DisplaySide.Below:
            callout_rect_origin += QPointF(0, self.CALLOUT_RECT_DIST)
            self._bounding_box = self._callout_rect.adjusted(0,-bounding_box_vertical_offset,0,0)
        
        callout_rect_origin -= QPointF(self._callout_rect.width()/2,0)  # Handle left overflow
        if callout_rect_origin.x() < 0:
            callout_rect_origin += QPointF(abs(callout_rect_origin.x()), 0)
        
        rect_right_x = callout_rect_origin.x() + self._callout_rect.width() # Handle right overflow
        if rect_right_x > chart_w:
            callout_rect_origin -= QPointF(rect_right_x - chart_w, 0)


        self.setPos(callout_rect_origin)


    def set_content(self, pos:QPointF, text:str, color:QColor) -> None:
        self._point_location_on_chart = pos
        self._text = text
        self._color = color
        self._compute_geometry()

    def boundingRect(self) -> QRectF:
        # Inform QT about the size we need
        return self._bounding_box

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget]=None) -> None:
        painter.setBrush(self._color)   # Fill color
        painter.setPen(self._color)     # Border color
        painter.drawRoundedRect(self._callout_rect, 5, 5)
        anchor = QPointF(self.mapFromParent(self._point_location_on_chart))
        painter.setPen(QColor(0,0,0))     # Border color
        painter.drawEllipse(anchor, self._marker_radius, self._marker_radius)
        painter.setPen(QColor(0,0,0))
        painter.drawText(self._text_rect, self._text)

class ScrutinyChartView(QChartView):
    class _Signals(QObject):
        context_menu_event = Signal(QContextMenuEvent)

    @tools.copy_type(QChartView.__init__)
    def __init__(self, *args:Any, **kwargs:Any) -> None:
        super().__init__(*args, **kwargs)
        self._signals = self._Signals()
    
    @property
    def signals(self) -> _Signals:
        return self._signals

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self._signals.context_menu_event.emit(event)
