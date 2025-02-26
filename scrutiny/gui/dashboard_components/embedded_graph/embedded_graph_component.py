#    embedded_graph_component.py
#        A componenbt to configure, trigger, view and browse embedded datalogging.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from typing import Dict, Any

from PySide6.QtWidgets import QVBoxLayout, QLabel, QWidget, QSplitter,  QPushButton
from PySide6.QtCore import Qt

from scrutiny.gui import assets
from scrutiny.gui.dashboard_components.embedded_graph.graph_config import GraphConfigWidget
from scrutiny.gui.dashboard_components.common.base_chart import GraphSignalTree, ScrutinyChart, ScrutinyChartView, ScrutinyChartToolBar
from scrutiny.gui.widgets.feedback_label import FeedbackLabel

class EmbeddedGraph(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("scope-96x128.png")
    _NAME = "Embedded Graph"


    _xval_label:QLabel
    _signal_tree:GraphSignalTree
    _btn_start_stop:QPushButton
    _btn_clear:QPushButton
    _feedback_label:FeedbackLabel
    _chartview:ScrutinyChartView
    _chart_toolbar:ScrutinyChartToolBar

    def setup(self) -> None:
        layout = QVBoxLayout(self)
        
        
        def make_left_side() -> QWidget:
            chart = ScrutinyChart()
            chart.layout().setContentsMargins(0,0,0,0)
            
            self._chartview = ScrutinyChartView(self)
            self._chartview.setChart(chart)
            #self._chartview.signals.context_menu_event.connect(self._chart_context_menu_slot)
            #self._chartview.signals.zoombox_selected.connect(self._chartview_zoombox_selected_slot)
            #self._chartview.signals.key_pressed.connect(self._chartview_key_pressed_slot)
            self._chartview.set_interaction_mode(ScrutinyChartView.InteractionMode.SELECT_ZOOM)

            self._chart_toolbar = ScrutinyChartToolBar(self._chartview) 

            left_side = QWidget()
            left_side_layout = QVBoxLayout(left_side)
            left_side_layout.setContentsMargins(0,0,0,0)
            left_side_layout.addWidget(self._chartview)
            return left_side

        def make_right_side() -> QWidget:
            right_side = QWidget()
            right_side_layout = QVBoxLayout(right_side)

            self._xval_label = QLabel()

            # Series on continuous graph don't have their X value aligned. 
            # We can only show the value next to each point, not all together in the tree
            self._signal_tree = GraphSignalTree(self, watchable_registry=self.watchable_registry, has_value_col=True)
            self._signal_tree.setMinimumWidth(200)
            #self._signal_tree.signals.selection_changed.connect(self._selection_changed_slot)

            self._btn_start_stop = QPushButton("")
           # self._btn_start_stop.clicked.connect(self._btn_start_stop_slot)
            self._btn_clear = QPushButton("Clear")
           # self._btn_clear.clicked.connect(self._btn_clear_slot)
            

            self._feedback_label = FeedbackLabel()
            self._feedback_label.text_label().setWordWrap(True)

            self._xval_label.setVisible(False)
            right_side_layout.addWidget(self._xval_label)
            right_side_layout.addWidget(self._signal_tree)
            right_side_layout.addWidget(self._btn_start_stop)
            right_side_layout.addWidget(self._btn_clear)
            right_side_layout.addWidget(self._feedback_label)

            return right_side

        
        left_side = make_left_side()
        right_side = make_right_side()
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setContentsMargins(0,0,0,0)
        splitter.setHandleWidth(5)
        splitter.addWidget(left_side)
        splitter.addWidget(GraphConfigWidget(self))
        splitter.addWidget(right_side)
        splitter.setCollapsible(0, False) # Cannot collapse the graph
        splitter.setCollapsible(1, True)  # Can collapse the right menu


        layout.addWidget(splitter)
        
    def ready(self) -> None:
        """Called when the component is inside the dashboard and its dimensions are computed"""
        # Make the right menu as small as possible. Only works after the widget is loaded. we need the ready() function for that
       # self._splitter.setSizes([self.width(), self._signal_tree.minimumWidth()])
        pass

    def teardown(self) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        raise NotImplementedError()

    def load_state(self, state: Dict[Any, Any]) -> None:
        raise NotImplementedError()
