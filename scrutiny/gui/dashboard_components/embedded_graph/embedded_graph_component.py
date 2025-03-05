#    embedded_graph_component.py
#        A component to configure, trigger, view and browse embedded datalogging.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from typing import Dict, Any

from PySide6.QtWidgets import QVBoxLayout, QLabel, QWidget, QSplitter, QPushButton, QScrollArea, QHBoxLayout
from PySide6.QtCore import Qt

from scrutiny.sdk import EmbeddedDataType
from scrutiny.sdk.datalogging import DataloggingConfig, DataloggingRequest
from scrutiny.sdk.client import ScrutinyClient

from scrutiny.gui import assets
from scrutiny.gui.dashboard_components.embedded_graph.graph_config_widget import GraphConfigWidget
from scrutiny.gui.dashboard_components.common.base_chart import ScrutinyChart, ScrutinyChartView, ScrutinyChartToolBar
from scrutiny.gui.dashboard_components.common.graph_signal_tree import GraphSignalTree
from scrutiny.gui.widgets.feedback_label import FeedbackLabel

from scrutiny.tools.typing import *

class EmbeddedGraph(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("scope-96x128.png")
    _NAME = "Embedded Graph"

    _graph_config_widget:GraphConfigWidget
    _splitter:QSplitter
    _xval_label:QLabel
    _signal_tree:GraphSignalTree
    _btn_start_stop:QPushButton
    _btn_clear:QPushButton
    _feedback_label:FeedbackLabel
    _chartview:ScrutinyChartView
    _chart_toolbar:ScrutinyChartToolBar

    _left_pane:QWidget
    _center_pane:QWidget
    _right_pane:QWidget

    def setup(self) -> None:
        layout = QVBoxLayout(self)
        

        def make_right_pane() -> QWidget:
            right_pane = QWidget()
            right_pane_layout = QVBoxLayout(right_pane)

            self._xval_label = QLabel()

            # Series on continuous graph don't have their X value aligned. 
            # We can only show the value next to each point, not all together in the tree
            self._signal_tree = GraphSignalTree(self, watchable_registry=self.watchable_registry, has_value_col=True)
            #self._signal_tree.signals.selection_changed.connect(self._selection_changed_slot)

            start_pause_line = QWidget()
            start_pause_line_layout = QHBoxLayout(start_pause_line)
            self._btn_start_stop = QPushButton("Start")
            self._btn_start_stop.clicked.connect(self._btn_start_stop_slot)
            self._btn_clear = QPushButton("Clear")
           # self._btn_clear.clicked.connect(self._btn_clear_slot)

            start_pause_line_layout.addWidget(self._btn_start_stop)
            start_pause_line_layout.addWidget(self._btn_clear)
            

            self._feedback_label = FeedbackLabel()
            self._feedback_label.text_label().setWordWrap(True)

            self._xval_label.setVisible(False)
            right_pane_layout.addWidget(self._xval_label)
            right_pane_layout.addWidget(self._signal_tree)
            right_pane_layout.addWidget(start_pause_line)
            right_pane_layout.addWidget(self._feedback_label)

            right_pane_scroll = QScrollArea(self)
            right_pane_scroll.setWidget(right_pane)
            right_pane_scroll.setWidgetResizable(True)
            right_pane_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            right_pane_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            right_pane_scroll.setMinimumWidth(right_pane_scroll.sizeHint().width())

            return right_pane_scroll

        def make_center_pane() -> QWidget:
            chart = ScrutinyChart()
            chart.layout().setContentsMargins(0,0,0,0)
            
            self._chartview = ScrutinyChartView(self)
            self._chartview.setChart(chart)
            #self._chartview.signals.context_menu_event.connect(self._chart_context_menu_slot)
            #self._chartview.signals.zoombox_selected.connect(self._chartview_zoombox_selected_slot)
            #self._chartview.signals.key_pressed.connect(self._chartview_key_pressed_slot)
            self._chartview.set_interaction_mode(ScrutinyChartView.InteractionMode.SELECT_ZOOM)
            self._chart_toolbar = ScrutinyChartToolBar(self._chartview)
            self._chart_toolbar.hide()

            return self._chartview


        def make_left_pane() -> QWidget:
            self._graph_config_widget = GraphConfigWidget(self, 
                                                        watchable_registry=self.watchable_registry,
                                                        get_signal_dtype_fn=self._get_signal_size_list)
            self._update_datalogging_capabilities()

            left_pane_scroll = QScrollArea(self)
            left_pane_scroll.setWidget(self._graph_config_widget)
            left_pane_scroll.setWidgetResizable(True)
            left_pane_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            left_pane_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            left_pane_scroll.setMinimumWidth(left_pane_scroll.sizeHint().width())

            return left_pane_scroll
        
        self._left_pane = make_left_pane()
        self._center_pane = make_center_pane()
        self._right_pane = make_right_pane()

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setContentsMargins(0,0,0,0)
        self._splitter.setHandleWidth(5)
        self._splitter.addWidget(self._left_pane)
        self._splitter.addWidget(self._center_pane)
        self._splitter.addWidget(self._right_pane)
        self._splitter.setCollapsible(0, True)
        self._splitter.setCollapsible(1, False)
        self._splitter.setCollapsible(2, True)

        layout.addWidget(self._splitter)

        self.server_manager.signals.device_info_availability_changed.connect(self._update_datalogging_capabilities)
        self.server_manager.signals.device_disconnected.connect(self._update_datalogging_capabilities)
        self.server_manager.signals.device_ready.connect(self._update_datalogging_capabilities)

        
    def ready(self) -> None:
        """Called when the component is inside the dashboard and its dimensions are computed"""
        # Make the right menu as small as possible. Only works after the widget is loaded. we need the ready() function for that
        self._splitter.setSizes([self._left_pane.minimumWidth(), self.width(), self._right_pane.minimumWidth()])
        

    def teardown(self) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        raise NotImplementedError()

    def load_state(self, state: Dict[Any, Any]) -> None:
        raise NotImplementedError()

    def _update_datalogging_capabilities(self) -> None:
        self._graph_config_widget.configure_from_device_info(self.server_manager.get_device_info())

    def _btn_start_stop_slot(self) -> None:
        result = self._graph_config_widget.validate_and_get_config()
        if not result.valid:
            assert result.error is not None
            self._feedback_label.set_error(result.error)
            return 
        assert result.config is not None
        
        self._feedback_label.clear()
        axes_signal = self._signal_tree.get_signals()
        if len(axes_signal) == 0:
            self._feedback_label.set_error("No signals to acquire")
            return

        nb_signals = 0
        for axis in axes_signal:
            if len(axis.signal_items) == 0:
                continue
            nb_signals += len(axis.signal_items)
            sdk_axis = result.config.add_axis(axis.axis_name)
            for signal_item in axis.signal_items:
                result.config.add_signal(
                    axis=sdk_axis,
                    name=signal_item.text(),
                    signal=self.watchable_registry.FQN.parse(signal_item.fqn).path
                )

        if nb_signals == 0:
            self._feedback_label.set_error("No signals to acquire")
            return
        
        self._acquire(result.config)
        
    
    def _acquire(self, config:DataloggingConfig) -> None:
        
        def ephemerous_thread_start_datalog(client:ScrutinyClient) -> DataloggingRequest:
            return client.start_datalog(config)

        def qt_thread_datalog_started(request:Optional[DataloggingRequest], error:Optional[Exception]) -> None:
            print(request)
            print(error)

        self.server_manager.schedule_client_request(
            user_func=ephemerous_thread_start_datalog,
            ui_thread_callback=qt_thread_datalog_started
        )


    def _get_signal_size_list(self) -> List[EmbeddedDataType]:
        outlist:List[EmbeddedDataType] = []
        axes = self._signal_tree.get_signals()
        for axis in axes:
            for item in axis.signal_items:
                watchable = self.watchable_registry.get_watchable_fqn(item.fqn)  # Might be unavailable
                if watchable is None:
                    return []
                outlist.append(watchable.datatype)

        return outlist
            
