#    continuous_graph_component.py
#        A component that makes a real time graphs of the values streamed by the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from datetime import datetime

from PySide6.QtWidgets import QHBoxLayout, QSplitter, QWidget, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCharts import QChart, QChartView
from PySide6.QtCore import Qt

from scrutiny.gui import assets
from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from scrutiny.gui.dashboard_components.common.graph_signal_tree import GraphSignalTree, ChartSeriesWatchableStandardItem
from scrutiny.gui.dashboard_components.common.base_chart import ScrutinyLineSeries, ScrutinyValueAxis
from scrutiny.gui.core.watchable_registry import WatchableRegistryNodeNotFoundError, ValueUpdate
from scrutiny import sdk
from scrutiny import tools

from typing import Dict, Any, Union, List, Optional, cast, Set


class ContinuousGraphComponent(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("graph-96x128.png")
    _NAME = "Continuous Graph"

    _chartview:QChartView
    _signal_tree:GraphSignalTree
    _btn_start_stop:QPushButton
    _btn_clear:QPushButton
    _message_label:QLabel
    _splitter:QSplitter
    _acquiring:bool
    _chart_has_content:bool
    _serverid2item:Dict[str, ChartSeriesWatchableStandardItem]

    _xaxis:ScrutinyValueAxis
    _yaxes:List[ScrutinyValueAxis]

    def setup(self) -> None:
        self._acquiring = False
        self._chart_has_content = False
        self._serverid2item = {}
        self._xaxis = ScrutinyValueAxis(self)
        self._xaxis.setTitleText("Time [s]")
        self._xaxis.setTitleVisible(True)
        self._xaxis.deemphasize()   # Default state
        self._yaxes = []
        self.watchable_registry.register_watcher(self.instance_name, self.val_update_callback, self.unwatch_callback)
        
        self._splitter = QSplitter(self)
        self._splitter.setOrientation(Qt.Orientation.Horizontal)
        self._splitter.setContentsMargins(0,0,0,0)
        self._splitter.setHandleWidth(5)
        
        self._chartview = QChartView(self)
        self._chartview.setChart(QChart())
        self._chartview.chart().layout().setContentsMargins(0,0,0,0)
        self._chartview.chart().setAxisX(self._xaxis)
        
        right_side = QWidget()
        right_side_layout = QVBoxLayout(right_side)
        
        self._signal_tree = GraphSignalTree(self)
        self._signal_tree.setMinimumWidth(150)
        self._btn_start_stop = QPushButton("")
        self._btn_start_stop.clicked.connect(self.btn_start_stop_slot)
        self._btn_clear = QPushButton("Clear")
        self._btn_clear.clicked.connect(self.btn_clear_slot)
        self._message_label = QLabel()
        right_side_layout.addWidget(self._signal_tree)
        right_side_layout.addWidget(self._btn_start_stop)
        right_side_layout.addWidget(self._btn_clear)
        right_side_layout.addWidget(self._message_label)

        self._splitter.addWidget(self._chartview)
        self._splitter.addWidget(right_side)
        self._splitter.setCollapsible(0, False)
        self._splitter.setCollapsible(1, True)

        self._signal_tree.signals.selection_changed.connect(self.selection_changed_slot)

        layout = QHBoxLayout(self)
        layout.addWidget(self._splitter)

        
    def ready(self) -> None:
        self._splitter.setSizes([self.width(), self._signal_tree.minimumWidth()])
        self.update_widgets()

    def teardown(self) -> None:
        self.watchable_registry.unregister_watcher(self.watcher_id())

    def get_state(self) -> Dict[Any, Any]:
        raise NotImplementedError()

    def load_state(self, state: Dict[Any, Any]) -> None:
        raise NotImplementedError()

    def clear_graph(self) -> None:
        self._chartview.chart().removeAllSeries()
        
        for yaxis in self._yaxes:
            with tools.SuppressException():
                self._chartview.chart().removeAxis(yaxis)

        for signal_item in self._serverid2item.values():
            if signal_item.series_attached():
                signal_item.detach_series() # Will reload original icons if any
        self._serverid2item.clear()
        self._xaxis.setRange(0,1)
        self._yaxes.clear()
        self._chart_has_content = False
    
    def stop_acquisition(self) -> None:
        self.watchable_registry.unwatch_all(self.watcher_id())
        self._acquiring = False
        self.update_widgets()

    def start_acquisition(self) -> None:
        if self._acquiring:
            return 
        try:
            self.clear_graph()
            signals = self._signal_tree.get_signals()
            if len(signals) == 0:
                self.report_error("No signals")
                return
            
            self._xaxis.setRange(datetime.now().timestamp(), datetime.now().timestamp() + 30)   # FIXME
            for axis in signals:
                yaxis = ScrutinyValueAxis(self)
                yaxis.setTitleText(axis.axis_name)
                yaxis.setTitleVisible(True)
                self._yaxes.append(yaxis)
                self._chartview.chart().addAxis(yaxis, Qt.AlignmentFlag.AlignRight)
                
                for signal_item in axis.signal_items:
                    try:
                        server_id = self.watchable_registry.watch_fqn(self.watcher_id(), signal_item.fqn)
                    except WatchableRegistryNodeNotFoundError as e:
                        self.report_error(f"Signal {signal_item.text()} ({signal_item.fqn}) is not available.")
                        self.watchable_registry.unwatch_all(self.watcher_id())
                        self.clear_graph()
                        return
            
                    series = ScrutinyLineSeries(self)
                    self._chartview.chart().addSeries(series)
                    signal_item.attach_series(series)
                    signal_item.change_icon_to_series_color()
                    self._serverid2item[server_id] = signal_item
                    series.setName(signal_item.text())
                    series.attachAxis(self._xaxis)
                    series.attachAxis(yaxis)

            self._chart_has_content = True
            self._acquiring = True
            self.update_emphasize_state()
            self.update_widgets()
        except Exception as e:
            tools.log_exception(self.logger, e, "Failed to start the acquisition")
            self.stop_acquisition()
    
    def btn_clear_slot(self) -> None:
        if not self._acquiring:
            self.clear_graph()
        
        self.update_widgets()

    def btn_start_stop_slot(self) -> None:
        if self._acquiring:           
            self.stop_acquisition()
        else:
            self.start_acquisition()
    
    def update_widgets(self) -> None:
        if self._acquiring:
            self._btn_clear.setDisabled(True)
            self._btn_start_stop.setText("Stop")
        else:
            self._btn_clear.setEnabled(True)
            self._btn_start_stop.setText("Start")

        if self._chart_has_content:
            self._signal_tree.lock()
        else:
            self._signal_tree.unlock()
        
        if self._chart_has_content and not self._acquiring:
            self._btn_clear.setEnabled(True)
        else:
            self._btn_clear.setDisabled(True)


    def watcher_id(self) -> str:
        return self.instance_name
    
    def report_error(self, msg:str) -> None:
        self._message_label.setText(msg)

    def val_update_callback(self, watcher_id:Union[str, int], vals:List[ValueUpdate]) -> None:
        if not self._chart_has_content:
            self.logger.error("Received value updates when no graph was ready")
            return 
        
        self._xaxis.setRange(self._xaxis.min(), vals[-1].update_timestamp.timestamp())
        try:
            for val in vals:
                series = self._serverid2item[val.watchable.server_id].series()
                floatval = float(val.value)
                yaxis = cast(ScrutinyValueAxis, self._chartview.chart().axisY(series))
                yaxis.setRange(min(yaxis.min(), floatval), max(yaxis.max(), floatval))
                series.append(val.update_timestamp.timestamp(), floatval)
        except KeyError as e:
            tools.log_exception(self.logger, e, "Received a value update from a watchable that maps to no valid series in the chart")
            self.stop_acquisition()
        except Exception as e:
            tools.log_exception(self.logger, e, f"Error when receiving data for the chart")
            self.stop_acquisition()
            
    def unwatch_callback(self, watcher_id:Union[str, int], server_path:str, watchable_config:sdk.WatchableConfiguration) -> None:
        # Should we do something? User feedback if the watcahble is not available anymore maybe?
        pass
    
    def update_emphasize_state(self) -> None:
        emphasized_yaxes_id:Set[int] = set()
        selected_index = self._signal_tree.selectedIndexes()
        for item in self._serverid2item.values():
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

    def selection_changed_slot(self) -> None:
        self.update_emphasize_state()
        
