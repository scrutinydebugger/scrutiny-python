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
    'ScrutinyChartView',
    'ScrutinyChartToolBar'
]

import enum
from bisect import bisect_left
from dataclasses import dataclass
import math

from PySide6.QtCharts import QLineSeries, QValueAxis, QChart, QChartView, QAbstractSeries, QAbstractAxis
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget, QRubberBand, QGraphicsSceneMouseEvent, QGraphicsSceneHoverEvent
from PySide6.QtGui import  (QFont, QPainter, QFontMetrics, QColor, QContextMenuEvent, QPaintEvent, QMouseEvent, QWheelEvent, QPixmap, QKeyEvent, QResizeEvent)
from PySide6.QtCore import  QPointF, QRect, QRectF, Qt, QObject, Signal, QSize, QPoint, QSizeF

from scrutiny import tools
from scrutiny.gui import assets
from scrutiny.gui.themes import get_theme_prop, ScrutinyThemeProperties
from scrutiny.gui.tools.min_max import MinMax
from scrutiny.tools import validation

from scrutiny.tools.typing import *


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
    """An extension of the QValueAxis specific to Scrutiny"""

    _latched_range: Optional[Tuple[float, float]]

    @tools.copy_type(QValueAxis.__init__)
    def __init__(self, *args:Any, **kwargs:Any) -> None:
        super().__init__(*args, **kwargs)
        self._latched_range = None

    def emphasize(self) -> None:
        """Make the axis more visible. Expected t be triggered when a series is selected"""
        font = self.titleFont()
        font.setBold(True)
        self.setTitleFont(font)
    
    def deemphasize(self) -> None:
        """Put back the axis in its normal state. Expected t be triggered when a series is deselected"""
        font = self.titleFont()
        font.setBold(False)
        self.setTitleFont(font)

    def latch_range(self) -> None:
        """Make an internal copy of the actual range. Used for resetting the zoom on a paused graph"""
        self._latched_range = (self.min(), self.max())

    def reload_latched_range(self) -> None:
        """Reload the last range that was latched with ``latch_range`` if any."""
        if self._latched_range is not None:
            self.setRange(self._latched_range[0], self._latched_range[1])

    def get_latched_range(self) -> Tuple[float, float]:
        """Return the last range that was latched with ``latch_range``. Exception if nothing is latched"""
        assert self._latched_range is not None
        return self._latched_range

class ScrutinyValueAxisWithMinMax(ScrutinyValueAxis):
    """An extension of the QValueAxis that contains stats about the data it is tied to.
    Tracking the min/max value of the data can be used to autoset the range of the axis using a margin so that the line doesn't
    touch the chart boundaries
    """
    _minmax:MinMax
    """The min/max stats"""

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

    def valspan(self) -> Optional[float]:
        """Return the difference between the maximum value and the minimum value. ``None`` if no data"""
        high = self.maxval()
        lo = self.minval()
        if high is None or lo is None:
            return None
        return high-lo
    
    def maxval_with_margin(self, margin_ratio:float) -> Optional[float]:
        """Return the maximum value with a margin ratio that represent a fraction of the total value span"""
        span = self.valspan()
        v = self.maxval()
        margin_ratio = max(margin_ratio, 0)
        if span is None or v is None:
            return None
        return v + margin_ratio * span

    def minval_with_margin(self, margin_ratio:float) -> Optional[float]:
        """Return the minimum value with a margin ratio that represent a fraction of the total value span"""
        span = self.valspan()
        v = self.minval()
        margin_ratio = max(margin_ratio, 0)
        if span is None or v is None:
            return None
        return v - margin_ratio * span
    
    def set_minval(self, v:float) -> None:
        """Assign a minimum value to the chart. Doesn't change the effective range, but this new value will be used for ``autoset_range()``"""
        self._minmax.set_min(v)
    
    def set_maxval(self, v:float) -> None:
        """Assign a maximum value to the chart. Doesn't change the effective range, but this new value will be used for ``autoset_range()``"""
        self._minmax.set_max(v)
    
    def autoset_range(self, margin_ratio:float=0) -> None:
        """Set the axis range based on the min/max value of the data it contains"""
        minv, maxv = self.minval_with_margin(margin_ratio), self.maxval_with_margin(margin_ratio)
        if minv is None or maxv is None:
            self.setRange(0,1)
            return
        if minv==maxv:
            self.setRange(minv-1, maxv+1)
        else:
            self.setRange(minv, maxv)
    
    def apply_zoombox_x(self, zoombox:QRectF, margin_ratio:float=0, saturate_to_latched_range:bool=False) -> None:
        """
        Apply a zoom rectangle generated by a ScrutinyChartview. It's a rectangle where the left/right bounds represent the 
        X limits of the new zoom. Value sare normalized to p.u.
        A rectangle with x1=0.2, x2=0.8 will zoom in, remove 20% of the graph on each side.
        A rectangle with x1=-0.1, x2=1.3 will zoom out and offset a little to the right. 10% more on the left, 30% more on the right.
        """
        range = self.max() - self.min()
        
        minval = self.minval_with_margin(margin_ratio)
        maxval = self.maxval_with_margin(margin_ratio)
        if minval is None or maxval is None:
            return
        limit_low, limit_high = minval, maxval
        if saturate_to_latched_range:
            limit_low, limit_high = self.get_latched_range()
        new_low = max(zoombox.left() * range + self.min(), limit_low )
        new_high = min(zoombox.right() * range + self.min(), limit_high )
        if new_low==new_high:
            self.setRange(new_low-1, new_high+1)
        else:
            self.setRange( new_low, new_high )
    
    def apply_zoombox_y(self, zoombox:QRectF) -> None:
        """
        Apply a zoom rectangle generated by a ScrutinyChartview. It's a rectangle where the top/bottom bounds represent the 
        Y limits of the new zoom. Value sare normalized to p.u.
        A rectangle with y1=0.2, y2=0.8 will zoom in, remove 20% of the graph on each side.
        A rectangle with y1=-0.1, y2=1.3 will zoom out and offset a little to the right. 10% more on the left, 30% more on the right.
        """
        range = self.max() - self.min()
        new_low = (1-zoombox.bottom()) * range + self.min()
        new_high = (1-zoombox.top()) * range + self.min()
        if new_low==new_high:
            self.setRange(new_low-1, new_high+1)
        else:
            self.setRange( new_low, new_high )

class ScrutinyChart(QChart):

    def series(self) -> List[ScrutinyLineSeries]:   # type: ignore
        return [cast(ScrutinyLineSeries, s) for s in super().series()]
    
    def axisX(self, series:Optional[QAbstractSeries]=None) -> ScrutinyValueAxis:
        assert series is None
        return cast(ScrutinyValueAxis, super().axisX())
    
    def setAxisX(self, axis:QAbstractAxis, series:Optional[QAbstractSeries]=None) -> None:
        assert series is None
        if not isinstance(axis, ScrutinyValueAxis):
            raise ValueError("ScrutinyChart require a ScrutinyValueAxis")
        return super().setAxisX(axis)

class ScrutinyChartCallout(QGraphicsItem):
    """A callout that can be displayed when the user hover a point on a graph"""

    CALLOUT_RECT_DIST = 10
    """Distance between point marker and """
    PADDING = 5
    """padding between text and callout border"""

    class DisplaySide(enum.Enum):
        """Describe if the callout should eb shown above the point, or below"""
        Above = enum.auto()
        Below = enum.auto()

    _chart:ScrutinyChart
    """The chart on which the callout is drawn over"""
    _text:str
    """The text displayed into the callout"""
    _point_location_on_chart:QPointF
    """X/Y location of the point that this callout is tied to"""
    _font:QFont
    """The text font"""
    _text_rect:QRectF
    """The rectangle that contain the text"""
    _callout_rect:QRectF
    """The rectangle that contains the callout filled region"""
    _bouding_rect:QRectF
    """The bounding box, include the callout filled region and the marker on the point"""
    _color:QColor
    """Fill color"""
    _side:DisplaySide
    """Above/below state kept to make an hysteresis on position change"""
    _marker_radius : int
    """Size of the marker drawn on top of the hovered point"""


    def __init__(self, chart:ScrutinyChart) -> None:
        super().__init__(chart)
        self._chart = chart
        self._text = ''
        self._point_location_on_chart = QPointF()
        self._font  = QFont()
        self._text_rect = QRectF()
        self._callout_rect = QRectF()
        self._bouding_rect = QRectF()
        self._color = QColor()
        self._updown_side = self.DisplaySide.Above
        self._marker_radius = 0
        self.hide()
        self.setZValue(11)

    def _compute_geometry(self) -> None:
        self.prepareGeometryChange()
        metrics = QFontMetrics(self._font)  # Required to estimated required size
        self._text_rect = QRectF(metrics.boundingRect(QRect(0, 0, 150, 150), Qt.AlignmentFlag.AlignLeft, self._text))
        self._text_rect.translate(self.PADDING, self.PADDING)   # Add some padding around the text
        self._callout_rect = QRectF(self._text_rect.adjusted(-self.PADDING, -self.PADDING, self.PADDING, self.PADDING))
        self._marker_radius = get_theme_prop(ScrutinyThemeProperties.CHART_CALLOUT_MARKER_RADIUS)

        # DEcide if we should display above or below the point
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
            self._bouding_rect = self._callout_rect.adjusted(0,0,0,bounding_box_vertical_offset)
        elif self._updown_side == self.DisplaySide.Below:
            callout_rect_origin += QPointF(0, self.CALLOUT_RECT_DIST)
            self._bouding_rect = self._callout_rect.adjusted(0,-bounding_box_vertical_offset,0,0)
        
        callout_rect_origin -= QPointF(self._callout_rect.width()/2,0)  # Handle left overflow
        if callout_rect_origin.x() < 0:
            callout_rect_origin += QPointF(abs(callout_rect_origin.x()), 0)
        
        rect_right_x = callout_rect_origin.x() + self._callout_rect.width() # Handle right overflow
        if rect_right_x > chart_w:
            callout_rect_origin -= QPointF(rect_right_x - chart_w, 0)
        
        self.setPos(callout_rect_origin)


    def set_content(self, pos:QPointF, text:str, color:QColor) -> None:
        """Define everything we need to know to display a callout. Location, color and content"""
        self._point_location_on_chart = pos
        self._text = text
        self._color = color
        self._compute_geometry()

    def boundingRect(self) -> QRectF:
        # Inform QT about the size we need
        return self._bouding_rect

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget]=None) -> None:
        color_transparent = QColor(self._color)
        color_transparent.setAlphaF(0.7)
        painter.setBrush(color_transparent)   # Fill color
        painter.setPen(self._color)     # Border color
        painter.drawRoundedRect(self._callout_rect, 5, 5)
        anchor = QPointF(self.mapFromParent(self._point_location_on_chart))
        painter.setPen(QColor(0,0,0))     # Border color
        painter.drawEllipse(anchor, self._marker_radius, self._marker_radius)
        painter.setPen(QColor(0,0,0))
        painter.drawText(self._text_rect, self._text)


@dataclass
class ChartCursorMoved:
    xval:float
    series:List[ScrutinyLineSeries]

class ScrutinyChartView(QChartView):
    """A QChartView extended with some features specific to the Scrutiny GUI"""

    DEFAULT_WHEEL_ZOOM_FACTOR_PER_120DEG = 0.9
    """Zooming on wheel step (common mouses) will reduces the axes range to 90% of their previous value"""
    MIN_RUBBERBAND_SIZE_PX = 5
    """The minimum size the rubberband to emit a zoom event. Prevent accidental zooms"""

    class ChartCursor:
        MOVE_MARGIN = 4

        _enabled:bool
        """Enable flag"""
        _chartview:"ScrutinyChartView"
        """A reference to the owning Chartview"""
        _x:Optional[float]
        """The graphical X position. Computed from graph X value"""
        _xval:float
        """The graph x value pointed by the cursor"""
        _dragging:bool
        """``True`` When the user is moving the cursor"""

        def __init__(self, chartview:"ScrutinyChartView") -> None:
            self._enabled = False
            self._chartview = chartview
            self._x = None
            self._xval = 0
            self._dragging = False
        
        def is_in_drag_zone(self, p:QPointF) -> bool:
            if not self._enabled or self._x is None:
                return False
            
            plotarea = self._chartview.chart().plotArea()
            xcheck = (self._x-self.MOVE_MARGIN) < p.x() < (self._x+self.MOVE_MARGIN)
            ycheck = plotarea.top() < p.y() <  plotarea.bottom()

            return  xcheck and ycheck
        
        def enable(self) -> None:
            self._enabled = True
        
        def disable(self) -> None:
            self._enabled = False
            self._dragging = False
            self._x = None

        def is_enabled(self) -> bool:
            return self._enabled
        
        def set_xval(self, xval:float) -> None:
            self._xval = xval
            self.update()
    
        def xval(self) -> float:
            return self._xval
        
        def xpos(self) -> Optional[float]:
            return self._x
        
        def start_drag(self) -> None:
            if self._enabled:
                self._dragging = True
        
        def stop_drag(self) -> None:
            self._dragging = False
        
        def is_dragging(self) -> bool:
            return self._dragging
        
        def update(self) -> None:
            if self._enabled:
                self._x = self._chartview.xval_to_xpos(self._xval)
            else:
                self._x = None


    class InteractionMode(enum.Enum):
        SELECT_ZOOM=enum.auto()
        #DRAG=enum.auto()       # todo

    class ZoomType(enum.Enum):
        ZOOM_X=enum.auto()
        ZOOM_Y=enum.auto()
        ZOOM_XY=enum.auto()

    class _Signals(QObject):
        context_menu_event = Signal(QContextMenuEvent)
        """When the user right click the chartview"""
        zoombox_selected = Signal(QRectF)
        """When the zoom changes (through a wheel event or a rubber band)"""
        paint_finished = Signal()
        """When the chartview has finished repainting. USed for throttling the update rate"""
        key_pressed = Signal(QKeyEvent)
        """Forwarding the keypress event"""
        resized = Signal()
        """Emitted when the chartview is resized"""
        chart_cursor_moved = Signal(ChartCursorMoved)
        """Emitted when the chart cursor is moved and snapped to new series"""

    _rubber_band:QRubberBand
    _rubberband_origin:QPointF
    _rubberband_end:QPointF
    _rubberband_valid:bool
    _interaction_mode:InteractionMode
    _zoom_type:ZoomType
    _wheel_zoom_factor_per_120deg:float
    _zoom_allowed:bool
    _chart_cursor:ChartCursor

    @tools.copy_type(QChartView.__init__)
    def __init__(self, *args:Any, **kwargs:Any) -> None:
        super().__init__(*args, **kwargs)
        self._signals = self._Signals()
        self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._rubberband_origin = QPointF()
        self._rubberband_end = QPointF()
        self._rubberband_valid= False
        self._interaction_mode = self.InteractionMode.SELECT_ZOOM
        self._zoom_type = self.ZoomType.ZOOM_XY
        self._wheel_zoom_factor_per_120deg = self.DEFAULT_WHEEL_ZOOM_FACTOR_PER_120DEG
        self._zoom_allowed = False
        self._chart_cursor = self.ChartCursor(self)

    def resizeEvent(self, event:QResizeEvent) -> None:
        super().resizeEvent(event)
        self._chart_cursor.update()
        self._signals.resized.emit()

    def setChart(self, chart:QChart) -> None:
        assert isinstance(chart, ScrutinyChart)
        super().setChart(chart)
        
    def chart(self) -> ScrutinyChart:
        return cast(ScrutinyChart, super().chart())

    def allow_zoom(self, val:bool) -> None:
        """Allow/disallow zooming of the chart"""
        self._zoom_allowed = val

    def set_zoom_type(self, zoom_type:ZoomType) -> None:
        """Sets the zoom type of the wheel events and rubber band if interraction mode == ZOOM"""
        self._zoom_type = zoom_type
    
    def set_interaction_mode(self, interaction_mode:InteractionMode) -> None:
        self._interaction_mode = interaction_mode

    def cursor_enabled(self) -> bool:
        return self._chart_cursor.is_enabled()

    def enable_cursor(self) -> None:
        xaxis = self.chart().axisX()
        range = xaxis.max() - xaxis.min()
        self._chart_cursor.enable()
        self._chart_cursor.set_xval(range/2)
        self.update()

    def disable_cursor(self) -> None:
        self._chart_cursor.disable()
        self.update()

    def xpos_to_xval(self, xpos:float) -> Optional[float]:
        chart = self.chart()
        xaxis = chart.axisX()
        plotarea = self.chart().plotArea()
        plotarea_width = max(plotarea.width(), 1)
        if (xpos < plotarea.x()) or (xpos > plotarea.x() + plotarea_width):
            return None
        return (xpos - plotarea.x()) * (xaxis.max() - xaxis.min()) / plotarea_width
    
    def xval_to_xpos(self, xval:float) -> Optional[float]:
        chart = self.chart()
        xaxis = chart.axisX()
        plotarea = self.chart().plotArea()
        plotarea_width = max(plotarea.width(), 1)
        if xval < xaxis.min() or xval > xaxis.max():
            return None
        return (xval - xaxis.min()) * plotarea_width / (xaxis.max() - xaxis.min()) + plotarea.x()
    
    
    
    @property
    def signals(self) -> _Signals:
        return self._signals

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Let the integrator decide what goes inside that menu"""
        self._signals.context_menu_event.emit(event)

    def paintEvent(self, event:QPaintEvent) -> None:
        """We inform the outside world that repainting is finished. 
        We can use this to disable chart updates while repaint is in progress and reenable with the signal below.
        That's a way to throttle the update rate based on CPU usage"""
        super().paintEvent(event)
        self._signals.paint_finished.emit()
    
    def keyPressEvent(self, event:QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._signals.key_pressed.emit(event)
        return super().keyPressEvent(event)

    def wheelEvent(self, event:QWheelEvent) -> None:
        if not self._zoom_allowed:
            return
        # Zoom box can be outside the range 0-1. 
        # When min>0 & max<1 : it's a zoom in
        # When min<0 & max>1 : it's a zoom out
        plotarea = self.chart().plotArea()
        event_pos_mapped_to_chart = self.chart().mapFromParent(event.position())
        if plotarea.contains(event_pos_mapped_to_chart):
            event_pos_mapped_to_plotarea = event_pos_mapped_to_chart - plotarea.topLeft()
            angle = event.angleDelta().y()  # We asusme standard mouse with vertical wheel only.
            new_relative_range = self._wheel_zoom_factor_per_120deg ** (angle/120)
            relative_event = QPointF(
                event_pos_mapped_to_plotarea.x() / plotarea.width(),
                event_pos_mapped_to_plotarea.y() / plotarea.height()
            )

            range_diff = new_relative_range - 1 # new_range - old_range
            left_diff = relative_event.x() * range_diff
            top_diff = relative_event.y() * range_diff

            x1 = -left_diff
            x2 = x1 + new_relative_range
            y1 = -top_diff
            y2 = y1 + new_relative_range

            if self._zoom_type == self.ZoomType.ZOOM_X:
                new_rect = QRectF(QPointF(x1,0), QPointF(x2,1)).normalized()
            elif self._zoom_type == self.ZoomType.ZOOM_Y:
                new_rect = QRectF(QPointF(0,y1), QPointF(1,y2)).normalized()
            elif self._zoom_type == self.ZoomType.ZOOM_XY:
                new_rect = QRectF(QPointF(x1,y1), QPointF(x2,y2)).normalized()
            else:
                raise NotImplementedError("Unsupported zoom type")
            
            self._signals.zoombox_selected.emit(new_rect)    
        super().wheelEvent(event)

    def mousePressEvent(self, event:QMouseEvent) -> None: 
        if self._chart_cursor.is_in_drag_zone(event.pos().toPointF()):
            event.accept()
            self._chart_cursor.start_drag()
        elif self._interaction_mode == self.InteractionMode.SELECT_ZOOM and self._zoom_allowed:
            # In zoom mode, we initialize a rubber band
            event.accept()
            plotarea = self.chart().plotArea()
            plotarea_mapped_to_chartview =self.chart().mapRectToParent(plotarea)
            event_saturated = QPointF(  # We saturate to the limits of the plot area so the rubber band is inside
                min(max(event.pos().x(), plotarea.left()), plotarea.right()), 
                min(max(event.pos().y(), plotarea.top()), plotarea.bottom())
                )
            event_mapped_to_chart = self.chart().mapFromParent(event_saturated)

            if self._zoom_type == self.ZoomType.ZOOM_XY:
                self._rubberband_origin = event_mapped_to_chart
            elif self._zoom_type == self.ZoomType.ZOOM_X:
                self._rubberband_origin = QPointF(event_mapped_to_chart.x(), plotarea_mapped_to_chartview.top())
            elif self._zoom_type == self.ZoomType.ZOOM_Y:
                self._rubberband_origin = QPointF(plotarea_mapped_to_chartview.left(), event_mapped_to_chart.y())
            else:
                raise NotImplementedError("Unknown zoom type")
            self._rubber_band.setGeometry(QRect(self._rubberband_origin.toPoint(), QSize()))
            self._rubber_band.show()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event:QMouseEvent) -> None:
        mouse_cursor = Qt.CursorShape.ArrowCursor
        if self._chart_cursor.is_dragging():
            mouse_cursor = Qt.CursorShape.SizeHorCursor
            xval = self.xpos_to_xval(event.pos().x())
            if xval is not None:
                snap_xval, snapped_series = self._get_closest_x_to_snap_to(xval)
                if snap_xval is not None:
                    self._chart_cursor.set_xval(snap_xval)
                    self.update()
                    self._signals.chart_cursor_moved.emit( ChartCursorMoved(snap_xval, snapped_series) )
        elif self._chart_cursor.is_in_drag_zone(event.pos().toPointF()):
            mouse_cursor = Qt.CursorShape.SizeHorCursor

        self.viewport().setCursor(mouse_cursor)

        if self._interaction_mode == self.InteractionMode.SELECT_ZOOM and self._zoom_allowed:
            # In zoom mode, we resize the rubber band
            event.accept()
            if self._rubber_band.isVisible():   # There's a rubber band active (MousePress happened before)
                plotarea = self.chart().plotArea()
                event_saturated = QPointF(  # We saturate to the limits of the plot area so the rubberband stays inside
                    min(max(event.pos().x(), plotarea.left()), plotarea.right()), 
                    min(max(event.pos().y(), plotarea.top()), plotarea.bottom())
                    )
                event_mapped_to_chart = self.chart().mapFromParent(event_saturated)
                plotarea_mapped_to_chartview = self.chart().mapRectToParent(plotarea)
                if self._zoom_type == self.ZoomType.ZOOM_XY:
                    self._rubberband_end = event_mapped_to_chart
                elif self._zoom_type == self.ZoomType.ZOOM_X:
                    self._rubberband_end = QPointF(event_mapped_to_chart.x(), plotarea_mapped_to_chartview.bottom())
                elif self._zoom_type == self.ZoomType.ZOOM_Y:
                    self._rubberband_end = QPointF(plotarea_mapped_to_chartview.right(), event_mapped_to_chart.y())
                else:
                    raise NotImplementedError("Unknown zoom type")
                self._rubberband_valid = True
                self._rubber_band.setGeometry(QRect(self._rubberband_origin.toPoint(), self._rubberband_end.toPoint()).normalized())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event:QMouseEvent) -> None:
        """When the mouse is released on the chartview"""

        if self._chart_cursor.is_dragging():
            self._chart_cursor.stop_drag()

        if self._interaction_mode == self.InteractionMode.SELECT_ZOOM and self._zoom_allowed:
            # In zoom mode, we release the rubberband and compute a new zoom box that we will broadcast
            event.accept()
            if self._rubberband_valid:  # Paranoid check to avoid using stalled values
                plotarea_mapped_to_chartview = self.chart().mapRectToParent(self.chart().plotArea())
                diffabs_x = abs(self._rubberband_end.x() - self._rubberband_origin.x())
                diffabs_y = abs(self._rubberband_end.y() - self._rubberband_origin.y())
                
                # Required to have a minimal size, otherwise accidental click can do a zoom on a tiny space making everything disappear
                # Rubberband starts from edge when the user clicked outsde the plotarea. Makes it easy to have a rebberbad of 0px or 1 px wide by mistake
                if diffabs_x > self.MIN_RUBBERBAND_SIZE_PX and diffabs_y > self.MIN_RUBBERBAND_SIZE_PX:   
                    relative_origin = QPointF(
                        (self._rubberband_origin.x() - plotarea_mapped_to_chartview.x()) / plotarea_mapped_to_chartview.width(),
                        (self._rubberband_origin.y() - plotarea_mapped_to_chartview.y()) / plotarea_mapped_to_chartview.height()
                    )
                    relative_end = QPointF(
                        (self._rubberband_end.x() - plotarea_mapped_to_chartview.x()) / plotarea_mapped_to_chartview.width(),
                        (self._rubberband_end.y() - plotarea_mapped_to_chartview.y()) / plotarea_mapped_to_chartview.height()
                    )
                    self._signals.zoombox_selected.emit(QRectF(relative_origin, relative_end).normalized())
        self._rubber_band.hide()
        self._rubberband_valid = False
        super().mouseReleaseEvent(event)

    def drawForeground(self, painter:QPainter, rect:Union[QRectF, QRect]) -> None:
        super().drawForeground(painter, rect)
        chart = self.chart()
        plotarea = chart.plotArea()
        if self._chart_cursor.is_enabled():
            cursor_xpos = self.xval_to_xpos(self._chart_cursor.xval())
            if cursor_xpos:
                y1 = plotarea.y()
                y2 = plotarea.y() + plotarea.height()
                painter.setPen(QColor(0,0,0))
                painter.setBrush(QColor(0,0,0))
                painter.drawPolygon([QPointF(cursor_xpos,y1), QPointF(cursor_xpos-3,y1-4), QPointF(cursor_xpos+3,y1-4)])
                painter.setPen(QColor(255,0,0))
                painter.drawLine(QPointF(cursor_xpos, y1), QPointF(cursor_xpos,y2))

    def _get_closest_x_to_snap_to(self, xval:float) -> Tuple[Optional[float], List[ScrutinyLineSeries]]:
        @dataclass
        class SeriesXValPair:
            series:ScrutinyLineSeries
            xval:float

        chart = self.chart()
        candidates:List[SeriesXValPair] = []
        for series in chart.series():
            point = series.search_closest_monotonic(xval)
            if point is not None:
                candidates.append( SeriesXValPair(series, point.x()) )

        if len(candidates) == 0:
            return (None, [])
        
        candidates.sort( key=lambda x: abs(x.xval - xval) ) # Sort by distance
        closest = candidates[0].xval
        selected_series = [x.series for x in candidates if x.xval == closest]
        return closest, selected_series


class ScrutinyChartToolBar(QGraphicsItem):
    """A toolbar designed to go at the top of a Scrutiny Chart. Can be tied to a Chartview and enable control of it"""
    class ToolbarButton(QGraphicsItem):
        """Represent a button that goes in the toolbar"""
        class _Signals(QObject):
            clicked = Signal()
            """Emitted on mouse release if the mouse pressed happened on the button"""

        _icon_id:assets.Icons
        """The icon of the button, identified by the it's ID in the icon repo"""
        _icon_size:QSizeF
        """Size of the icon"""
        _pixmap:QPixmap
        """The button icon as a pixmap resized for the button"""
        _bounding_rect:QRectF
        """The bounding box for the graphic scene"""
        _is_hovered:bool
        """True when the mouse is above this button"""
        _is_pressed:bool
        """True when the mouse left button is pressed on this button"""
        _is_selected:bool
        """True when the button is set as 'selected' programatically"""

        ICON_SIZE = 20  # Square icons
        PADDING_X = 5
        PADDING_Y = 2

        def __init__(self, toolbar:"ScrutinyChartToolBar", icon:assets.Icons) -> None:
            super().__init__(toolbar)
            self._signals = self._Signals()
            self._is_hovered = False
            self._is_pressed = False
            self._is_selected = False
            self.setAcceptHoverEvents(True) # Required for hoverEnter and hoverLeaves
            self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)     # No need for right button
            self.set_icon(icon)
        
        @property
        def signals(self) -> _Signals:
            return self._signals
        
        def set_icon(self, icon:assets.Icons, size:Optional[float] = None) -> None:
            """Changes the icon of the button"""
            self._icon_id = icon
            if size is None:
                self.set_icon_size(self.ICON_SIZE)
            else:
                self.set_icon_size(size)
            self.update()
            
        def set_icon_size(self, icon_size:float) -> None:
            """Resize the icon """
            self.prepareGeometryChange()
            self._icon_size = QSizeF(icon_size,icon_size)
            self._pixmap = assets.load_medium_icon_as_pixmap(self._icon_id).scaled(
                self._icon_size.toSize(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
                )
            
            # Add internal padding. 2x for left/right and top/bottom
            size_padded = self._icon_size + QSizeF(2*self.PADDING_X, 2*self.PADDING_Y)
            self._bounding_rect = QRectF(QPointF(0,0), size_padded)
            self.update()
        
        def boundingRect(self) -> QRectF:
            """The zone where we draw"""
            return self._bounding_rect 
        
        def select(self) -> None:
            """Set the button as 'selected' which change the color"""
            self._is_selected = True
            self.update()
        
        def deselect(self) -> None:
            """Set the button as 'deselected' which change the color"""
            self._is_selected = False
            self.update()

        def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget]=None) -> None:
            HOVERED_COLOR = get_theme_prop(ScrutinyThemeProperties.CHART_TOOLBAR_HOVERED_BUTTON_COLOR) 
            HOVERED_SELECTED_BORDER_COLOR = get_theme_prop(ScrutinyThemeProperties.CHART_TOOLBAR_HOVERED_SELECTED_BORDER_COLOR)  
            SELECTED_COLOR = get_theme_prop(ScrutinyThemeProperties.CHART_TOOLBAR_SELECTED_COLOR) 
            PRESSED_COLOR = get_theme_prop(ScrutinyThemeProperties.CHART_TOOLBAR_PRESSED_COLOR) 
            # If the is a focus on the button, draw a background
            if self._is_pressed or self._is_selected or self._is_hovered:
                
                if self._is_pressed:
                    painter.setPen(PRESSED_COLOR)
                    painter.setBrush(PRESSED_COLOR)
                else:
                    if self._is_selected:
                        if self._is_hovered:
                            painter.setPen(HOVERED_SELECTED_BORDER_COLOR)
                        else:
                            painter.setPen(SELECTED_COLOR)
                        painter.setBrush(SELECTED_COLOR)
                    elif self._is_hovered:
                        painter.setPen(HOVERED_COLOR)
                        painter.setBrush(HOVERED_COLOR)
                painter.drawRect(self._bounding_rect)

            painter.drawPixmap(QPoint(self.PADDING_X,self.PADDING_Y), self._pixmap)

        
        def mousePressEvent(self, event:QGraphicsSceneMouseEvent) -> None:
            # Used to generate click event
            event.accept()
            self._is_pressed = True # Will make the color different
            self.update()

        def mouseReleaseEvent(self, event:QGraphicsSceneMouseEvent) -> None:
            event.accept()
            if self._is_pressed:
                self._signals.clicked.emit()
            self._is_pressed = False
            self.update()

        def hoverEnterEvent(self, event:QGraphicsSceneHoverEvent) -> None:
            event.accept()
            self._is_hovered = True
            self.update()
        
        def hoverLeaveEvent(self, event:QGraphicsSceneHoverEvent) -> None:
            event.accept()
            self._is_hovered = False
            self._is_pressed = False
            self.update()
            

    BUTTON_SPACING = 0
    """ Spaces between each buttons"""
    _chart:ScrutinyChart
    """The chart on which we draw the toolbar"""
    _chartview:ScrutinyChartView
    """The chartview that the toolbar controls"""
    _btn_enable_cursor:ToolbarButton
    """ Enable/disable the graph cursor"""
    _btn_zoom_xy:ToolbarButton
    """ Zoom XY button"""
    _btn_zoom_x:ToolbarButton
    """ Zoom X button"""
    _btn_zoom_y:ToolbarButton
    """ Zoom Y button"""
    _bounding_rect : QRectF
    """The zone where we draw"""
    _buttons : List[ToolbarButton]
    """All the buttons in order from left to right"""

    def __init__(self, chartview:ScrutinyChartView) -> None:
        validation.assert_type(chartview, 'chartview', ScrutinyChartView)
        super().__init__(chartview.chart())
        self._chart = chartview.chart()
        self._chartview = chartview
        
        self._btn_enable_cursor = self.ToolbarButton(self, assets.Icons.GraphCursor)
        self._btn_zoom_xy = self.ToolbarButton(self, assets.Icons.ZoomXY)
        self._btn_zoom_x = self.ToolbarButton(self, assets.Icons.ZoomX)
        self._btn_zoom_y = self.ToolbarButton(self, assets.Icons.ZoomY)
        self._bounding_rect = QRectF()

        self._buttons = [self._btn_enable_cursor, self._btn_zoom_xy, self._btn_zoom_x, self._btn_zoom_y]
        self._chart.geometryChanged.connect(self._update_geometry)
        
        self._btn_enable_cursor.signals.clicked.connect(self._enable_disable_cursor)
        self._btn_zoom_xy.signals.clicked.connect(self._zoom_xy)
        self._btn_zoom_x.signals.clicked.connect(self._zoom_x)
        self._btn_zoom_y.signals.clicked.connect(self._zoom_y)

        self._btn_zoom_xy.select()


    def disable_chart_cursor(self) -> None:
        self._chartview.disable_cursor()
        self._btn_enable_cursor.deselect()

    def enable_chart_cursor(self) -> None:
        self._chartview.enable_cursor()
        self._btn_enable_cursor.select()

    def toggle_chart_cursor(self) -> None:
        if self._chartview.cursor_enabled():
            self.disable_chart_cursor()
        else:
            self.enable_chart_cursor()

    def _enable_disable_cursor(self) -> None:
        if self._chartview.cursor_enabled():
            self._chartview.disable_cursor()
            self._btn_enable_cursor.deselect()
        else:
            self._chartview.enable_cursor()
            self._btn_enable_cursor.select()

    def _zoom_x(self) -> None:
        """Called when Zoom X button is clicked"""

        # Change the chartview behavior
        self._chartview.set_interaction_mode(ScrutinyChartView.InteractionMode.SELECT_ZOOM)
        self._chartview.set_zoom_type(ScrutinyChartView.ZoomType.ZOOM_X)
        
        # Visual feedback
        self._btn_zoom_x.select()
        self._btn_zoom_xy.deselect()
        self._btn_zoom_y.deselect()
    
    def _zoom_y(self) -> None:
        # Change the chartview behavior
        self._chartview.set_interaction_mode(ScrutinyChartView.InteractionMode.SELECT_ZOOM)
        self._chartview.set_zoom_type(ScrutinyChartView.ZoomType.ZOOM_Y)
        
        # Visual feedback
        self._btn_zoom_y.select()
        self._btn_zoom_xy.deselect()
        self._btn_zoom_x.deselect()
    
    def _zoom_xy(self) -> None:
        # Change the chartview behavior
        self._chartview.set_interaction_mode(ScrutinyChartView.InteractionMode.SELECT_ZOOM)
        self._chartview.set_zoom_type(ScrutinyChartView.ZoomType.ZOOM_XY)
        # Visual feedback
        self._btn_zoom_xy.select()
        self._btn_zoom_x.deselect()
        self._btn_zoom_y.deselect()

    def _update_geometry(self) -> None:
        """Recompute all the internal drawing dimensions"""
        self.prepareGeometryChange()
        chart_size = self._chart.size()
        
        #We will scan all the buttons from left to right and decide how much space we need
        width_cursor = float(0) 
        required_height = float(0)
        for i in range(len(self._buttons)):
            button = self._buttons[i]
            r = button.boundingRect()
            required_height = max(required_height, r.height())  # We need as much height as the tallest button (doesn't matter, they're squares.)
            button.setPos(width_cursor, 0)  # This button new location. They draw from 0,0 internally
            width_cursor += r.width()
            if i < len(self._buttons):
                width_cursor += self.BUTTON_SPACING
        required_width = width_cursor
        size = QSizeF(required_width, required_height)
        origin = QPointF(chart_size.width()/2 - required_width/2, 0)
        self.setPos(origin)
        self._bounding_rect = QRectF(QPointF(0,0), size)
    
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget]=None) -> None:
        pass    # Nothing to do. Need to exist

    def boundingRect(self) -> QRectF:
        return self._bounding_rect
