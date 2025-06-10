#    base_chart.py
#        Some customized extensions of the QT Charts for the Scrutiny GUI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = [
    'ScrutinyLineSeries',
    'ScrutinyValueAxis',
    'ScrutinyValueAxisWithMinMax',
    'ScrutinyChart',
    'ScrutinyChartCallout',
    'ScrutinyChartView',
    'ScrutinyChartToolBar',
    'ChartCursorMovedData'
]

import enum
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from PySide6.QtCharts import QLineSeries, QValueAxis, QChart, QChartView, QAbstractSeries, QAbstractAxis
from PySide6.QtWidgets import (QGraphicsItem, QStyleOptionGraphicsItem, QWidget, QRubberBand,
                               QGraphicsSceneMouseEvent, QGraphicsSceneHoverEvent, QHBoxLayout, QLabel,
                               QGraphicsScene)
from PySide6.QtGui import (QFont, QPainter, QFontMetrics, QColor, QContextMenuEvent,
                           QPaintEvent, QMouseEvent, QWheelEvent, QPixmap, QKeyEvent,
                           QResizeEvent, QStandardItem)
from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QObject, Signal, QSize, QPoint, QSizeF, QTimer

from scrutiny import tools
from scrutiny.gui import assets
from scrutiny.gui.themes import scrutiny_get_theme_prop, ScrutinyThemeProperties, scrutiny_get_theme
from scrutiny.gui.tools.min_max import MinMax

from scrutiny.tools import validation
from scrutiny.gui.widgets.graph_signal_tree import GraphSignalTree

from scrutiny.tools.typing import *


class ScrutinyLineSeries(QLineSeries):

    def emphasize(self) -> None:
        """Emphasize the line serie sby making it bolder"""
        pen = self.pen()
        pen.setWidth(scrutiny_get_theme_prop(ScrutinyThemeProperties.CHART_EMPHASIZED_SERIES_WIDTH))
        self.setPen(pen)

    def deemphasize(self) -> None:
        """Remove the emphasis and put back the line to its normal size"""
        pen = self.pen()
        pen.setWidth(scrutiny_get_theme_prop(ScrutinyThemeProperties.CHART_NORMAL_SERIES_WIDTH))
        self.setPen(pen)

    def search_closest_non_monotonic(self, xval: float, min_x: Optional[float] = None, max_x: Optional[float] = None) -> Optional[QPointF]:
        pass

    def search_closest_monotonic(self, xval: float, min_x: Optional[float] = None, max_x: Optional[float] = None) -> Optional[QPointF]:
        """Search for the closest point using the XAxis. Assume a monotonic X axis.
        If the values are not monotonic : undefined behavior

        :param xval: Target point
        :param min_x: Lowest allowed x value
        :param max_x: Highest allowed x value
        """

        # This function is fully unit tested.
        points = self.points()
        if len(points) == 0:
            return None

        max_x_index = len(points) - 1
        if max_x is not None:
            max_x_index = bisect_right(points, max_x, key=lambda p: p.x()) - 1

        min_x_index = 0
        if min_x is not None:
            min_x_index = bisect_left(points, min_x, key=lambda p: p.x())

        if max_x_index < min_x_index:
            return None  # Range is too small. Between 2 points

        index = bisect_left(points, xval, key=lambda p: p.x())
        index = max(min(index, max_x_index), min_x_index)
        p_after = points[index]

        # exactly on it or right after the minimum
        if index == min_x_index:
            return p_after
        p_before = points[index - 1]  # Guaranteed to be possible. min_x_index is 0 or more, so length is > 0 here

        # We are between 2 points inside the range. Take the closest
        dist_to_p_after = abs(p_after.x() - xval)
        dist_to_p_before = abs(p_before.x() - xval)
        return p_after if dist_to_p_after <= dist_to_p_before else p_before


class ScrutinyValueAxis(QValueAxis):
    """An extension of the QValueAxis specific to Scrutiny"""

    _latched_range: Optional[Tuple[float, float]]

    @tools.copy_type(QValueAxis.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._latched_range = None
        palette = scrutiny_get_theme().palette()
        self.setGridLineColor(palette.window().color())
        self.setLinePenColor(palette.window().color())
        self.setLabelsBrush(palette.text())
        self.setTitleBrush(palette.text())

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
    _minmax: MinMax
    """The min/max stats"""

    @tools.copy_type(ScrutinyValueAxis.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._minmax = MinMax()

    def update_minmax(self, v: float) -> None:
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
        return high - lo

    def maxval_with_margin(self, margin_ratio: float) -> Optional[float]:
        """Return the maximum value with a margin ratio that represent a fraction of the total value span"""
        span = self.valspan()
        v = self.maxval()
        margin_ratio = max(margin_ratio, 0)
        if span is None or v is None:
            return None
        return v + margin_ratio * span

    def minval_with_margin(self, margin_ratio: float) -> Optional[float]:
        """Return the minimum value with a margin ratio that represent a fraction of the total value span"""
        span = self.valspan()
        v = self.minval()
        margin_ratio = max(margin_ratio, 0)
        if span is None or v is None:
            return None
        return v - margin_ratio * span

    def set_minval(self, v: float) -> None:
        """Assign a minimum value to the chart. Doesn't change the effective range, but this new value will be used for ``autoset_range()``"""
        self._minmax.set_min(v)

    def set_maxval(self, v: float) -> None:
        """Assign a maximum value to the chart. Doesn't change the effective range, but this new value will be used for ``autoset_range()``"""
        self._minmax.set_max(v)

    def autoset_range(self, margin_ratio: float = 0) -> None:
        """Set the axis range based on the min/max value of the data it contains"""
        minv, maxv = self.minval_with_margin(margin_ratio), self.maxval_with_margin(margin_ratio)
        if minv is None or maxv is None:
            self.setRange(0, 1)
            return
        if minv == maxv:
            self.setRange(minv - 1, maxv + 1)
        else:
            self.setRange(minv, maxv)

    def apply_zoombox_x(self, zoombox: QRectF, margin_ratio: float = 0, saturate_to_latched_range: bool = False) -> None:
        """
        Apply a zoom rectangle generated by a ScrutinyChartview. It's a rectangle where the left/right bounds represent the 
        X limits of the new zoom. Values are normalized to p.u.
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
        new_low = max(zoombox.left() * range + self.min(), limit_low)
        new_high = min(zoombox.right() * range + self.min(), limit_high)
        if new_low == new_high:
            self.setRange(new_low - 1, new_high + 1)
        else:
            self.setRange(new_low, new_high)

    def apply_zoombox_y(self, zoombox: QRectF) -> None:
        """
        Apply a zoom rectangle generated by a ScrutinyChartview. It's a rectangle where the top/bottom bounds represent the 
        Y limits of the new zoom. Value sare normalized to p.u.
        A rectangle with y1=0.2, y2=0.8 will zoom in, remove 20% of the graph on each side.
        A rectangle with y1=-0.1, y2=1.3 will zoom out and offset a little to the right. 10% more on the left, 30% more on the right.
        """
        range = self.max() - self.min()
        new_low = (1 - zoombox.bottom()) * range + self.min()
        new_high = (1 - zoombox.top()) * range + self.min()
        if new_low == new_high:
            self.setRange(new_low - 1, new_high + 1)
        else:
            self.setRange(new_low, new_high)


class ScrutinyChart(QChart):

    _mouse_callout: "ScrutinyChartCallout"
    """A callout (popup bubble) that shows the values on hover"""
    _mouse_callout_hide_timer: QTimer
    """A timer to trigger the hiding of the graph callout. Avoid fast show/hide"""

    @tools.copy_type(QChart.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._mouse_callout = ScrutinyChartCallout(self)
        self._mouse_callout_hide_timer = QTimer()
        self._mouse_callout_hide_timer.setInterval(250)
        self._mouse_callout_hide_timer.setSingleShot(True)
        self._mouse_callout_hide_timer.timeout.connect(self._callout_hide_timer_slot)
        self.layout().setContentsMargins(0, 0, 0, 0)
        palette = scrutiny_get_theme().palette()
        self.setBackgroundBrush(palette.base())
        self.setTitleBrush(palette.text())
        self.legend().setLabelBrush(palette.text())

    def _callout_hide_timer_slot(self) -> None:
        self.hide_mouse_callout()

    def hide_mouse_callout(self) -> None:
        self._mouse_callout.hide()

    def update_mouse_callout_state(self, series: ScrutinyLineSeries, visible: bool, val_point: QPointF, signal_name: str) -> None:
        """Show or hide the callout with the X/Y value triggered by mouse move"""
        xaxis = self.axisX()
        if visible and xaxis is not None:
            closest_real_point = series.search_closest_monotonic(val_point.x(), xaxis.min(), xaxis.max())
            if closest_real_point is not None:
                self._mouse_callout_hide_timer.stop()
                txt = f"{signal_name}\nX: {closest_real_point.x()}\nY: {closest_real_point.y()}"
                pos = self.mapToPosition(closest_real_point, series)
                color = series.color()
                self._mouse_callout.set_content(pos, txt, color)
                self._mouse_callout.show()
        else:
            self._mouse_callout_hide_timer.start()

    def series(self) -> List[ScrutinyLineSeries]:   # type: ignore
        return [cast(ScrutinyLineSeries, s) for s in super().series()]

    def axisX(self, series: Optional[QAbstractSeries] = None) -> ScrutinyValueAxis:
        assert series is None
        return cast(ScrutinyValueAxis, super().axisX())

    def axisY(self, series: Optional[QAbstractSeries] = None) -> ScrutinyValueAxis:
        return cast(ScrutinyValueAxis, super().axisY(series))

    def setAxisX(self, axis: QAbstractAxis, series: Optional[QAbstractSeries] = None) -> None:
        assert series is None
        assert isinstance(axis, ScrutinyValueAxis)
        return super().setAxisX(axis)

    def setAxisY(self, axis: QAbstractAxis, series: Optional[QAbstractSeries] = None) -> None:
        assert isinstance(axis, ScrutinyValueAxis)
        return super().setAxisX(axis, series)

    def pos_to_val(self, pos: QPointF, yaxis: ScrutinyValueAxis, clip_if_outside: bool = False) -> Optional[QPointF]:
        """Convert a screen X/Y position relative to the chart origin into a graph value point"""
        xaxis = self.axisX()
        if xaxis is None:
            return None
        plotarea = self.plotArea()

        plotarea_width = plotarea.width()
        plotarea_height = plotarea.height()
        if plotarea_width == 0 or plotarea_height == 0:
            return None

        xval: Optional[float] = None
        yval: Optional[float] = None
        if pos.x() < plotarea.x():
            xval = xaxis.min()

        if pos.x() > plotarea.x() + plotarea_width:
            xval = xaxis.max()

        # Y-Axis is reversed
        if pos.y() < plotarea.y():
            yval = yaxis.max()

        if pos.y() > plotarea.y() + plotarea_height:
            yval = yaxis.min()

        if (xval is not None or yval is not None) and not clip_if_outside:
            return None

        if xval is None:
            xval = (pos.x() - plotarea.x()) * (xaxis.max() - xaxis.min()) / plotarea_width + xaxis.min()
        if yval is None:
            yval = (plotarea.y() + plotarea_height - pos.y()) * (yaxis.max() - yaxis.min()) / plotarea_height + yaxis.min()
        return QPointF(xval, yval)

    def xpos_to_xval(self, xpos: float, clip_if_outside: bool = False) -> Optional[float]:
        """Convert a screen X position relative to the chart origin into a graph X axis value"""
        xaxis = self.axisX()
        assert xaxis is not None
        plotarea = self.plotArea()
        plotarea_width = max(plotarea.width(), 1)
        if xpos < plotarea.x():
            return xaxis.min() if clip_if_outside else None

        if xpos > plotarea.x() + plotarea_width:
            return xaxis.max() if clip_if_outside else None

        return (xpos - plotarea.x()) * (xaxis.max() - xaxis.min()) / plotarea_width + xaxis.min()

    def val_to_pos(self, val: QPointF, yaxis: ScrutinyValueAxis, clip_if_outside: bool = False) -> Optional[QPointF]:
        """Convert a graph value point into a screen X/Y position relative to the chart origin"""
        xaxis = self.axisX()
        assert xaxis is not None
        assert yaxis is not None
        plotarea = self.plotArea()

        plotarea_width = plotarea.width()
        plotarea_height = plotarea.height()
        if plotarea_width == 0 or plotarea_height == 0:
            return None
        xpos: Optional[float] = None
        ypos: Optional[float] = None

        if val.x() < xaxis.min():
            xpos = plotarea.x()

        if val.x() > xaxis.max():
            xpos = plotarea.x() + plotarea_width

        if val.y() < yaxis.min():
            ypos = plotarea.y() + plotarea_height

        if val.y() > yaxis.max():
            ypos = plotarea.y()

        if (xpos is not None or ypos is not None) and not clip_if_outside:
            return None

        if xpos is None:    # Not outside
            xpos = (val.x() - xaxis.min()) * plotarea_width / (xaxis.max() - xaxis.min()) + plotarea.x()
        if ypos is None:    # Not outside
            ypos = plotarea.y() + plotarea_height - (val.y() - yaxis.min()) * plotarea_height / (yaxis.max() - yaxis.min())
        return QPointF(xpos, ypos)

    def xval_to_xpos(self, xval: float, clip_if_outside: bool = False) -> Optional[float]:
        """Convert a  graph X axis value into a screen X position relative to the chart origin"""
        xaxis = self.axisX()
        assert xaxis is not None
        plotarea = self.plotArea()
        plotarea_width = max(plotarea.width(), 1)
        if xval < xaxis.min():
            return plotarea.x() if clip_if_outside else None
        if xval > xaxis.max():
            return plotarea.x() + plotarea_width if clip_if_outside else None
        return (xval - xaxis.min()) * plotarea_width / (xaxis.max() - xaxis.min()) + plotarea.x()

    def dx_to_dvalx(self, dx: float) -> float:
        """Compute a pixel delta along the X axis into a change in X-Axis value"""
        xaxis = self.axisX()
        assert xaxis is not None
        plotarea_width = self.plotArea().width()
        if plotarea_width == 0:
            return 0
        return dx / plotarea_width * (xaxis.max() - xaxis.min())

    def dy_to_dvaly(self, dy: float, yaxis: ScrutinyValueAxis) -> float:
        """Compute a pixel delta along the Y axis into a change in Y-Axis value"""
        assert yaxis is not None
        plotarea_height = self.plotArea().height()
        if plotarea_height == 0:
            return 0
        return -dy / plotarea_height * (yaxis.max() - yaxis.min())

    def apply_drag(self, dx: int, dy: int) -> None:
        """Move the chart by adjusting the axes range.
        Triggered by a chartview chart_dragged signal."""
        # Apply X-Axis
        dvalx = self.dx_to_dvalx(dx)
        xaxis = self.axisX()
        if xaxis is None:
            return
        xaxis.setRange(xaxis.min() - dvalx, xaxis.max() - dvalx)

        # Apply all Y-Axes
        yaxis_set = set([self.axisY(series) for series in self.series()])   # remove duplicate
        for yaxis in yaxis_set:
            if yaxis is not None:
                dvaly = self.dy_to_dvaly(dy, yaxis)
                yaxis.setRange(yaxis.min() - dvaly, yaxis.max() - dvaly)


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

    _chart: ScrutinyChart
    """The chart on which the callout is drawn over"""
    _text: str
    """The text displayed into the callout"""
    _point_location_on_chart: QPointF
    """X/Y location of the point that this callout is tied to"""
    _text_color: QColor
    """The text color coming from the theme"""
    _font: QFont
    """The text font"""
    _text_rect: QRectF
    """The rectangle that contain the text"""
    _callout_rect: QRectF
    """The rectangle that contains the callout filled region"""
    _bouding_rect: QRectF
    """The bounding box, include the callout filled region and the marker on the point"""
    _color: QColor
    """Fill color"""
    _side: DisplaySide
    """Above/below state kept to make an hysteresis on position change"""
    _marker_radius: int
    """Size of the marker drawn on top of the hovered point"""

    def __init__(self, chart: ScrutinyChart) -> None:
        super().__init__(chart)
        self._chart = chart
        self._text = ''
        self._point_location_on_chart = QPointF()
        self._font = QFont()
        self._text_rect = QRectF()
        self._text_color = scrutiny_get_theme().palette().text().color()
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
        self._marker_radius = scrutiny_get_theme_prop(ScrutinyThemeProperties.CHART_CALLOUT_MARKER_RADIUS)

        # DEcide if we should display above or below the point
        chart_h = self._chart.size().height()
        chart_w = self._chart.size().width()
        if self._point_location_on_chart.y() <= chart_h / 3:
            self._updown_side = self.DisplaySide.Below
        elif self._point_location_on_chart.y() >= chart_h * 2 / 3:
            self._updown_side = self.DisplaySide.Above
        else:
            pass    # Keep last. Makes an hysteresis

        callout_rect_origin = QPointF(self._point_location_on_chart)
        bounding_box_vertical_offset = self._marker_radius + self.CALLOUT_RECT_DIST
        if self._updown_side == self.DisplaySide.Above:
            callout_rect_origin -= QPointF(0, self._callout_rect.height() + self.CALLOUT_RECT_DIST)
            self._bouding_rect = self._callout_rect.adjusted(0, 0, 0, bounding_box_vertical_offset)
        elif self._updown_side == self.DisplaySide.Below:
            callout_rect_origin += QPointF(0, self.CALLOUT_RECT_DIST)
            self._bouding_rect = self._callout_rect.adjusted(0, -bounding_box_vertical_offset, 0, 0)

        callout_rect_origin -= QPointF(self._callout_rect.width() / 2, 0)  # Handle left overflow
        if callout_rect_origin.x() < 0:
            callout_rect_origin += QPointF(abs(callout_rect_origin.x()), 0)

        rect_right_x = callout_rect_origin.x() + self._callout_rect.width()  # Handle right overflow
        if rect_right_x > chart_w:
            callout_rect_origin -= QPointF(rect_right_x - chart_w, 0)

        self.setPos(callout_rect_origin)

    def set_content(self, pos: QPointF, text: str, color: QColor) -> None:
        """Define everything we need to know to display a callout. Location, color and content"""
        self._point_location_on_chart = pos
        self._text = text
        self._color = color
        self._compute_geometry()

    def boundingRect(self) -> QRectF:
        # Inform QT about the size we need
        return self._bouding_rect

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
        color_transparent = QColor(self._color)
        color_transparent.setAlphaF(0.7)
        painter.setBrush(color_transparent)   # Fill color
        painter.setPen(self._color)     # Border color
        painter.drawRoundedRect(self._callout_rect, 5, 5)
        anchor = QPointF(self.mapFromParent(self._point_location_on_chart))
        painter.setPen(self._text_color)     # Border color
        painter.drawEllipse(anchor, self._marker_radius, self._marker_radius)
        painter.setPen(self._text_color)
        painter.drawText(self._text_rect, self._text)


@dataclass
class ChartCursorMovedData:
    xval: float
    series: List[ScrutinyLineSeries]


class ScrutinyChartView(QChartView):
    """A QChartView extended with some features specific to the Scrutiny GUI"""

    DEFAULT_WHEEL_ZOOM_FACTOR_PER_120DEG = 0.9
    """Zooming on wheel step (common mouses) will reduces the axes range to 90% of their previous value"""
    MIN_RUBBERBAND_SIZE_PX = 5
    """The minimum size the rubberband to emit a zoom event. Prevent accidental zooms"""

    @dataclass
    class SeriesPointPair:
        series: ScrutinyLineSeries
        point: QPointF

    @dataclass
    class PointColorPair:
        point: QPointF
        color: QColor

    class ChartCursor:
        """A vertical line that the user can drag to inspect the graph data of all series at once"""
        MOVE_MARGIN = 4

        _enabled: bool
        """Enable flag"""
        _chartview: "ScrutinyChartView"
        """A reference to the owning Chartview"""
        _x: Optional[float]
        """The graphical X position. Computed from graph X value"""
        _xval: float
        """The graph x value pointed by the cursor"""
        _dragging: bool
        """``True`` When the user is moving the cursor"""

        def __init__(self, chartview: "ScrutinyChartView") -> None:
            self._enabled = False
            self._chartview = chartview
            self._x = None
            self._xval = 0
            self._dragging = False

        def is_in_drag_zone(self, p: QPointF) -> bool:
            """Tells if a point (the cursor position) is in the dragging zone of the chart cursor. 
            Used to set the screen cursot to a drag arrow"""
            if not self._enabled or self._x is None:
                return False
            chart = self._chartview.chart()
            plotarea_mapped_to_chartview = chart.mapRectToParent(chart.plotArea())
            xcheck = (self._x - self.MOVE_MARGIN) < p.x() < (self._x + self.MOVE_MARGIN)
            ycheck = plotarea_mapped_to_chartview.top() < p.y() < plotarea_mapped_to_chartview.bottom()

            return xcheck and ycheck

        def enable(self) -> None:
            self._enabled = True

        def disable(self) -> None:
            self._enabled = False
            self._dragging = False
            self._x = None

        def is_enabled(self) -> bool:
            return self._enabled

        def set_xval(self, xval: float) -> None:
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
                self._x = self._chartview.chart().xval_to_xpos(self._xval)
            else:
                self._x = None

    class InteractionMode(enum.Enum):
        SELECT_ZOOM = enum.auto()
        """Select/zoom, the user can draw a zoombox (rubberband) with his mouse to zoom the graph """
        DRAG = enum.auto()
        """Drag mode, the user can move the graph with its mouse in X/Y direction (cursor is a hand)"""

    class ZoomType(enum.Enum):
        ZOOM_X = enum.auto()
        ZOOM_Y = enum.auto()
        ZOOM_XY = enum.auto()

    class _Signals(QObject):
        context_menu_event = Signal(QContextMenuEvent)
        """When the user right click the chartview"""
        zoombox_selected = Signal(QRectF)
        """When the zoom changes (through a wheel event or a rubber band)"""
        paint_finished = Signal()
        """When the chartview has finished repainting. USed for throttling the update rate"""
        key_pressed = Signal(QKeyEvent)
        """Forwarding the keypress event"""
        resized = Signal(QResizeEvent)
        """Emitted when the chartview is resized"""
        chart_cursor_moved = Signal(ChartCursorMovedData)
        """Emitted when the chart cursor is moved and snapped to new series"""
        graph_dragged = Signal(int, int)
        """Emitted when the user drag the graph with the drag tool"""

    _rubber_band: QRubberBand
    """The rubber band (zoom box) dragged by the user"""
    _rubberband_origin: QPointF
    """Wher ethe user clicked to start to draw a rubber band"""
    _rubberband_end: QPointF
    """Where the user stopped dragging the rubber band"""
    _rubberband_valid: bool
    """Tells if the origin/end values of the rubberband can be used to display it"""
    _interaction_mode: InteractionMode
    """How the chartiew behave under the user click action"""
    _zoom_type: ZoomType
    """Type of zoomn: X, Y, XY"""
    _wheel_zoom_factor_per_120deg: float
    """Zoom ratio for a standrd mouse wheel step"""
    _zoom_allowed: bool
    """Tells if the user is allowed to zoom"""
    _drag_allowed: bool
    """Tells if the user is allowed to drag the graph"""
    _is_dragging: bool
    """Tells if the user is presently dragging the graph"""
    _chart_cursor: ChartCursor
    """The vertical value cursor (red line)"""
    _signal_tree: Optional[GraphSignalTree]
    """An optional Singal tree (TreeView that displays the curves color/name/values) tied to the chart cursor"""
    _series_to_signal_tree_value_item: Dict[int, QStandardItem]
    """A map that let us find the where to write a Y-value when moving the cursor using the QValueSeries as the key"""
    _cursor_markers_vals: List[SeriesPointPair]
    """When the cursor is positionned, contains all the value points of each series"""
    _last_mouse_pos: QPoint
    """Last mouse position recorded onmousemove event in order to compute drag delta"""
    _chart_cursor_broadcast_xval_func: Optional[Callable[[float, bool], None]]
    """The function to call to display the cursor x-value into the app"""
    _text_color: QColor
    """Text color given by the loaded theme"""

    @tools.copy_type(QChartView.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._signals = self._Signals()
        self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._rubberband_origin = QPointF()
        self._rubberband_end = QPointF()
        self._rubberband_valid = False
        self._interaction_mode = self.InteractionMode.SELECT_ZOOM
        self._zoom_type = self.ZoomType.ZOOM_XY
        self._wheel_zoom_factor_per_120deg = self.DEFAULT_WHEEL_ZOOM_FACTOR_PER_120DEG
        self._zoom_allowed = False
        self._drag_allowed = False
        self._is_dragging = False
        self._chart_cursor = self.ChartCursor(self)
        self._signal_tree = None
        self._series_to_signal_tree_value_item = {}
        self._cursor_markers_vals = []
        self._last_mouse_pos = QPoint()
        self._chart_cursor_broadcast_xval_func = None
        self._text_color = scrutiny_get_theme().palette().text().color()
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.update()
        self._signals.resized.emit(event)

    def setChart(self, chart: QChart) -> None:
        assert isinstance(chart, ScrutinyChart)
        super().setChart(chart)
        self._signals.graph_dragged.connect(chart.apply_drag)

    def chart(self) -> ScrutinyChart:
        return cast(ScrutinyChart, super().chart())

    def allow_zoom(self, val: bool) -> None:
        """Allow/disallow zooming of the chart"""
        self._zoom_allowed = val

    def allow_drag(self, val: bool) -> None:
        """Allow/disallow dragging the chart"""
        self._drag_allowed = val

    def set_zoom_type(self, zoom_type: ZoomType) -> None:
        """Sets the zoom type of the wheel events and rubber band if interaction mode == ZOOM"""
        self._zoom_type = zoom_type

    def get_zoom_type(self) -> ZoomType:
        """Return the actual zoom type (X,Y,XY)"""
        return self._zoom_type

    def set_interaction_mode(self, interaction_mode: InteractionMode) -> None:
        """Set the chartview user interaction mode. Being select/zoom or drag"""
        self._interaction_mode = interaction_mode
        if interaction_mode != self.InteractionMode.DRAG:
            self._is_dragging = False

    def get_interaction_mode(self) -> InteractionMode:
        """Return the actual user graph interaciton mode"""
        return self._interaction_mode

    def cursor_enabled(self) -> bool:
        """Tells if the chart cursor is enabled"""
        return self._chart_cursor.is_enabled()

    def enable_cursor(self) -> None:
        """Enable the chart cursor (red vertical line) to inspect the data"""
        xaxis = self.chart().axisX()
        assert xaxis is not None
        range = xaxis.max() - xaxis.min()
        self._chart_cursor.enable()
        self._chart_cursor.set_xval(xaxis.min() + range / 2)

        self._invalidate_forground()
        self.update()

        # Here we build a lookup between series and the signal tree element that this series refer to
        # Will be used for mapping quickly a value referenced by the chart cursor to a textbox
        self._series_to_signal_tree_value_item.clear()
        if self._signal_tree is not None:
            for series, value_item in self._signal_tree.get_value_item_by_attached_series():
                self._series_to_signal_tree_value_item[id(series)] = value_item

        # The cursor is set at a value that is not snapped to a real point (range/2).
        # Don't show text value to avoid giving false information. Values will be updated on first drag
        self._clear_signal_tree_values()
        self._cursor_markers_vals.clear()

    def disable_cursor(self) -> None:
        """Disable the chart cursor (red vertical line) to inspect the data"""
        self._chart_cursor.disable()
        self._invalidate_forground()
        self.update()
        self._clear_signal_tree_values()
        self._cursor_markers_vals.clear()

    @property
    def signals(self) -> _Signals:
        return self._signals

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Let the integrator decide what goes inside that menu"""
        self._signals.context_menu_event.emit(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        """We inform the outside world that repainting is finished. 
        We can use this to disable chart updates while repaint is in progress and reenable with the signal below.
        That's a way to throttle the update rate based on CPU usage"""
        super().paintEvent(event)
        self._signals.paint_finished.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._signals.key_pressed.emit(event)
        return super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
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
            new_relative_range = self._wheel_zoom_factor_per_120deg ** (angle / 120)
            relative_event = QPointF(
                event_pos_mapped_to_plotarea.x() / plotarea.width(),
                event_pos_mapped_to_plotarea.y() / plotarea.height()
            )

            range_diff = new_relative_range - 1  # new_range - old_range
            left_diff = relative_event.x() * range_diff
            top_diff = relative_event.y() * range_diff

            x1 = -left_diff
            x2 = x1 + new_relative_range
            y1 = -top_diff
            y2 = y1 + new_relative_range

            if self._zoom_type == self.ZoomType.ZOOM_X:
                new_rect = QRectF(QPointF(x1, 0), QPointF(x2, 1)).normalized()
            elif self._zoom_type == self.ZoomType.ZOOM_Y:
                new_rect = QRectF(QPointF(0, y1), QPointF(1, y2)).normalized()
            elif self._zoom_type == self.ZoomType.ZOOM_XY:
                new_rect = QRectF(QPointF(x1, y1), QPointF(x2, y2)).normalized()
            else:
                raise NotImplementedError("Unsupported zoom type")

            self._signals.zoombox_selected.emit(new_rect)
            self._invalidate_forground()
        super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._chart_cursor.is_in_drag_zone(event.pos().toPointF()):
            event.accept()
            self._chart_cursor.start_drag()
        elif self._interaction_mode == self.InteractionMode.SELECT_ZOOM and self._zoom_allowed:
            # In zoom mode, we initialize a rubber band
            event.accept()
            plotarea = self.chart().plotArea()
            plotarea_mapped_to_chartview = self.chart().mapRectToParent(plotarea)
            event_saturated = QPointF(  # We saturate to the limits of the plot area so the rubber band is inside
                min(max(event.pos().x(), plotarea_mapped_to_chartview.left()), plotarea_mapped_to_chartview.right()),
                min(max(event.pos().y(), plotarea_mapped_to_chartview.top()), plotarea_mapped_to_chartview.bottom())
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
        elif self._interaction_mode == self.InteractionMode.DRAG and self._drag_allowed:
            if self._is_in_plotarea(event.pos()):
                event.accept()
                self._is_dragging = True
                self.setCursor(Qt.CursorShape.ClosedHandCursor)

        self._last_mouse_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        mouse_cursor = Qt.CursorShape.ArrowCursor
        chart = self.chart()
        if self._chart_cursor.is_dragging():    # The user is dragging the chart cursor (red vertical line)
            event.accept()
            mouse_cursor = Qt.CursorShape.SizeHorCursor
            eventpos_mapped_to_chart = chart.mapFromParent(event.pos())
            xval = chart.xpos_to_xval(eventpos_mapped_to_chart.x(), clip_if_outside=True)
            self._cursor_markers_vals.clear()
            if xval is not None:
                snap_xval, point_series_pairs = self._get_closest_x_to_snap_to(xval)
                if snap_xval is not None:

                    self._chart_cursor.set_xval(snap_xval)
                    self._cursor_markers_vals = point_series_pairs

            self._invalidate_forground()
            self.update()

        elif self._chart_cursor.is_in_drag_zone(event.pos().toPointF()):
            mouse_cursor = Qt.CursorShape.SizeHorCursor
        elif self._interaction_mode == self.InteractionMode.DRAG and self._drag_allowed:
            if self._is_dragging:
                mouse_cursor = Qt.CursorShape.ClosedHandCursor
            elif self._is_in_plotarea(event.pos()):
                mouse_cursor = Qt.CursorShape.OpenHandCursor
        else:
            pass

        self.viewport().setCursor(mouse_cursor)

        if self._interaction_mode == self.InteractionMode.SELECT_ZOOM and self._zoom_allowed:
            # In zoom mode, we resize the rubber band
            event.accept()
            if self._rubber_band.isVisible():   # There's a rubber band active (MousePress happened before)
                plotarea = self.chart().plotArea()
                plotarea_mapped_to_chartview = self.chart().mapRectToParent(plotarea)
                event_saturated = QPointF(  # We saturate to the limits of the plot area so the rubberband stays inside
                    min(max(event.pos().x(), plotarea_mapped_to_chartview.left()), plotarea_mapped_to_chartview.right()),
                    min(max(event.pos().y(), plotarea_mapped_to_chartview.top()), plotarea_mapped_to_chartview.bottom())
                )
                event_mapped_to_chart = self.chart().mapFromParent(event_saturated)
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
        # In drag mode, we simply emit the delta drag and let the chart adjust its axes
        elif self._interaction_mode == self.InteractionMode.DRAG and self._drag_allowed:
            if self._is_dragging:
                delta = event.pos() - self._last_mouse_pos
                self._signals.graph_dragged.emit(delta.x(), delta.y())
                self._invalidate_forground()
                self.update()

        self._last_mouse_pos = event.pos()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """When the mouse is released on the chartview"""

        require_foreground_redraw = False
        if self._chart_cursor.is_dragging():
            self._chart_cursor.stop_drag()
            require_foreground_redraw = True

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
                    self._invalidate_forground()
        elif self._interaction_mode == self.InteractionMode.DRAG and self._drag_allowed:
            pass    # Nothing to do. _is_dragging is always set to False

        self._is_dragging = False
        self._rubber_band.hide()
        self._rubberband_valid = False
        self._last_mouse_pos = event.pos()

        if require_foreground_redraw:
            self._invalidate_forground()
            self.update()

        super().mouseReleaseEvent(event)

    def drawForeground(self, painter: QPainter, rect: Union[QRectF, QRect]) -> None:
        """Draw the forground of the chartview. We use it to draw a vertical cursor overlay"""
        super().drawForeground(painter, rect)

        MARKER_RADIUS = scrutiny_get_theme_prop(ScrutinyThemeProperties.CHART_CURSOR_MARKER_RADIUS)
        CHART_CURSOR_COLOR = scrutiny_get_theme_prop(ScrutinyThemeProperties.CHART_CURSOR_COLOR)

        chart = self.chart()
        plotarea_mapped_to_chartview = chart.mapRectToParent(chart.plotArea())
        xaxis = self.chart().axisX()
        if self._chart_cursor.is_enabled() and xaxis is not None:
            cursor_xpos_mapped_to_chart = chart.xval_to_xpos(self._chart_cursor.xval())
            if cursor_xpos_mapped_to_chart:
                cursor_xpos = chart.mapToParent(cursor_xpos_mapped_to_chart, 0).x()  # Map it to this chartview
                y1 = plotarea_mapped_to_chartview.y()
                y2 = plotarea_mapped_to_chartview.y() + plotarea_mapped_to_chartview.height()
                painter.setPen(self._text_color)
                painter.setBrush(self._text_color)
                painter.drawPolygon([QPointF(cursor_xpos, y1), QPointF(cursor_xpos - 3, y1 - 4), QPointF(cursor_xpos + 3, y1 - 4)])
                painter.setPen(CHART_CURSOR_COLOR)
                painter.drawLine(QPointF(cursor_xpos, y1), QPointF(cursor_xpos, y2))

            plotarea_width = chart.plotArea().width()
            cursor_val_width = (xaxis.max() - xaxis.min()) / plotarea_width
            cursor_xval = self._chart_cursor.xval()
            painter.setPen(self._text_color)

            for pair in self._cursor_markers_vals:
                snap = abs(pair.point.x() - cursor_xval) <= cursor_val_width
                if snap:
                    val = QPointF(cursor_xval, pair.point.y())
                    pos = chart.val_to_pos(val, chart.axisY(pair.series), clip_if_outside=False)
                    if pos is not None:
                        painter.setBrush(pair.series.color())
                        painter.drawEllipse(chart.mapToParent(pos), MARKER_RADIUS, MARKER_RADIUS)

    def _invalidate_forground(self) -> None:
        # self.invalidateScene(self.geometry(), QGraphicsScene.SceneLayer.ForegroundLayer)   # Does not work??
        self.chart().update(QRect(0, 0, 0, 0))   # Best workaround I found...

    def _is_in_plotarea(self, p: Union[QPointF, QPoint]) -> bool:
        chart = self.chart()
        return chart.mapToParent(chart.plotArea()).containsPoint(p, Qt.FillRule.OddEvenFill)

    def _get_closest_x_to_snap_to(self, xval: float) -> Tuple[Optional[float], List[SeriesPointPair]]:
        """Scan every visible series to find the closest X value so we can put the chart cursor on from a given X val."""
        chart = self.chart()
        xaxis = chart.axisX()
        if xaxis is None:
            return (None, [])
        candidates: List[ScrutinyChartView.SeriesPointPair] = []
        for series in chart.series():
            if series.isVisible():
                point = series.search_closest_monotonic(xval, min_x=xaxis.min(), max_x=xaxis.max())
                if point is not None:
                    candidates.append(self.SeriesPointPair(series, point))

        if len(candidates) == 0:
            return (None, [])

        candidates.sort(key=lambda x: abs(x.point.x() - xval))  # Sort by distance
        closest_xval = candidates[0].point.x()  # First one is the closest, we snap on it
        return closest_xval, candidates

    def _update_signal_tree_with_cursor_values(self) -> None:
        """Update the textual Y value that appears next to a signal in a treeview dedicated to show the graph series."""
        if self._signal_tree is None:
            return

        self._clear_signal_tree_values()

        for pair in self._cursor_markers_vals:
            try:
                value_item = self._series_to_signal_tree_value_item[id(pair.series)]
            except KeyError as e:
                raise

            value_item.setText(str(pair.point.y()))

    def _clear_signal_tree_values(self) -> None:
        """Clear the value box in the signal tree"""
        if self._signal_tree is not None:
            for value_item in self._signal_tree.get_all_value_items():
                value_item.setText("")

    def configure_chart_cursor(self, signal_tree: GraphSignalTree, xval_func: Optional[Callable[[float, bool], None]]) -> None:
        if not signal_tree.has_value_col():
            raise RuntimeError("Cannot tie the chart cursor to a signal tree with no value column")
        self._signal_tree = signal_tree
        self._chart_cursor_broadcast_xval_func = xval_func

    @tools.copy_type(QChartView.update)
    def update(self, *args: Any, **kwargs: Any) -> None:
        self._chart_cursor.update()
        self._update_signal_tree_with_cursor_values()
        if self._chart_cursor_broadcast_xval_func is not None:
            self._chart_cursor_broadcast_xval_func(self._chart_cursor.xval(), self._chart_cursor.is_enabled())
        super().update(*args, **kwargs)


class ScrutinyChartToolBar(QGraphicsItem):
    """A toolbar designed to go at the top of a Scrutiny Chart. Can be tied to a Chartview and enable control of it"""

    TOOLBAR_HEIGHT = 24
    ICON_SIZE = 20  # Square icons
    PADDING_Y = int((TOOLBAR_HEIGHT - ICON_SIZE) / 2)

    class ToolbarButton(QGraphicsItem):
        """Represent a button that goes in the toolbar"""
        class _Signals(QObject):
            clicked = Signal()
            """Emitted on mouse release if the mouse pressed happened on the button"""

        _icon_id: assets.Icons
        """The icon of the button, identified by the it's ID in the icon repo"""
        _icon_size: QSizeF
        """Size of the icon"""
        _pixmap: QPixmap
        """The button icon as a pixmap resized for the button"""
        _bounding_rect: QRectF
        """The bounding box for the graphic scene"""
        _is_hovered: bool
        """True when the mouse is above this button"""
        _is_pressed: bool
        """True when the mouse left button is pressed on this button"""
        _is_selected: bool
        """True when the button is set as 'selected' programmatically"""

        PADDING_X = 5

        def __init__(self, toolbar: "ScrutinyChartToolBar", icon: assets.Icons) -> None:
            super().__init__(toolbar)
            self._signals = self._Signals()
            self._is_hovered = False
            self._is_pressed = False
            self._is_selected = False
            self.setAcceptHoverEvents(True)  # Required for hoverEnter and hoverLeaves
            self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)     # No need for right button
            self.set_icon(icon)

        @property
        def signals(self) -> _Signals:
            return self._signals

        def set_icon(self, icon: assets.Icons, size: Optional[float] = None) -> None:
            """Changes the icon of the button"""
            self._icon_id = icon
            if size is None:
                self.set_icon_size(ScrutinyChartToolBar.ICON_SIZE)
            else:
                self.set_icon_size(size)
            self.update()

        def set_icon_size(self, icon_size: float) -> None:
            """Resize the icon """
            self.prepareGeometryChange()
            self._icon_size = QSizeF(icon_size, icon_size)
            self._pixmap = scrutiny_get_theme().load_medium_icon_as_pixmap(self._icon_id).scaled(
                self._icon_size.toSize(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            # Add internal padding. 2x for left/right and top/bottom
            size_padded = self._icon_size + QSizeF(2 * self.PADDING_X, 2 * ScrutinyChartToolBar.PADDING_Y)
            self._bounding_rect = QRectF(QPointF(0, 0), size_padded)
            self.update()

        def boundingRect(self) -> QRectF:
            """The zone where we draw"""
            return self._bounding_rect

        def select(self) -> None:
            """Set the button as 'selected' which change the color"""
            self.set_selected(True)

        def deselect(self) -> None:
            """Set the button as 'deselected' which change the color"""
            self.set_selected(False)

        def set_selected(self, val: bool) -> None:
            """Set the button as 'selected' or 'deselected' which change the color"""
            self._is_selected = val
            self.update()

        def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
            HOVERED_COLOR = scrutiny_get_theme_prop(ScrutinyThemeProperties.CHART_TOOLBAR_HOVERED_BUTTON_COLOR)
            HOVERED_SELECTED_BORDER_COLOR = scrutiny_get_theme_prop(ScrutinyThemeProperties.CHART_TOOLBAR_HOVERED_SELECTED_BORDER_COLOR)
            SELECTED_COLOR = scrutiny_get_theme_prop(ScrutinyThemeProperties.CHART_TOOLBAR_SELECTED_COLOR)
            PRESSED_COLOR = scrutiny_get_theme_prop(ScrutinyThemeProperties.CHART_TOOLBAR_PRESSED_COLOR)
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

            painter.drawPixmap(QPoint(self.PADDING_X, ScrutinyChartToolBar.PADDING_Y), self._pixmap)

        def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
            # Used to generate click event
            event.accept()
            self._is_pressed = True  # Will make the color different
            self.update()

        def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
            event.accept()
            if self._is_pressed:
                self._signals.clicked.emit()
            self._is_pressed = False
            self.update()

        def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:
            event.accept()
            self._is_hovered = True
            self.update()

        def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
            event.accept()
            self._is_hovered = False
            self._is_pressed = False
            self.update()

    class ToolbarSpacer(QGraphicsItem):
        _width: int

        def __init__(self, toolbar: "ScrutinyChartToolBar", width: int) -> None:
            super().__init__(toolbar)
            self._width = width

        def boundingRect(self) -> QRectF:
            return QRectF(QPoint(0, 0), QPoint(self._width, ScrutinyChartToolBar.TOOLBAR_HEIGHT))

        def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
            pass    # Nothing to do. Need to exist

    class ToolbarDivision(QGraphicsItem):
        LINE_WIDTH = 1
        LINE_COLOR = QColor(226, 226, 226)
        PADDING_X = 6
        _line_y1: int
        _line_y2: int

        def __init__(self, toolbar: "ScrutinyChartToolBar") -> None:
            super().__init__(toolbar)
            self._line_y1 = ScrutinyChartToolBar.PADDING_Y
            self._line_y2 = ScrutinyChartToolBar.TOOLBAR_HEIGHT - ScrutinyChartToolBar.PADDING_Y

        def boundingRect(self) -> QRectF:
            return QRectF(QPoint(0, self._line_y1), QPoint(2 * self.PADDING_X, self._line_y2))

        def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
            painter.setPen(self.LINE_COLOR)
            p1 = QPoint(self.PADDING_X, self._line_y1)
            p2 = QPoint(self.PADDING_X, self._line_y2)
            painter.drawLine(p1, p2)

    BUTTON_SPACING = 0
    """ Spaces between each buttons"""
    _chart: ScrutinyChart
    """The chart on which we draw the toolbar"""
    _chartview: ScrutinyChartView
    """The chartview that the toolbar controls"""
    _btn_mode_select_zoom: ToolbarButton

    _btn_mode_drag: ToolbarButton

    _btn_enable_cursor: ToolbarButton
    """ Enable/disable the graph cursor"""
    _btn_zoom_xy: ToolbarButton
    """ Zoom XY button"""
    _btn_zoom_x: ToolbarButton
    """ Zoom X button"""
    _btn_zoom_y: ToolbarButton
    """ Zoom Y button"""
    _bounding_rect: QRectF
    """The zone where we draw"""
    _buttons: List[QGraphicsItem]
    """All the buttons in order from left to right"""

    def __init__(self, chartview: ScrutinyChartView) -> None:
        validation.assert_type(chartview, 'chartview', ScrutinyChartView)
        super().__init__(chartview.chart())
        self._chart = chartview.chart()
        self._chartview = chartview

        self._btn_enable_cursor = self.ToolbarButton(self, assets.Icons.GraphCursor)
        self._btn_mode_select_zoom = self.ToolbarButton(self, assets.Icons.CursorArrow)
        self._btn_mode_drag = self.ToolbarButton(self, assets.Icons.CursorHandDrag)
        self._btn_zoom_xy = self.ToolbarButton(self, assets.Icons.ZoomXY)
        self._btn_zoom_x = self.ToolbarButton(self, assets.Icons.ZoomX)
        self._btn_zoom_y = self.ToolbarButton(self, assets.Icons.ZoomY)
        self._bounding_rect = QRectF()

        self._buttons = [
            self._btn_enable_cursor,
            self.ToolbarDivision(self),
            self._btn_mode_select_zoom,
            self._btn_mode_drag,
            self.ToolbarDivision(self),
            self._btn_zoom_xy,
            self._btn_zoom_x,
            self._btn_zoom_y
        ]
        self._chart.geometryChanged.connect(self._update_geometry)

        self._btn_enable_cursor.signals.clicked.connect(self._slot_btn_enable_disable_cursor)
        self._btn_zoom_xy.signals.clicked.connect(self._slot_btn_zoom_xy)
        self._btn_zoom_x.signals.clicked.connect(self._slot_btn_zoom_x)
        self._btn_zoom_y.signals.clicked.connect(self._slot_btn_zoom_y)
        self._btn_mode_select_zoom.signals.clicked.connect(self._slot_btn_mode_select_zoom)
        self._btn_mode_drag.signals.clicked.connect(self._slot_btn_mode_drag)

        self.update_buttons_from_state()

    def disable_chart_cursor(self) -> None:
        self._chartview.disable_cursor()
        self.update_buttons_from_state()

    def enable_chart_cursor(self) -> None:
        self._chartview.enable_cursor()
        self.update_buttons_from_state()

    def toggle_chart_cursor(self) -> None:
        if self._chartview.cursor_enabled():
            self.disable_chart_cursor()
        else:
            self.enable_chart_cursor()

    def _slot_btn_enable_disable_cursor(self) -> None:
        self.toggle_chart_cursor()

    def _slot_btn_zoom_x(self) -> None:
        """Called when Zoom X button is clicked"""
        # Change the chartview behavior
        self._chartview.set_zoom_type(ScrutinyChartView.ZoomType.ZOOM_X)
        self.update_buttons_from_state()

    def _slot_btn_zoom_y(self) -> None:
        # Change the chartview behavior
        self._chartview.set_zoom_type(ScrutinyChartView.ZoomType.ZOOM_Y)
        self.update_buttons_from_state()

    def _slot_btn_zoom_xy(self) -> None:
        # Change the chartview behavior
        self._chartview.set_zoom_type(ScrutinyChartView.ZoomType.ZOOM_XY)
        self.update_buttons_from_state()

    def _slot_btn_mode_select_zoom(self) -> None:
        self._chartview.set_interaction_mode(ScrutinyChartView.InteractionMode.SELECT_ZOOM)
        self.update_buttons_from_state()

    def _slot_btn_mode_drag(self) -> None:
        self._chartview.set_interaction_mode(ScrutinyChartView.InteractionMode.DRAG)
        self.update_buttons_from_state()

    def update_buttons_from_state(self) -> None:
        self._btn_enable_cursor.set_selected(self._chartview.cursor_enabled())

        self._btn_mode_select_zoom.set_selected(self._chartview.get_interaction_mode() == ScrutinyChartView.InteractionMode.SELECT_ZOOM)
        self._btn_mode_drag.set_selected(self._chartview.get_interaction_mode() == ScrutinyChartView.InteractionMode.DRAG)

        self._btn_zoom_xy.set_selected(self._chartview.get_zoom_type() == ScrutinyChartView.ZoomType.ZOOM_XY)
        self._btn_zoom_x.set_selected(self._chartview.get_zoom_type() == ScrutinyChartView.ZoomType.ZOOM_X)
        self._btn_zoom_y.set_selected(self._chartview.get_zoom_type() == ScrutinyChartView.ZoomType.ZOOM_Y)

    def _update_geometry(self) -> None:
        """Recompute all the internal drawing dimensions"""
        self.prepareGeometryChange()
        chart_size = self._chart.size()

        # We will scan all the buttons from left to right and decide how much space we need
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
        origin = QPointF(chart_size.width() / 2 - required_width / 2, 0)
        self.setPos(origin)
        self._bounding_rect = QRectF(QPointF(0, 0), size)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
        pass    # Nothing to do. Need to exist

    def boundingRect(self) -> QRectF:
        return self._bounding_rect
