#    continuous_graph_component.py
#        A component that makes a real time graphs of the values streamed by the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from datetime import datetime
import functools

from PySide6.QtWidgets import QHBoxLayout, QSplitter, QWidget, QVBoxLayout, QPushButton, QCheckBox, QFormLayout, QSpinBox
from PySide6.QtCharts import QChart
from PySide6.QtCore import Qt, QItemSelectionModel, QPointF, QTimer
from scrutiny.gui.widgets.feedback_label import FeedbackLabel

from scrutiny.gui import assets
from scrutiny.gui.core.definitions import WidgetState
from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from scrutiny.gui.dashboard_components.common.graph_signal_tree import GraphSignalTree, ChartSeriesWatchableStandardItem
from scrutiny.gui.dashboard_components.common.base_chart import ScrutinyLineSeries, ScrutinyValueAxisWithMinMax, ScrutinyChartCallout, ScrutinyChartView
from scrutiny.gui.core.watchable_registry import WatchableRegistryNodeNotFoundError, ValueUpdate
from scrutiny import sdk
from scrutiny import tools

from typing import Dict, Any, Union, List, Optional, cast, Set, Tuple


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
        self.watchable_registry.register_watcher(self.instance_name, self._val_update_callback, self._unwatch_callback)
        
        self._splitter = QSplitter(self)
        self._splitter.setOrientation(Qt.Orientation.Horizontal)
        self._splitter.setContentsMargins(0,0,0,0)
        self._splitter.setHandleWidth(5)
        
        self._chartview = ScrutinyChartView(self)
        chart = QChart()
        chart.layout().setContentsMargins(0,0,0,0)
        chart.setAxisX(self._xaxis)
        self._chartview.setChart(chart)
        self._callout = ScrutinyChartCallout(chart)
        self._callout_hide_timer = QTimer()
        self._callout_hide_timer.setInterval(250)
        self._callout_hide_timer.setSingleShot(True)
        self._callout_hide_timer.timeout.connect(self._callout_hide_timer_slot)
        
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
    
    def stop_acquisition(self) -> None:
        """Stop a an ongoing acquisition"""
        self._graph_maintenance_timer.stop()
        self.watchable_registry.unwatch_all(self._watcher_id())
        self._acquiring = False
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
            
                    series = ScrutinyLineSeries(self)
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
            self._graph_maintenance_timer.start()
            self.enable_autoscale()
            self.update_emphasize_state()
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

    def _val_update_callback(self, watcher_id:Union[str, int], vals:List[ValueUpdate]) -> None:
        if not self._chart_has_content:
            self.logger.error("Received value updates when no graph was ready")
            return 
        
        if self._first_val_dt is None:
            self._first_val_dt = vals[0].update_timestamp   # precise to the microsecond. Coming from the server

        tstart = self._first_val_dt
        def get_x(val:ValueUpdate) -> float:
            return  (val.update_timestamp-tstart).total_seconds()
        
        try:
            for val in vals:
                xval = get_x(val)
                yval = float(val.value)

                series = cast(ScrutinyLineSeries, self._serverid2sgnal_item[val.watchable.server_id].series())
                yaxis = cast(ScrutinyValueAxisWithMinMax, self._chartview.chart().axisY(series))
                self._xaxis.update_minmax(xval)
                yaxis.update_minmax(yval)   # Can only grow
                series.add_point_with_minmax(xval, yval)
                if self.is_autoscale_enabled():
                    yaxis.autoset_range(margin_ratio=0.02)
            
            if self.is_autoscale_enabled():
                self.auto_scale_xaxis()

        except KeyError as e:
            tools.log_exception(self.logger, e, "Received a value update from a watchable that maps to no valid series in the chart")
            self.stop_acquisition()
        except Exception as e:
            tools.log_exception(self.logger, e, f"Error when receiving data for the chart")
            self.stop_acquisition()
            
    def _unwatch_callback(self, watcher_id:Union[str, int], server_path:str, watchable_config:sdk.WatchableConfiguration) -> None:
        # Should we do something? User feedback if the watcahble is not available anymore maybe?
        pass
    
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
        if not self.is_acquiring():
            return
        
        new_min_x = self._xaxis.maxval()
        if new_min_x is None:
            return 

        for item in self._serverid2sgnal_item.values():
            series = item.series()
            points = series.points()
            if len(points) == 0:
                continue
            series_maxx = points[-1].x()
            min_allowed_x = series_maxx - self._graph_max_width
            count=0
            
            for point in points:
                x = point.x() 
                if x >= min_allowed_x:
                    new_min_x = min(new_min_x, x)
                    break
                count+=1
                
            if count > 0:
                series.removePoints(0, count)

        self._xaxis.set_minval(new_min_x)
    
    def _series_hovered_slot(self, signal_item:ChartSeriesWatchableStandardItem, point:QPointF, state:bool) -> None:
        # FIXME : Snap zone is too small. QT source code says it is computed with markersize, but changing it has no effect.
        must_show = state
        if self.is_acquiring() and self.is_autoscale_enabled():
            must_show  = False

        if must_show:
            series = cast(ScrutinyLineSeries, signal_item.series())
            closest_real_point = series.monotonic_search_closest(point.x())
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
    
    #endregion
