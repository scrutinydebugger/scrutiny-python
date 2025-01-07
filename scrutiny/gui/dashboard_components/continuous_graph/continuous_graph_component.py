#    continuous_graph_component.py
#        A component that makes a real time graphs of the values streamed by the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from datetime import datetime
import functools

from PySide6.QtGui import QPainter, QFontMetrics, QFont, QColor
from PySide6.QtWidgets import (QHBoxLayout, QSplitter, QWidget, QVBoxLayout, 
                               QPushButton, QCheckBox, QFormLayout, QSpinBox, QGraphicsItem, QStyleOptionGraphicsItem,
                               QLineEdit)
from PySide6.QtCore import Qt, QItemSelectionModel, QPointF, QTimer, QRectF, QRect
from scrutiny.gui.widgets.feedback_label import FeedbackLabel

from scrutiny.gui import assets
from scrutiny.gui.tools.min_max import MinMax
from scrutiny.gui.core.definitions import WidgetState
from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from scrutiny.gui.dashboard_components.common.graph_signal_tree import GraphSignalTree, ChartSeriesWatchableStandardItem
from scrutiny.gui.dashboard_components.common.base_chart import (
    ScrutinyLineSeries, ScrutinyValueAxisWithMinMax, ScrutinyChartCallout, ScrutinyChartView, ScrutinyChart)
from scrutiny.gui.dashboard_components.continuous_graph.decimator import GraphMonotonicNonUniformMinMaxDecimator
from scrutiny.gui.core.watchable_registry import WatchableRegistryNodeNotFoundError, ValueUpdate
from scrutiny import sdk
from scrutiny import tools
from scrutiny.gui.tools.invoker import InvokeQueued

from typing import Dict, Any, Union, List, Optional, cast, Set

class DecimableScrutinyLineSeries(ScrutinyLineSeries):
    _decimator:GraphMonotonicNonUniformMinMaxDecimator
    _x_minmax:MinMax
    _y_minmax:MinMax

    def __init__(self, *args:Any, **kwargs:Any) -> None:
        super().__init__(*args, **kwargs)
        self._decimator = GraphMonotonicNonUniformMinMaxDecimator()
        self._x_minmax = MinMax()
        self._y_minmax = MinMax()
        
    def set_x_resolution(self, resolution:float) -> None:
        if self._decimator.set_x_resolution(resolution):
            self.flush()
    
    def decimation_factor(self) -> float:
        return self._decimator.decimation_factor()
    
    def count_visible_points(self) -> int:
        return len(self._decimator.get_decimated_buffer())

    def count_all_points(self) -> int:
        return len(self._decimator.get_input_buffer())

    def add_point(self, point:QPointF) -> int:
        n = self._decimator.add_point(point)
        if n > 0:
            for p in self._decimator.get_decimated_buffer()[-n:]:
                self._y_minmax.update(p.y())
                self._x_minmax.update_max(p.x())
        return n
    
    def delete_up_to_x(self, x:float) -> None:
        self._decimator.delete_data_up_to_x(x)
    
    def get_last_x(self) -> Optional[float]:
        decimated = self._decimator.get_decimated_buffer()
        if len(decimated) == 0:
            return None
        return decimated[-1].x()

    def get_first_x(self) -> Optional[float]:
        decimated = self._decimator.get_decimated_buffer()
        if len(decimated) == 0:
            return None
        return decimated[0].x()

    def flush(self) -> None:
        self.replace(self._decimator.get_decimated_buffer())

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

    def update_overlay(self) -> None:
        self._overlay.update_content()

    def overlay(self) -> Overlay:
        return self._overlay


class ContinuousGraphComponent(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("graph-96x128.png")
    _NAME = "Continuous Graph"

    DEFAULT_GRAPH_MAX_WIDTH=30

    _chartview:ScrutinyChartView
    """The QT chartview"""
    _callout:ScrutinyChartCallout
    """A callout (popup bubble) that shows the values on hover"""
    _signal_tree:GraphSignalTree
    """The right menu with axis and signal"""
    _btn_start_stop:QPushButton
    """The start/stop button"""
    _chk_autoscale:QCheckBox
    """Autoscal checkbox"""
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
    
    _stats:GraphStatistics

    _xaxis:ScrutinyValueAxisWithMinMax
    """The single time X-Axis"""
    _yaxes:List[ScrutinyValueAxisWithMinMax]
    """All the Y-Axes defined by the user"""

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
        
        param_widget = QWidget()
        param_layout = QFormLayout(param_widget)
        
        self._chk_autoscale = QCheckBox(self)
        self._chk_autoscale.checkStateChanged.connect(self._chk_autoscale_slot)
        
        self._spinbox_graph_max_width = QSpinBox(self)
        self._spinbox_graph_max_width.setMaximum(600)
        self._spinbox_graph_max_width.setMinimum(0)
        self._spinbox_graph_max_width.setValue(self.DEFAULT_GRAPH_MAX_WIDTH)
        self._spinbox_graph_max_width.valueChanged.connect(self._spinbox_graph_max_width_changed_slot)
        self._spinbox_graph_max_width.setKeyboardTracking(False)

        param_layout.addRow("Graph width (s)", self._spinbox_graph_max_width)
        param_layout.addRow("Autoscale", self._chk_autoscale)

        self._feedback_label = FeedbackLabel()
        self._feedback_label.text_label().setWordWrap(True)
        self._graph_maintenance_timer = QTimer()
        self._graph_maintenance_timer.setInterval(1000)
        self._graph_maintenance_timer.timeout.connect(self._graph_maintenance_timer_slot)

        right_side_layout.addWidget(self._signal_tree)
        right_side_layout.addWidget(param_widget)
        right_side_layout.addWidget(self._btn_start_stop)
        right_side_layout.addWidget(self._btn_clear)
        right_side_layout.addWidget(self._feedback_label)

        self._splitter.addWidget(self._chartview)
        self._splitter.addWidget(right_side)
        self._splitter.setCollapsible(0, False)
        self._splitter.setCollapsible(1, True)

        self._signal_tree.signals.selection_changed.connect(self._selection_changed_slot)

        layout = QHBoxLayout(self)
        layout.addWidget(self._splitter)

        self._chk_autoscale.setChecked(True)
        
    def ready(self) -> None:
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
        self._stats.overlay().hide()
        self._stats.clear()
    
    def stop_acquisition(self) -> None:
        """Stop a an ongoing acquisition"""
        self._graph_maintenance_timer.stop()
        self.watchable_registry.unwatch_all(self._watcher_id())
        self._acquiring = False
        
        self._chartview.setDisabled(True)
        self._do_graph_maintenance(full=True)
        for item in self._serverid2sgnal_item.values():
            series = self._get_item_series(item)
            series.stop_decimator()
            series.flush()
        self._update_stats()
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
            
                    series = DecimableScrutinyLineSeries(self)
                    self._chartview.chart().addSeries(series)
                    signal_item.attach_series(series)
                    signal_item.show_series()
                    self._serverid2sgnal_item[server_id] = signal_item
                    series.setName(signal_item.text())
                    series.attachAxis(self._xaxis)
                    series.attachAxis(yaxis)

                    series.clicked.connect(functools.partial(self._series_clicked_slot, signal_item))
                    series.hovered.connect(functools.partial(self._series_hovered_slot, signal_item))

            self._y_minmax_recompute_index=0
            self._first_val_dt = None
            self._chart_has_content = True
            self._acquiring = True
            self._graph_maintenance_timer.start()
            #self._enable_opengl_drawing(True)   # Reduce CPU usage a lot
            self._change_x_resolution(0)
            self.update_emphasize_state()
            self.enable_autoscale()
            self._update_stats()
            self._stats.overlay().show()
            self._clear_error()
            self._update_widgets()
        except Exception as e:
            tools.log_exception(self.logger, e, "Failed to start the acquisition")
            self.stop_acquisition()
    
    def disable_autoscale(self) -> None:
        self._autoscale_enabled = False

    def enable_autoscale(self) -> None:
        self._autoscale_enabled = True

    def is_autoscale_enabled(self) -> bool:
        return self._autoscale_enabled
    
    def is_acquiring(self) -> bool:
        return self._acquiring

    def update_emphasize_state(self) -> None:
        """Read the items in the SignalTree object (right menu with axis) and update the size/boldness of the graph series
        based on wether they are selected or not"""
        emphasized_yaxes_id:Set[int] = set()
        selected_index = self._signal_tree.selectedIndexes()
        for item in self._serverid2sgnal_item.values():
            if item.series_attached():
                series = cast(ScrutinyLineSeries, item.series())
                if item.index() in selected_index:
                    series.emphasize()
                    yaxis = self._chartview.chart().axisY(series)
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

    def _get_item_series(self, item:ChartSeriesWatchableStandardItem) -> DecimableScrutinyLineSeries:
        return cast(DecimableScrutinyLineSeries, item.series())
    
    def _enable_opengl_drawing(self, val:bool) -> None:
        for item in self._serverid2sgnal_item.values():
            item.series().setUseOpenGL(val)
        # Force redraw.
        self._chartview.setDisabled(True)
        self._chartview.setDisabled(False)

    def _change_x_resolution(self, resolution:float) -> None:
        self._x_resolution = resolution
        
        for item in self._serverid2sgnal_item.values():
            self._get_item_series(item).set_x_resolution(resolution)
            
        self._update_stats()

    def _update_stats(self) -> None:
        self._stats.decimation_factor = 0
        self._stats.visible_points = 0
        self._stats.total_points = 0
        nb_series = len(self._serverid2sgnal_item)
        if nb_series > 0:
            per_series_weight = 1/nb_series
            for item in self._serverid2sgnal_item.values():
                series = self._get_item_series(item)
                self._stats.decimation_factor += series.decimation_factor() * per_series_weight
                self._stats.visible_points+=series.count_visible_points()
                self._stats.total_points+=series.count_all_points()
    
        self._stats.update_overlay()

    def _update_widgets(self) -> None:
        if self.is_acquiring():
            self._btn_clear.setDisabled(True)
            self._btn_start_stop.setText("Stop")
        else:
            self._btn_clear.setEnabled(True)
            self._btn_start_stop.setText("Start")

        if self._chart_has_content:
            self._signal_tree.lock()
        else:
            self._signal_tree.unlock()

        if self._autoscale_enabled:
            self._chk_autoscale.setCheckState(Qt.CheckState.Checked)
        else:
            self._chk_autoscale.setCheckState(Qt.CheckState.Unchecked)
        
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
        if not self._chart_has_content:
            self.logger.error("Received value updates when no graph was ready")
            return 
        
        if self._first_val_dt is None:
            self._first_val_dt = value_updates[0].update_timestamp   # precise to the microsecond. Coming from the server

        tstart = self._first_val_dt
        def get_x(val:ValueUpdate) -> float:
            return  (val.update_timestamp-tstart).total_seconds()
        
        self._chartview.setDisabled(True)
        modified_series = set()
        try:
            for value_update in value_updates:
                xval = get_x(value_update)
                yval = float(value_update.value)

                series = self._get_item_series(self._serverid2sgnal_item[value_update.watchable.server_id]) 
                if series.add_point(QPointF(xval, yval)) > 0:
                    modified_series.add(id(series))

                yaxis = cast(ScrutinyValueAxisWithMinMax, self._chartview.chart().axisY(series))
                self._xaxis.update_minmax(xval)
                yaxis.update_minmax(yval)   # Can only grow
                if self.is_autoscale_enabled():
                    yaxis.autoset_range(margin_ratio=0.02)
            
            if self.is_autoscale_enabled():
                self.auto_scale_xaxis()

            for item in self._serverid2sgnal_item.values():
                series = self._get_item_series(item)
                if id(series) in modified_series:
                    series.flush()
                
        except KeyError as e:
            tools.log_exception(self.logger, e, "Received a value update from a watchable that maps to no valid series in the chart")
            self.stop_acquisition()
        except Exception as e:
            tools.log_exception(self.logger, e, f"Error when receiving data for the chart")
            self.stop_acquisition()
        
        self._chartview.setDisabled(False)

            
    def _unwatch_callback(self, watcher_id:Union[str, int], server_path:str, watchable_config:sdk.WatchableConfiguration) -> None:
        # Should we do something? User feedback if the watcahble is not available anymore maybe?
        pass
    
    def _round_robin_recompute_single_series_min_max(self, full:bool) -> None:
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
        allseries = [ cast(DecimableScrutinyLineSeries, item.series()) for item in self._serverid2sgnal_item.values()]
        for yaxis in self._yaxes:
            yaxis.clear_minmax()
            for series in allseries:
                if id(yaxis) in [id(axis) for axis in series.attachedAxes()]:
                    minv, maxv = series.y_min(), series.y_max()
                    if minv is not None:
                        yaxis.update_minmax(minv)
                    if maxv is not None:
                        yaxis.update_minmax(maxv)


    def _do_graph_maintenance(self, full:bool) -> None:
        w = self._chartview.chart().size().width()
        xspan = self._xaxis.max() - self._xaxis.min()
        sec_per_pixel = xspan/w
        resolution = round(2*sec_per_pixel, 2)
        self._change_x_resolution(resolution)

        # X axis maintenance (span shrink)
        new_min_x = self._xaxis.maxval()
        if new_min_x is not None:
            for item in self._serverid2sgnal_item.values():
                series = self._get_item_series(item)
                last_x = series.get_last_x()
                if last_x is None:
                    continue
                min_allowed_x = last_x - self._graph_max_width
                series.delete_up_to_x(min_allowed_x)
                first_x = series.get_first_x()
                if first_x is not None:
                    new_min_x = min(new_min_x, first_x)

            self._xaxis.set_minval(new_min_x)

        # Y-Axis mainteance (span shrink)
        self._round_robin_recompute_single_series_min_max(full=full) # Update a single series at a time to reduce the load on the CPU
        self._update_yaxes_minmax_based_on_series_minmax()  # Recompute min/max. Only way to shrink the scale reliably.
        self._update_stats()


    # endregion Internal

    # region SLOTS
    def _chk_autoscale_slot(self, state:Qt.CheckState) -> None:
        if state == Qt.CheckState.Checked:
            self.enable_autoscale()
        else:
            self.disable_autoscale()
        self._update_widgets()

    def _btn_clear_slot(self) -> None:
        """Slot when "clear" is clicked"""
        if not self.is_acquiring():
            self.clear_graph()
        self._clear_error()
        
        self._update_widgets()

    def _btn_start_stop_slot(self) -> None:
        """Slot when "start/stop" is clicked"""
        if self.is_acquiring():           
            self.stop_acquisition()
        else:
            self.start_acquisition()
    
    def _selection_changed_slot(self) -> None:
        self.update_emphasize_state()
        
    def _series_clicked_slot(self, signal_item:ChartSeriesWatchableStandardItem, point:QPointF) -> None:
        sel = self._signal_tree.selectionModel()
        sel.select(signal_item.index(), QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)

    def _graph_maintenance_timer_slot(self) -> None:
        """Periodic callback meant to prune the graph and recompute the rang eof the axis.
        Done periodically to reduce the strain on the CPU"""
        if not self.is_acquiring():
            return

        self._do_graph_maintenance(full=False) 
        

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
        def deselect_spinbox():
            child = cast(Optional[QLineEdit], self._spinbox_graph_max_width.findChild(QLineEdit))
            if child is not None:
                child.deselect()
            child.clearFocus()
        InvokeQueued(deselect_spinbox)
    
    #endregion
