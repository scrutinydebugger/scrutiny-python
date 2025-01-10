#    continuous_graph_component.py
#        A component that makes a real time graphs of the values streamed by the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from datetime import datetime
import functools
import math

from PySide6.QtGui import QPainter, QFontMetrics, QFont, QColor
from PySide6.QtWidgets import (QHBoxLayout, QSplitter, QWidget, QVBoxLayout, 
                               QPushButton, QMessageBox, QFormLayout, QSpinBox, QGraphicsItem, QStyleOptionGraphicsItem,
                               QLineEdit)
from PySide6.QtCore import Qt, QItemSelectionModel, QPointF, QTimer, QRectF, QRect

from scrutiny.gui import assets
from scrutiny.gui.tools.prompt import exception_msgbox
from scrutiny.gui.tools.invoker import InvokeQueued, InvokeInQtThread
from scrutiny.gui.tools.min_max import MinMax
from scrutiny.gui.core.definitions import WidgetState
from scrutiny.gui.core.watchable_registry import WatchableRegistryNodeNotFoundError, ValueUpdate
from scrutiny.gui.widgets.feedback_label import FeedbackLabel
from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from scrutiny.gui.dashboard_components.common.graph_signal_tree import GraphSignalTree, ChartSeriesWatchableStandardItem
from scrutiny.gui.dashboard_components.common.export_chart_csv import export_chart_csv_threaded
from scrutiny.gui.dashboard_components.common.base_chart import (
    ScrutinyLineSeries, ScrutinyValueAxisWithMinMax, ScrutinyChartCallout, ScrutinyChartView, ScrutinyChart)
from scrutiny.gui.dashboard_components.continuous_graph.decimator import GraphMonotonicNonUniformMinMaxDecimator
from scrutiny import sdk
from scrutiny import tools

from typing import Dict, Any, Union, List, Optional, cast, Set, Generator

class RealTimeScrutinyLineSeries(ScrutinyLineSeries):
    _decimator:GraphMonotonicNonUniformMinMaxDecimator
    _x_minmax:MinMax
    _y_minmax:MinMax
    _dirty:bool
    _paused:bool

    def __init__(self, *args:Any, **kwargs:Any) -> None:
        super().__init__(*args, **kwargs)
        self._decimator = GraphMonotonicNonUniformMinMaxDecimator()
        self._x_minmax = MinMax()
        self._y_minmax = MinMax()
        self._dirty = False
        self._paused = False
        
    def pause(self) -> None:
        self._paused = True

    def unpause(self) -> None:
        self._paused = False
        if self._dirty:
            self.flush_decimated()

    def is_paused(self) -> bool:
        return self._paused
        
    def set_x_resolution(self, resolution:float) -> bool:
        changed = self._decimator.set_x_resolution(resolution)
        if changed:            
            self._dirty = True
            if not self._paused:
                self.flush_decimated()
        return changed
    
    def decimation_factor(self) -> float:
        return self._decimator.decimation_factor()
    
    def count_visible_points(self) -> int:
        return len(self._decimator.get_decimated_buffer())

    def count_all_points(self) -> int:
        return len(self._decimator.get_input_buffer())

    def add_point(self, point:QPointF) -> int:
        n = self._decimator.add_point(point)    # Can have 2 points out for a single in (min/max)
        if n > 0:
            for p in self._decimator.get_decimated_buffer()[-n:]:
                self._y_minmax.update(p.y())
                self._x_minmax.update_max(p.x())
            self._dirty=True
        return n
    
    def delete_up_to_x(self, x:float) -> None:
        in_deleted, out_deleted = self._decimator.delete_data_up_to_x(x)
        if out_deleted > 0: # That affects the visible graph
            self._dirty = True
    
    def get_last_x(self) -> Optional[float]:
        buffer = self._decimator.get_input_buffer()
        if len(buffer) == 0:
            return None
        return buffer[-1].x()

    def get_first_x(self) -> Optional[float]:
        buffer = self._decimator.get_input_buffer()
        if len(buffer) == 0:
            return None
        return buffer[0].x()
    
    def get_last_decimated_x(self) -> Optional[float]:
        buffer = self._decimator.get_decimated_buffer()
        if len(buffer) == 0:
            return None
        return buffer[-1].x()

    def get_first_decimated_x(self) -> Optional[float]:
        buffer = self._decimator.get_decimated_buffer()
        if len(buffer) == 0:
            return None
        return buffer[0].x()

    def flush_decimated(self) -> None:
        if not self._paused:
            self.replace(self._decimator.get_decimated_buffer())
            self._dirty = False
    
    def flush_full_dataset(self) -> None:
        if not self._paused:
            self.replace(self._decimator.get_input_buffer())

    def is_dirty(self) -> bool:
        return self._dirty

    def stop_decimator(self) -> None:
        self._decimator.force_flush_pending()

    def recompute_minmax(self) -> None:
        self._x_minmax.clear()
        self._y_minmax.clear()

        for p in self._decimator.get_decimated_buffer(): 
            self._x_minmax.update(p.x())
            self._y_minmax.update(p.y())
        
        for p in self._decimator.get_unprocessed_input():
            self._x_minmax.update(p.x())
            self._y_minmax.update(p.y())

    def recompute_y_minmax(self) -> None:
        self._y_minmax.clear()

        for p in self._decimator.get_decimated_buffer(): 
            self._y_minmax.update(p.y())

        for p in self._decimator.get_unprocessed_input():
            self._y_minmax.update(p.y())
    
    def x_min(self) -> Optional[float]:
        return self._x_minmax.min()
    
    def x_max(self) -> Optional[float]:
        return self._x_minmax.max()
    
    def y_min(self) -> Optional[float]:
        return self._y_minmax.min()
    
    def y_max(self) -> Optional[float]:
        return self._y_minmax.max()


class GraphStatistics:

    class Overlay(QGraphicsItem):
        _stats:"GraphStatistics"
        _bounding_box:QRectF
        _text_rect:QRectF
        _font:QFont
        _text:str

        def __init__(self, parent:Optional[QGraphicsItem], stats:"GraphStatistics") -> None:
            super().__init__(parent)
            self._stats = stats
            self._bounding_box = QRectF()
            self._text_rect = QRectF()
            self._font  = QFont()
            self._text = ""
            self.setZValue(11)

        def update_content(self) -> None:
            self._make_text()
            self._compute_geometry()

        def _make_text(self) -> None:
            self._text =  "Decimation: %0.1fx\nVisible points: %d/%d" % (
                self._stats.decimation_factor,
                self._stats.visible_points,
                self._stats.total_points,
            )

        def _compute_geometry(self) -> None:
            self.prepareGeometryChange()
            metrics = QFontMetrics(self._font)
            self._text_rect = QRectF(metrics.boundingRect(QRect(0, 0, 200, 100), Qt.AlignmentFlag.AlignLeft, self._text))
            self._bounding_box = QRectF(self._text_rect.adjusted(0,0,0,0))

        def boundingRect(self) -> QRectF:
            return self._bounding_box

        def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget]=None) -> None:
            painter.setPen(QColor(0,0,0))
            painter.drawText(self._text_rect, self._text)

    visible_points:int
    total_points:int
    decimation_factor:float
    _overlay:Overlay

    def __init__(self, draw_zone:Optional[QGraphicsItem] = None) -> None:
        self._overlay = self.Overlay(draw_zone, self)
        self.clear()

    def clear(self) -> None:
        self.visible_points = 0
        self.total_points = 0
        self.decimation_factor = 1

    def show_overlay(self) -> None:
        self._overlay.show()
        self._overlay.update_content()

    def hide_overlay(self) -> None:
        self._overlay.hide()

    def update_overlay(self) -> None:
        self._overlay.update_content()

    def overlay(self) -> Overlay:
        return self._overlay


class ContinuousGraphComponent(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("graph-96x128.png")
    _NAME = "Continuous Graph"

    DEFAULT_GRAPH_MAX_WIDTH=30
    MAX_SIGNALS=32
    Y_AXIS_MARGIN = 0.02

    _chartview:ScrutinyChartView
    """The QT chartview"""
    _callout:ScrutinyChartCallout
    """A callout (popup bubble) that shows the values on hover"""
    _signal_tree:GraphSignalTree
    """The right menu with axis and signal"""
    _btn_start_stop:QPushButton
    """The start/stop button"""
    _btn_pause:QPushButton
    """The Pause button"""
    _btn_clear:QPushButton
    """The "clear" button"""
    _spinbox_graph_max_width:QSpinBox
    """Spinbox to select the X-size of the graph in the GUI"""
    _feedback_label:FeedbackLabel
    """A label to report error to the user"""
    _splitter:QSplitter
    """The splitter between the graph and the signal/axis tree"""
    _acquiring:bool
    """A flag indicating if an acquisition is running"""
    _chart_has_content:bool
    """A flag indicating if there is data in the graph being displayed"""
    _serverid2sgnal_item:Dict[str, ChartSeriesWatchableStandardItem]
    """A dictionnary mapping server_id associated with ValueUpdates broadcast by the server to their respective signal (a tree item, which has a reference to the chart series) """
    _callout_hide_timer:QTimer
    """A timer to trigger the hiding of the graph callout. Avoid fast show/hide"""
    _first_val_dt:Optional[datetime]
    """The server timestamp of the first value gotten. Used to offset the ValueUpdates timestamps to 0"""
    _autoscale_enabled:bool
    """Tells if the axis range should be adjusted based on the content"""
    _graph_maintenance_timer:QTimer
    """A timer to periodically remove data and do some non-real time computation"""
    _graph_max_width:float
    """The maximum width of the X-Axis (max-min). Used to delete expired data"""
    _y_minmax_recompute_index:int
    """A persistent index used to recompute the minmax of all the Y serie sin round robin fashion. Used this index to reduce the CPU load by doing 1 series per call"""
    _x_resolution:float
    """The actual X resolution in sec. This value is given to the series decimator"""
    _stats:GraphStatistics
    """Graph statistics displayed to the user in real time"""
    _xaxis:ScrutinyValueAxisWithMinMax
    """The single time X-Axis"""
    _yaxes:List[ScrutinyValueAxisWithMinMax]
    """All the Y-Axes defined by the user"""
    _paused:bool

    def setup(self) -> None:
        self._acquiring = False
        self._chart_has_content = False
        self._serverid2sgnal_item = {}
        self._autoscale_enabled = False
        self._xaxis = ScrutinyValueAxisWithMinMax(self)
        self._xaxis.setTitleText("Time [s]")
        self._xaxis.setTitleVisible(True)
        self._xaxis.deemphasize()   # Default state
        self._yaxes = []
        self._x_resolution = 0
        self._paused = False
        
        self._y_minmax_recompute_index=0
        self.watchable_registry.register_watcher(self.instance_name, self._val_update_callback, self._unwatch_callback)
        
        self._splitter = QSplitter(self)
        self._splitter.setOrientation(Qt.Orientation.Horizontal)
        self._splitter.setContentsMargins(0,0,0,0)
        self._splitter.setHandleWidth(5)
        
        self._chartview = ScrutinyChartView(self)
        chart = ScrutinyChart()
        chart.layout().setContentsMargins(0,0,0,0)
        chart.setAxisX(self._xaxis)
        self._chartview.setChart(chart)
        self._chartview.signals.save_csv.connect(self._save_csv_slot)
        self._callout = ScrutinyChartCallout(chart)
        self._callout_hide_timer = QTimer()
        self._callout_hide_timer.setInterval(250)
        self._callout_hide_timer.setSingleShot(True)
        self._callout_hide_timer.timeout.connect(self._callout_hide_timer_slot)
        
        self._stats = GraphStatistics(chart)
        self._stats.overlay().setPos(0,0)
        
        
        right_side = QWidget()
        right_side_layout = QVBoxLayout(right_side)
        self._first_val_dt = None

        # Series on continuous graph don't have their X value aligned. 
        # We can only show the value next to each point, not all together in the tree
        self._signal_tree = GraphSignalTree(self, has_value_col=False)
        self._signal_tree.setMinimumWidth(150)
        self._btn_start_stop = QPushButton("")
        self._btn_start_stop.clicked.connect(self._btn_start_stop_slot)
        self._btn_clear = QPushButton("Clear")
        self._btn_clear.clicked.connect(self._btn_clear_slot)
        self._btn_pause = QPushButton("Pause")
        self._btn_pause.clicked.connect(self._btn_pause_slot)
        
        param_widget = QWidget()
        param_layout = QFormLayout(param_widget)

        self._spinbox_graph_max_width = QSpinBox(self)
        self._spinbox_graph_max_width.setMaximum(600)
        self._spinbox_graph_max_width.setMinimum(0)
        self._spinbox_graph_max_width.setValue(self.DEFAULT_GRAPH_MAX_WIDTH)
        self._spinbox_graph_max_width.valueChanged.connect(self._spinbox_graph_max_width_changed_slot)
        self._spinbox_graph_max_width.setKeyboardTracking(False)

        param_layout.addRow("Graph width (s)", self._spinbox_graph_max_width)

        self._feedback_label = FeedbackLabel()
        self._feedback_label.text_label().setWordWrap(True)
        self._graph_maintenance_timer = QTimer()
        self._graph_maintenance_timer.setInterval(1000)
        self._graph_maintenance_timer.timeout.connect(self._graph_maintenance_timer_slot)

        right_side_layout.addWidget(self._signal_tree)
        right_side_layout.addWidget(param_widget)
        right_side_layout.addWidget(self._btn_start_stop)
        right_side_layout.addWidget(self._btn_clear)
        right_side_layout.addWidget(self._btn_pause)
        right_side_layout.addWidget(self._feedback_label)

        self._splitter.addWidget(self._chartview)
        self._splitter.addWidget(right_side)
        self._splitter.setCollapsible(0, False)
        self._splitter.setCollapsible(1, True)

        self._signal_tree.signals.selection_changed.connect(self._selection_changed_slot)

        layout = QHBoxLayout(self)
        layout.addWidget(self._splitter)
        
    def ready(self) -> None:
        # Make the right menu as small as possible. Only works after the widget is loaded. we need the ready() function for that
        self._splitter.setSizes([self.width(), self._signal_tree.minimumWidth()])
        self._update_widgets()

    def teardown(self) -> None:
        self.watchable_registry.unregister_watcher(self._watcher_id())

    def get_state(self) -> Dict[Any, Any]:
        raise NotImplementedError("Not implemented")

    def load_state(self, state: Dict[Any, Any]) -> None:
        raise NotImplementedError("Not implemented")


    # region Controls
    def clear_graph(self) -> None:
        """Delete the graph content and reset the state to of the component to a vanilla state"""
        self._chartview.chart().removeAllSeries()
        self._callout.hide()
        self._clear_stats_and_hide()
        
        for yaxis in self._yaxes:
            with tools.SuppressException():
                self._chartview.chart().removeAxis(yaxis)

        for signal_item in self._serverid2sgnal_item.values():
            if signal_item.series_attached():
                signal_item.detach_series() # Will reload original icons if any
        self._serverid2sgnal_item.clear()
        self._xaxis.setRange(0,1)
        self._xaxis.clear_minmax()
        self._yaxes.clear()
        self._chart_has_content = False
        self._chartview.allow_save_img(False)
        self._chartview.allow_save_csv(False)
        self._first_val_dt = None
        
    
    def stop_acquisition(self) -> None:
        """Stop a an ongoing acquisition"""
        self._stop_periodic_graph_maintenance()     # Not required anymore 
        self.watchable_registry.unwatch_all(self._watcher_id()) # Stops to flow of values
        self._acquiring = False     # Main acquisition flag 
        self._paused = False        # We can't be paused if we are not running. 
        
        self._chartview.setDisabled(True)       # Disable while we do lots of operations on the graph 

        for series in self._all_series():
            series.stop_decimator()         # Flush pending data to the output. Not necessary, future proofing here
            series.flush_full_dataset()     # When stopped, the user wants to see everything.CPU can handle a single draw. Require all data for CSV export.
        
        self._recompute_xaxis_minmax_and_delete_old_data()  # Doesn't change the range, just finds the min/max
        self._round_robin_recompute_single_series_min_max(full=True)        # Update a single series at a time to reduce the load on the CPU
        self._update_yaxes_minmax_based_on_series_minmax()                  # Recompute min/max. Only way to shrink the scale reliably.

        if self.is_autoscale_enabled():
            self._xaxis.autoset_range()         # Range based on min/max computed just above
            for series in self._all_series():
                yaxis = self._get_series_yaxis(series)
                yaxis.autoset_range(margin_ratio=self.Y_AXIS_MARGIN)    # Range based on min/max computed just above

        self.update_stats(use_decimated=False)  # Display 1x decimation factor and all points
        self._chartview.setEnabled(True)
        #self._enable_opengl_drawing(False)  #  Required for callout to work
        self._update_widgets()

    def start_acquisition(self) -> None:
        """Start a graph acquisition"""
        if self._acquiring:
            return 
        
        if self._spinbox_graph_max_width.value() == 0:
            self._report_error("Invalid graph width")
            return 
        
        self._graph_max_width = float(self._spinbox_graph_max_width.value())
        try:
            self.clear_graph()
            signals = self._signal_tree.get_signals()
            if len(signals) == 0:
                self._report_error("No signals")
                return
        
            if len(signals) > self.MAX_SIGNALS:
                self._report_error(f"Too many signals. Max={self.MAX_SIGNALS}")
                return
            
            self._xaxis.setRange(0, 1)
            for axis in signals:
                yaxis = ScrutinyValueAxisWithMinMax(self)
                yaxis.setTitleText(axis.axis_name)
                yaxis.setTitleVisible(True)
                self._yaxes.append(yaxis)
                self._chartview.chart().addAxis(yaxis, Qt.AlignmentFlag.AlignRight)
                
                for signal_item in axis.signal_items:
                    try:
                        server_id = self.watchable_registry.watch_fqn(self._watcher_id(), signal_item.fqn)
                    except WatchableRegistryNodeNotFoundError as e:
                        self._report_error(f"Signal {signal_item.text()} ({signal_item.fqn}) is not available.")
                        self.watchable_registry.unwatch_all(self._watcher_id())
                        self.clear_graph()
                        return
            
                    series = RealTimeScrutinyLineSeries(self)
                    self._chartview.chart().addSeries(series)
                    signal_item.attach_series(series)
                    signal_item.show_series()
                    self._serverid2sgnal_item[server_id] = signal_item
                    series.setName(signal_item.text())
                    series.attachAxis(self._xaxis)
                    series.attachAxis(yaxis)

                    series.clicked.connect(functools.partial(self._series_clicked_slot, signal_item))
                    series.hovered.connect(functools.partial(self._series_hovered_slot, signal_item))

            self._first_val_dt = None
            self._chart_has_content = True
            self._acquiring = True
            self._paused = False
            #self._enable_opengl_drawing(True)   # Reduce CPU usage a lot
            self._change_x_resolution(0)    # 0 mean no decimation
            self.update_emphasize_state()
            self.enable_autoscale()
            self.update_stats(use_decimated=True)
            self.show_stats()
            self._start_periodic_graph_maintenance()
            self._clear_error()
            self._update_widgets()
        except Exception as e:
            tools.log_exception(self.logger, e, "Failed to start the acquisition")
            self.stop_acquisition()
    
    def pause(self) -> None:
        """Pause the real time graph. Flush non-decimated background data buffer to the QChart and prevent further updates."""
        if self._paused:
            return 
        for series in self._all_series():
            series.flush_full_dataset()
            series.pause()
        self.disable_autoscale()
        self.update_stats(use_decimated=False)
        self._paused = True

    def unpause(self) -> None:
        """Unpause the real time graph. Flush decimated background data buffer to the QChart and update periodically"""
        if not self._paused:
            return
            
        for series in self._all_series():
            series.unpause()
            series.flush_decimated()
        self._paused=False
        self.enable_autoscale()
        self.update_stats(use_decimated=True)

    def disable_autoscale(self) -> None:
        self._autoscale_enabled = False

    def enable_autoscale(self) -> None:
        self._autoscale_enabled = True

    def is_autoscale_enabled(self) -> bool:
        return self._autoscale_enabled
    
    def is_acquiring(self) -> bool:
        return self._acquiring

    def is_paused(self) -> bool:
        return self._paused

    def update_emphasize_state(self) -> None:
        """Read the items in the SignalTree object (right menu with axis) and update the size/boldness of the graph series
        based on wether they are selected or not"""
        emphasized_yaxes_id:Set[int] = set()
        selected_index = self._signal_tree.selectedIndexes()
        for item in self._serverid2sgnal_item.values():
            if item.series_attached():
                series = self._get_item_series(item)
                if item.index() in selected_index:
                    series.emphasize()
                    yaxis = self._get_series_yaxis(series)
                    emphasized_yaxes_id.add(id(yaxis))
                else:
                    series.deemphasize()

        for axis in self._yaxes:
            if id(axis) in emphasized_yaxes_id:
                axis.emphasize()
            else:
                axis.deemphasize()

    def auto_scale_xaxis(self) -> None:
        max_x = self._xaxis.maxval()
        min_x = self._xaxis.minval()
        if max_x is not None and min_x is not None:
            if max_x > min_x + self._graph_max_width:
                min_x = max_x - self._graph_max_width
            self._xaxis.setRange(min_x, max_x)
    
    #endregion Control

    # region Internal

    def _get_item_series(self, item:ChartSeriesWatchableStandardItem) -> RealTimeScrutinyLineSeries:
        return cast(RealTimeScrutinyLineSeries, item.series())
    
    def _get_series_yaxis(self, series:RealTimeScrutinyLineSeries) -> ScrutinyValueAxisWithMinMax:
        return cast(ScrutinyValueAxisWithMinMax, self._chartview.chart().axisY(series))
    
    def _all_series(self) -> Generator[RealTimeScrutinyLineSeries, None, None]:
        for item in self._serverid2sgnal_item.values():
            yield self._get_item_series(item)

    def _enable_opengl_drawing(self, val:bool) -> None:
        for series in self._all_series():
            series.setUseOpenGL(val)
        # Force redraw.
        self._chartview.setDisabled(True)
        self._chartview.setDisabled(False)

    def _change_x_resolution(self, resolution:float) -> None:
        self._x_resolution = resolution
        for series in self._all_series():
            series.set_x_resolution(resolution)
        self.update_stats()

    def update_stats(self, use_decimated:Optional[bool]=None) -> None:
        if use_decimated is None:
            use_decimated = True if not self.is_paused() else False
        self._stats.decimation_factor = 0
        self._stats.visible_points = 0
        self._stats.total_points = 0
        all_series = list(self._all_series())
        if use_decimated:
            nb_series = len(all_series)
            if nb_series > 0:
                per_series_weight = 1/nb_series
                for series in all_series:
                    self._stats.decimation_factor += series.decimation_factor() * per_series_weight
                    self._stats.visible_points+=series.count_visible_points()
                    self._stats.total_points+=series.count_all_points()
        else:
            self._stats.decimation_factor = 1
            total_points = 0
            for series in all_series:
                total_points  += series.count_all_points()
            self._stats.visible_points = total_points
            self._stats.total_points = total_points

        if not self._paused:
            self._stats.update_overlay()

    def _clear_stats_and_hide(self)->None:
        self._stats.clear()
        self._stats.hide_overlay()
    
    def show_stats(self) -> None:
        self._stats.show_overlay()

    def _update_widgets(self) -> None:
        if self.is_acquiring():
            self._btn_clear.setDisabled(True)
            self._btn_start_stop.setText("Stop")
            self._btn_pause.setEnabled(True)
        else:
            self._btn_clear.setEnabled(True)
            self._btn_start_stop.setText("Start")
            self._btn_pause.setDisabled(True)

        if self._paused:
            self._btn_pause.setText("Unpause")
        else:
            self._btn_pause.setText("Pause")

        if self._chart_has_content:
            self._signal_tree.lock()
        else:
            self._signal_tree.unlock()

        if self._chart_has_content and not self.is_acquiring():
            self._btn_clear.setEnabled(True)
            self._chartview.allow_save_img(True)
            self._chartview.allow_save_csv(True)
        else:
            self._btn_clear.setDisabled(True)
            self._chartview.allow_save_img(False)
            self._chartview.allow_save_csv(False)

    def _watcher_id(self) -> str:
        return self.instance_name
    
    def _report_error(self, msg:str) -> None:
        self._feedback_label.set_error(msg)
    
    def _clear_error(self) -> None:
        self._feedback_label.clear()

    def _val_update_callback(self, watcher_id:Union[str, int], value_updates:List[ValueUpdate]) -> None:
        """Invoked when we have new data available"""
        if not self._chart_has_content:
            self.logger.error("Received value updates when no graph was ready")
            return 
        
        if self._first_val_dt is None:
            self._first_val_dt = value_updates[0].update_timestamp   # precise to the microsecond. Coming from the server

        tstart = self._first_val_dt
        def get_x(val:ValueUpdate) -> float:    # A getter to get the relative timestamp
            return  (val.update_timestamp-tstart).total_seconds()
        
        try:
            for value_update in value_updates:
                xval = get_x(value_update)
                yval = float(value_update.value)
                
                series = self._get_item_series(self._serverid2sgnal_item[value_update.watchable.server_id]) 
                yaxis = self._get_series_yaxis(series)
                series.add_point(QPointF(xval, yval))
                self._xaxis.update_minmax(xval)
                yaxis.update_minmax(yval)   # Can only grow
                if self.is_autoscale_enabled():
                    yaxis.autoset_range(margin_ratio=self.Y_AXIS_MARGIN)
            
            if self.is_autoscale_enabled():
                self.auto_scale_xaxis()

            if not self.is_paused():
                for series in self._all_series():
                    if series.is_dirty():
                        series.flush_decimated()
                
        except KeyError as e:
            tools.log_exception(self.logger, e, "Received a value update from a watchable that maps to no valid series in the chart")
            self.stop_acquisition()
        except Exception as e:
            tools.log_exception(self.logger, e, f"Error when receiving data for the chart")
            self.stop_acquisition()

            
    def _unwatch_callback(self, watcher_id:Union[str, int], server_path:str, watchable_config:sdk.WatchableConfiguration) -> None:
        # Should we do something? User feedback if the watcahble is not available anymore maybe?
        pass
    
    def _start_periodic_graph_maintenance(self) -> None:
        self._y_minmax_recompute_index=0
        self._graph_maintenance_timer.start()
    
    def _stop_periodic_graph_maintenance(self) -> None:
        self._graph_maintenance_timer.stop()

    def _round_robin_recompute_single_series_min_max(self, full:bool) -> None:
        """Compute a series min/max values. 
        if full=``False``, does only 1 series per call to reduce the load on the CPU. Does all if full=``True``"""
        sorted_ids = sorted(list(self._serverid2sgnal_item.keys()))
        all_series = [self._get_item_series(self._serverid2sgnal_item[server_id]) for server_id in sorted_ids]
        
        if full:
            self._y_minmax_recompute_index = 0
        nb_loop = len(all_series) if full else 1

        for i in range(nb_loop):
            if self._y_minmax_recompute_index < len(all_series):
                series = all_series[self._y_minmax_recompute_index]
                series.recompute_minmax()
            
            self._y_minmax_recompute_index+=1
            if self._y_minmax_recompute_index >= len(all_series):
                self._y_minmax_recompute_index = 0
        

    def _update_yaxes_minmax_based_on_series_minmax(self) -> None:
        """Recompute the min/max values of an axis using the minmax values of each series. 
        series.recompute_minmax() must be called prior to this method"""
        allseries = list(self._all_series())
        for yaxis in self._yaxes:
            yaxis.clear_minmax()
            for series in allseries:
                if id(yaxis) in [id(axis) for axis in series.attachedAxes()]:
                    minv, maxv = series.y_min(), series.y_max()
                    if minv is not None:
                        yaxis.update_minmax(minv)
                    if maxv is not None:
                        yaxis.update_minmax(maxv)


    def _compute_new_decimator_resolution(self) -> None:
        """Compute a decimator resolution to have ~1pt per pixel. Maybe a little more to spare the CPU."""
        w = self._chartview.chart().size().width()
        xspan = self._xaxis.max() - self._xaxis.min()
        sec_per_pixel = xspan/w
        resolution = 2*sec_per_pixel        # When full, the decimator produces 2 points per time slice. (min/max
        resolution = 1.5*resolution         # Heuristic to reduce the CPU load. Result is visually acceptable
        resolution = round(resolution, 2)   # Avoid constantly recomputing the decimated data
        self._change_x_resolution(resolution)

    def _recompute_xaxis_minmax_and_delete_old_data(self) -> None:
        """Delete old data, then recompute the X-Axis min/max values without touching the effective chart range"""
        # X axis maintenance (span shrink)
        new_max_f = -math.inf
        
        for series in self._all_series():
            last_x = series.get_last_x()
            if last_x is None:
                continue    # Means serie sis empty.
            new_max_f = max(new_max_f, last_x)
        
        if not math.isfinite(new_max_f):
            return
        
        new_min_x = math.inf
        lower_x_bound_for_deletion = new_max_f - self._graph_max_width  # wanted lower bound
        for series in self._all_series():
            series.delete_up_to_x(lower_x_bound_for_deletion)
            first_x = series.get_first_x()

            if first_x is not None:
                new_min_x = min(new_min_x, first_x) # Reduce the axis lower bound to the series lower bound

        if math.isfinite(new_min_x):
            self._xaxis.set_minval(new_min_x)
            self._xaxis.set_maxval(new_max_f)

    # endregion Internal

    # region SLOTS
    def _btn_clear_slot(self) -> None:
        """Slot when "clear" is clicked"""
        if not self.is_acquiring():
            self.clear_graph()
        self._clear_error()
        self._update_widgets()

    def _btn_pause_slot(self) -> None:
        """Slot when "pause" is clicked"""
        if self.is_paused():           
            self.unpause()
        else:
            self.pause()
        self._update_widgets()

    def _btn_start_stop_slot(self) -> None:
        """Slot when "start/stop" is clicked"""
        if self.is_acquiring():           
            self.stop_acquisition()
        else:
            self.start_acquisition()
        self._update_widgets()
    
    def _selection_changed_slot(self) -> None:
        """Whent he user selected/deselected a signal in the right menu"""
        self.update_emphasize_state()
        
    def _series_clicked_slot(self, signal_item:ChartSeriesWatchableStandardItem, point:QPointF) -> None:
        """When the user clicked a line on the graph. We make it bold and select the matching item in the right menu"""
        sel = self._signal_tree.selectionModel()
        sel.select(signal_item.index(), QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)

    def _graph_maintenance_timer_slot(self) -> None:
        """Periodic callback meant to prune the graph and recompute the rang eof the axis.
        Done periodically to reduce the strain on the CPU"""
        if not self.is_acquiring():
            return

        self._compute_new_decimator_resolution()
        self._recompute_xaxis_minmax_and_delete_old_data()
        self._round_robin_recompute_single_series_min_max(full=False) # Update a single series at a time to reduce the load on the CPU
        self._update_yaxes_minmax_based_on_series_minmax()  # Recompute min/max. Only way to shrink the scale reliably.
        self.update_stats()    # Recompute the stats and display
        

    def _series_hovered_slot(self, signal_item:ChartSeriesWatchableStandardItem, point:QPointF, state:bool) -> None:
        # FIXME : Snap zone is too small. QT source code says it is computed with markersize, but changing it has no effect.
        must_show = state
        if self.is_acquiring() and self.is_autoscale_enabled():
            must_show  = False

        if must_show:
            series = cast(ScrutinyLineSeries, signal_item.series())
            closest_real_point = series.search_closest_monotonic(point.x())
            if closest_real_point is not None:
                self._callout_hide_timer.stop()
                txt = f"{signal_item.text()}\nX: {closest_real_point.x()}\nY: {closest_real_point.y()}"
                pos = self._chartview.chart().mapToPosition(closest_real_point, series)
                color = series.color()
                self._callout.set_content(pos, txt, color)
                self._callout.show()
        else:
            self._callout_hide_timer.start()

    def _callout_hide_timer_slot(self)-> None:
        self._callout.hide()

    def _spinbox_graph_max_width_changed_slot(self, val:int) -> None:
        if val == 0:
            self._spinbox_graph_max_width.setProperty("state", WidgetState.error)
            return
        self._spinbox_graph_max_width.setProperty("state", WidgetState.default)
        
        self._graph_max_width = val
        if self.is_acquiring() and self.is_autoscale_enabled():
            self.auto_scale_xaxis()
        
        # QT Selects the textbox when the value is changed. We add a clear action at the end of the event loop
        def deselect_spinbox() -> None:
            child = cast(Optional[QLineEdit], self._spinbox_graph_max_width.findChild(QLineEdit))
            if child is not None:
                child.deselect()
                child.clearFocus()
        InvokeQueued(deselect_spinbox)

    def _save_csv_slot(self, filename:str) -> None:
        def finished_callback(exception:Optional[Exception]) -> None:
            # This runs in a different thread
            # Todo : Add visual "saving..." feedback ?
            if exception is not None:
                tools.log_exception(self.logger, exception, f"Error while saving graph into {filename}" )
                InvokeInQtThread(lambda: exception_msgbox(self, "Failed to save", f"Failed to save the graph to {filename}", exception))
            
        if self._chart_has_content:
            export_chart_csv_threaded(filename, self._signal_tree.get_signals(), finished_callback)

    
    #endregion
