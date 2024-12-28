#    continuous_graph_component.py
#        A component that makes a real time graphs of the values streamed by the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from datetime import datetime

from PySide6.QtWidgets import QHBoxLayout, QSplitter, QWidget, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis, QDateTimeAxis
from PySide6.QtCore import Qt

from scrutiny.gui import assets
from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from scrutiny.gui.dashboard_components.common.graph_signal_tree import GraphSignalTree
from scrutiny.gui.core.watchable_registry import WatchableRegistryNodeNotFoundError, ValueUpdate
from scrutiny import sdk
from scrutiny.tools import SuppressException

from typing import Dict, Any, Union, List, Optional, cast

class ContinuousGraphComponent(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("graph-96x128.png")
    _NAME = "Continuous Graph"

    _chartview:QChartView
    _signal_tree:GraphSignalTree
    _start_stop_btn:QPushButton
    _message_label:QLabel
    _splitter:QSplitter
    _acquiring:bool
    _serverid2series_map:Dict[str, QLineSeries]

    _xaxis:Optional[QValueAxis]
    _yaxis:Optional[List[QValueAxis]]

    def setup(self) -> None:
        self._acquiring = False
        self._serverid2series_map = {}
        self._xaxis = None
        self._yaxis = None
        self.watchable_registry.register_watcher(self.instance_name, self.val_update_callback, self.unwatch_callback)
        
        self._splitter = QSplitter(self)
        self._splitter.setOrientation(Qt.Orientation.Horizontal)
        self._splitter.setContentsMargins(0,0,0,0)
        self._splitter.setHandleWidth(5)
        

        self._chartview = QChartView(self)
        self._chartview.setChart(QChart())
        self._chartview.chart().layout().setContentsMargins(0,0,0,0)
        
        right_side = QWidget()
        right_side_layout = QVBoxLayout(right_side)
        
        self._signal_tree = GraphSignalTree(self)
        self._signal_tree.setMinimumWidth(150)
        self._start_stop_btn = QPushButton("")
        self._start_stop_btn.clicked.connect(self.start_stop_btn_slot)
        self._message_label = QLabel()
        right_side_layout.addWidget(self._signal_tree)
        right_side_layout.addWidget(self._start_stop_btn)
        right_side_layout.addWidget(self._message_label)


        self._splitter.addWidget(self._chartview)
        self._splitter.addWidget(right_side)
        self._splitter.setCollapsible(0, False)
        self._splitter.setCollapsible(1, True)

        layout = QHBoxLayout(self)
        layout.addWidget(self._splitter)

        
    def ready(self) -> None:
        self._splitter.setSizes([self.width(), self._signal_tree.minimumWidth()])
        self.update_visual()

    def teardown(self) -> None:
        self.watchable_registry.unregister_watcher(self.watcher_id())

    def get_state(self) -> Dict[Any, Any]:
        raise NotImplementedError()

    def load_state(self, state: Dict[Any, Any]) -> None:
        raise NotImplementedError()

    def clear_graph(self) -> None:
        self._chartview.chart().removeAllSeries()
        if self._xaxis is not None:
            with SuppressException():
                self._chartview.chart().removeAxis(self._xaxis)
        
        if self._yaxis is not None:
            for yaxis in self._yaxis:
                with SuppressException():
                    self._chartview.chart().removeAxis(yaxis)

        self._serverid2series_map.clear()
        self._xaxis = None
        self._yaxis = None
    
    def stop_acquisition(self) -> None:
        if not self._acquiring:
            return 

        self.watchable_registry.unwatch_all(self.watcher_id())
        self._acquiring = False
        self.update_visual()

    def start_acquisition(self) -> None:
        if self._acquiring:
            return 
        self.clear_graph()
        signals = self._signal_tree.get_signals()
        if len(signals) == 0:
            self.report_error("No signals")
            return
        
        self._xaxis = QValueAxis(self)
        self._xaxis.setRange(datetime.now().timestamp(), datetime.now().timestamp() + 30)
        self._chartview.chart().addAxis(self._xaxis, Qt.AlignmentFlag.AlignBottom)
        self._yaxis = []
        for axis in signals:
            yaxis = QValueAxis(self)
            yaxis.setTitleText(axis.axis_name)
            yaxis.setTitleVisible(True)
            self._yaxis.append(yaxis)
            self._chartview.chart().addAxis(yaxis, Qt.AlignmentFlag.AlignRight)
            
            for signal in axis.signals:
                try:
                    server_id = self.watchable_registry.watch_fqn(self.watcher_id(), signal.watchable_fqn)
                except WatchableRegistryNodeNotFoundError as e:
                    self.report_error(f"Signal {signal.name} ({signal.watchable_fqn}) is not available.")
                    self.watchable_registry.unwatch_all(self.watcher_id())
                    self.clear_graph()
                    return
        
                series = QLineSeries(self)
                self._chartview.chart().addSeries(series)
                self._serverid2series_map[server_id] = series
                series.setName(signal.name)
                series.attachAxis(self._xaxis)
                series.attachAxis(yaxis)

        self._acquiring = True
        self.update_visual()
        

    def start_stop_btn_slot(self) -> None:
        if self._acquiring:           
            self.stop_acquisition()
        else:
            self.start_acquisition()
    
    def update_visual(self) -> None:
        if self._acquiring:
            self._start_stop_btn.setText("Stop")
            self._signal_tree.lock()
        else:
            self._start_stop_btn.setText("Start")
            self._signal_tree.unlock()

    def watcher_id(self) -> str:
        return self.instance_name
    
    def report_error(self, msg:str) -> None:
        self._message_label.setText(msg)

    def val_update_callback(self, watcher_id:Union[str, int], vals:List[ValueUpdate]) -> None:
        if self._xaxis is None or self._yaxis is None:
            self.logger.error("Received value updates when no graph was ready")
            return 
        
        self._xaxis.setRange(self._xaxis.min(), vals[-1].update_timestamp.timestamp())
        for val in vals:
            floatval = float(val.value)
            series = self._serverid2series_map[val.watchable.server_id]
            yaxis = cast(QValueAxis, self._chartview.chart().axisY(series))
            yaxis.setRange(min(yaxis.min(), floatval), max(yaxis.max(), floatval))
            series.append(val.update_timestamp.timestamp(), floatval)
            
    def unwatch_callback(self, watcher_id:Union[str, int], server_path:str, watchable_config:sdk.WatchableConfiguration) -> None:
        pass
