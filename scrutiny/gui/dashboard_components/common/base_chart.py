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
from bisect import bisect_left

from PySide6.QtCharts import QLineSeries, QValueAxis, QChart, QChartView
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget, QRubberBand, QGraphicsSceneMouseEvent, QGraphicsSceneHoverEvent
from PySide6.QtGui import  (QFont, QPainter, QFontMetrics, QColor, QContextMenuEvent, QPaintEvent, QMouseEvent, QWheelEvent, QPixmap, QKeyEvent)
from PySide6.QtCore import  QPointF, QRect, QRectF, Qt, QObject, Signal, QSize, QPoint, QSizeF

from scrutiny import tools
from scrutiny.gui import assets
from scrutiny.gui.themes import get_theme_prop, ScrutinyThemeProperties
from scrutiny.gui.tools.min_max import MinMax
from scrutiny.core import validation

from typing import Any, Optional, Any, List


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
    
    def apply_zoombox_x(self, zoombox:QRectF, margin_ratio:float=0) -> None:
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
        new_low = max(zoombox.left() * range + self.min(), minval )
        new_high = min(zoombox.right() * range + self.min(), maxval )
        if new_low==new_high:
            self.setRange(new_low-1, new_high+1)
        else:
            self.setRange( new_low, new_high )
    
    def apply_zoombox_y(self, zoombox:QRectF, margin_ratio:float=0) -> None:
        """
        Apply a zoom rectangle generated by a ScrutinyChartview. It's a rectangle where the top/bottom bounds represent the 
        Y limits of the new zoom. Value sare normalized to p.u.
        A rectangle with y1=0.2, y2=0.8 will zoom in, remove 20% of the graph on each side.
        A rectangle with y1=-0.1, y2=1.3 will zoom out and offset a little to the right. 10% more on the left, 30% more on the right.
        """
        range = self.max() - self.min()
        minval = self.minval_with_margin(margin_ratio)
        maxval = self.maxval_with_margin(margin_ratio)
        if minval is None or maxval is None:
            return
        new_low = max((1-zoombox.bottom()) * range + self.min(), minval)
        new_high = min((1-zoombox.top()) * range + self.min(), maxval)
        if new_low==new_high:
            self.setRange(new_low-1, new_high+1)
        else:
            self.setRange( new_low, new_high )

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

class ScrutinyChartView(QChartView):

    DEFAULT_WHEEL_ZOOM_FACTOR_PER_120DEG = 0.9
    MIN_ZOOMBOX_SIZE_PX = 5

    class InteractionMode(enum.Enum):
        SELECT=enum.auto()
        DRAG=enum.auto()
        ZOOM=enum.auto()

    class ZoomType(enum.Enum):
        ZOOM_X=enum.auto()
        ZOOM_Y=enum.auto()
        ZOOM_XY=enum.auto()

    class _Signals(QObject):
        context_menu_event = Signal(QContextMenuEvent)
        zoombox_selected = Signal(QRectF)
        paint_finished = Signal()
        key_pressed = Signal(QKeyEvent)

    _rubber_band:QRubberBand
    _rubberband_origin:QPointF
    _rubberband_end:QPointF
    _rubberband_valid:bool
    _interaction_mode:InteractionMode
    _zoom_type:ZoomType
    _wheel_zoom_factor_per_120deg:float
    _zoom_allowed:bool

    @tools.copy_type(QChartView.__init__)
    def __init__(self, *args:Any, **kwargs:Any) -> None:
        super().__init__(*args, **kwargs)
        self._signals = self._Signals()
        self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._rubberband_origin = QPointF()
        self._rubberband_end = QPointF()
        self._rubberband_valid= False
        self._interaction_mode = self.InteractionMode.SELECT
        self._zoom_type = self.ZoomType.ZOOM_XY
        self._wheel_zoom_factor_per_120deg = self.DEFAULT_WHEEL_ZOOM_FACTOR_PER_120DEG
        self._zoom_allowed = False

    def allow_zoom(self, val:bool) -> None:
        self._zoom_allowed = val

    def set_zoom_type(self, zoom_type:ZoomType) -> None:
        self._zoom_type = zoom_type
    
    def set_interaction_mode(self, interaction_mode:InteractionMode) -> None:
        self._interaction_mode = interaction_mode

    def enable_cursor(self) -> None:
        pass

    def disable_cursor(self) -> None:
        pass
    
    @property
    def signals(self) -> _Signals:
        return self._signals

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self._signals.context_menu_event.emit(event)

    def paintEvent(self, event:QPaintEvent) -> None:
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
        if self._interaction_mode == self.InteractionMode.ZOOM and self._zoom_allowed:
            event.accept()
            plotarea = self.chart().plotArea()
            plotarea_mapped_to_chartview =self.chart().mapRectToParent(plotarea)
            event_saturated = QPointF( 
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
        if self._interaction_mode == self.InteractionMode.ZOOM and self._zoom_allowed:
            event.accept()
            if self._rubber_band.isVisible():
                plotarea = self.chart().plotArea()
                event_saturated = QPointF( 
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
        if self._interaction_mode == self.InteractionMode.ZOOM and self._zoom_allowed:
            event.accept()
            if self._rubberband_valid:
                plotarea_mapped_to_chartview = self.chart().mapRectToParent(self.chart().plotArea())
                diffabs_x = abs(self._rubberband_end.x() - self._rubberband_origin.x())
                diffabs_y = abs(self._rubberband_end.y() - self._rubberband_origin.y())
                if diffabs_x > self.MIN_ZOOMBOX_SIZE_PX and diffabs_y > self.MIN_ZOOMBOX_SIZE_PX:
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


class ScrutinyChartToolBar(QGraphicsItem):
    class ToolbarButton(QGraphicsItem):
        class _Signals(QObject):
            clicked = Signal()

        _icon_id:assets.Icons
        _icon_size:QSizeF
        _pixmap:QPixmap
        _rect:QRectF
        _is_hovered:bool
        _is_pressed:bool
        _is_selected:bool

        HOVERED_COLOR = QColor(0xE0, 0xf0, 0xFF)
        HOVERED_BORDER_COLOR = QColor(0x99, 0xD0, 0xFF)
        SELECTED_COLOR = QColor(0xC8, 0xE8, 0xFF)
        ICON_SIZE = 20
        PADDING_X = 5
        PADDING_Y = 2

        def __init__(self, toolbar:"ScrutinyChartToolBar", icon:assets.Icons) -> None:
            super().__init__(toolbar)
            self._signals = self._Signals()
            self._is_hovered = False
            self._is_pressed = False
            self._is_selected = False
            self.setAcceptHoverEvents(True)
            self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
            self.set_icon(icon)
        
        @property
        def signals(self) -> _Signals:
            return self._signals
        
        def set_icon(self, icon:assets.Icons) -> None:
            self._icon_id = icon
            self.set_icon_size(self.ICON_SIZE)
            self.update()
            
        def set_icon_size(self, icon_size:float) -> None:
            self.prepareGeometryChange()
            self._icon_size = QSizeF(icon_size,icon_size)
            self._pixmap = assets.load_large_icon_as_pixmap(self._icon_id).scaled(
                self._icon_size.toSize(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
                )
            
            size_padded = self._icon_size + QSizeF(2*self.PADDING_X, 2*self.PADDING_Y)
            self._rect = QRectF(QPointF(0,0), size_padded)
            self.update()
        
        def boundingRect(self) -> QRectF:
            return self._rect 
        
        def select(self) -> None:
            self._is_selected = True
            self.update()
        
        def deselect(self) -> None:
            self._is_selected = False
            self.update()

        def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget]=None) -> None:
            if self._is_selected or self._is_pressed:
                painter.setPen(self.SELECTED_COLOR)
                painter.setBrush(self.SELECTED_COLOR)
                painter.drawRect(self._rect)
            elif self._is_hovered:
                painter.setPen(self.HOVERED_BORDER_COLOR)
                painter.setBrush(self.HOVERED_COLOR)
                painter.drawRect(self._rect)
            
            painter.drawPixmap(QPoint(self.PADDING_X,self.PADDING_Y), self._pixmap)

        
        def mousePressEvent(self, event:QGraphicsSceneMouseEvent) -> None:
            event.accept()
            self._is_pressed = True
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
    _chart:ScrutinyChart
    _chartview:Optional[ScrutinyChartView]
    _btn_zoom_value_cursor:ToolbarButton

    _btn_zoom_xy:ToolbarButton
    _btn_zoom_x:ToolbarButton
    _btn_zoom_y:ToolbarButton
    _rect : QRectF
    _buttons : List[ToolbarButton]

    def __init__(self, chart:ScrutinyChart) -> None:
        validation.assert_type(chart, 'chart', ScrutinyChart)
        super().__init__(chart)
        self._chart = chart
        self._chartview = None
        #self._btn_zoom_value_cursor = self.ToolbarButton(self, assets.Icons.GraphCursor)
        self._btn_zoom_xy = self.ToolbarButton(self, assets.Icons.ZoomXY)
        self._btn_zoom_x = self.ToolbarButton(self, assets.Icons.ZoomX)
        self._btn_zoom_y = self.ToolbarButton(self, assets.Icons.ZoomY)
        self._rect = QRectF()

        self._buttons = [self._btn_zoom_xy, self._btn_zoom_x, self._btn_zoom_y]
        self._chart.geometryChanged.connect(self._update_geometry)
        
        self._btn_zoom_xy.signals.clicked.connect(self._zoom_xy)
        self._btn_zoom_x.signals.clicked.connect(self._zoom_x)
        self._btn_zoom_y.signals.clicked.connect(self._zoom_y)

        self._btn_zoom_xy.select()

    def set_chartview(self, chartview:ScrutinyChartView) -> None:
        self._chartview = chartview

    def _zoom_x(self) -> None:
        if self._chartview is None:
            return
        self._chartview.set_interaction_mode(ScrutinyChartView.InteractionMode.ZOOM)
        self._chartview.set_zoom_type(ScrutinyChartView.ZoomType.ZOOM_X)
        self._btn_zoom_x.select()
        self._btn_zoom_xy.deselect()
        self._btn_zoom_y.deselect()
    
    def _zoom_y(self) -> None:
        if self._chartview is None:
            return
        self._chartview.set_interaction_mode(ScrutinyChartView.InteractionMode.ZOOM)
        self._chartview.set_zoom_type(ScrutinyChartView.ZoomType.ZOOM_Y)
        self._btn_zoom_y.select()
        self._btn_zoom_xy.deselect()
        self._btn_zoom_x.deselect()
    
    def _zoom_xy(self) -> None:
        if self._chartview is None:
            return
        self._chartview.set_interaction_mode(ScrutinyChartView.InteractionMode.ZOOM)
        self._chartview.set_zoom_type(ScrutinyChartView.ZoomType.ZOOM_XY)
        self._btn_zoom_xy.select()
        self._btn_zoom_x.deselect()
        self._btn_zoom_y.deselect()

    def _update_geometry(self) -> None:
        self.prepareGeometryChange()
        chart_size = self._chart.size()
        
        width_cursor = float(0)
        required_height = float(0)
        for i in range(len(self._buttons)):
            button = self._buttons[i]
            r = button.boundingRect()
            required_height = max(required_height, r.height())
            button.setPos(width_cursor, 0)
            width_cursor += r.width()
            if i < len(self._buttons):
                width_cursor += self.BUTTON_SPACING
        required_width = width_cursor
        size = QSizeF(required_width, required_height)
        origin = QPointF(chart_size.width()/2 - required_width/2, 0)
        self.setPos(origin)
        self._rect = QRectF(QPointF(0,0), size)
    
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget]=None) -> None:
        pass


    def boundingRect(self) -> QRectF:
        return self._rect
