
from PySide6.QtWidgets import QHBoxLayout, QSplitter, QWidget, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCharts import QChart, QChartView
from PySide6.QtCore import Qt

from scrutiny.gui import assets
from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from scrutiny.gui.dashboard_components.common.graph_signal_tree import GraphSignalTree
from scrutiny.gui.core.watchable_registry import WatchableRegistryNodeNotFoundError, ValueUpdate
from scrutiny import sdk

from typing import Dict, Any, Union, List

class ContinuousGraphComponent(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("graph-96x128.png")
    _NAME = "Continuous Graph"

    _chart:QChart
    _chartview:QChartView
    _signal_tree:GraphSignalTree
    _start_stop_btn:QPushButton
    _message_label:QLabel
    _splitter:QSplitter
    _acquiring:bool

    def setup(self) -> None:
        self._acquiring = False
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

        
    def ready(self):
        self._splitter.setSizes([self.width(), self._signal_tree.minimumWidth()])
        self.update_visual()

    def teardown(self) -> None:
        self.watchable_registry.unregister_watcher(self.watcher_id())

    def get_state(self) -> Dict[Any, Any]:
        raise NotImplementedError()

    def load_state(self, state: Dict[Any, Any]) -> None:
        raise NotImplementedError()


    def start_stop_btn_slot(self) -> None:
        if not self._acquiring:
            signals = self._signal_tree.get_signals()
            if len(signals) == 0:
                self.report_error("No signals")
                return
            
            for axis in signals:
                for signal in axis.signals:
                    try:
                        self.watchable_registry.watch_fqn(self.watcher_id(), signal.watchable_fqn)
                    except WatchableRegistryNodeNotFoundError as e:
                        self.report_error(f"Signal {signal.name} ({signal.watchable_fqn}) is not available.")
                        self.watchable_registry.unwatch_all(self.watcher_id())
                        return
            
            self._acquiring = True
            
        else:
            self.watchable_registry.unwatch_all(self.watcher_id())
            self._acquiring = False

        self.update_visual()
    
    def update_visual(self) -> None:
        if self._acquiring:
            self._start_stop_btn.setText("Stop")
        else:
            self._start_stop_btn.setText("Start")

    def watcher_id(self) -> str:
        return self.instance_name
    
    def report_error(self, msg:str) -> None:
        self._message_label.setText(msg)

    def val_update_callback(self, watcher_id:Union[str, int], vals:List[ValueUpdate]) -> None:
        print(f"Updates: {len(vals)}")

    def unwatch_callback(self, watcher_id:Union[str, int], server_path:str, watchable_config:sdk.WatchableConfiguration) -> None:
        pass
