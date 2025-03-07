#    embedded_graph_component.py
#        A component to configure, trigger, view and browse embedded datalogging.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from dataclasses import dataclass
from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from typing import Dict, Any

from PySide6.QtWidgets import QVBoxLayout, QLabel, QWidget, QSplitter, QPushButton, QScrollArea, QHBoxLayout
from PySide6.QtCore import Qt, QPointF, QRectF

from scrutiny.sdk import EmbeddedDataType
from scrutiny.sdk.datalogging import DataloggingConfig, DataloggingRequest, DataloggingAcquisition
from scrutiny.sdk.client import ScrutinyClient

from scrutiny.gui import assets
from scrutiny.gui.dashboard_components.embedded_graph.graph_config_widget import GraphConfigWidget
from scrutiny.gui.dashboard_components.common.base_chart import (
    ScrutinyChart, ScrutinyChartView, ScrutinyChartToolBar, ScrutinyValueAxis, ScrutinyLineSeries, ScrutinyValueAxisWithMinMax
    )
from scrutiny.gui.dashboard_components.common.graph_signal_tree import GraphSignalTree, ChartSeriesWatchableStandardItem, AxisStandardItem
from scrutiny.gui.widgets.feedback_label import FeedbackLabel

from scrutiny.tools.typing import *
from scrutiny import tools

@dataclass
class EmbeddedGraphState:
    has_content:bool
    waiting_on_graph:bool
    chart_toolbar_wanted:bool

    def allow_save_csv(self) -> bool:
        return self.has_content

    def allow_save_image(self) -> bool:
        return self.has_content

    def allow_zoom(self) -> bool:
        return self.has_content

    def allow_drag(self) -> bool:
        return self.has_content

    def must_lock_signal_tree(self) -> bool:
        return self.has_content or self.waiting_on_graph

    def enable_clear_button(self) -> bool:
        return self.has_content

    def enable_startstop_button(self) -> bool:
        return True

    def can_display_toolbar(self) -> bool:
        return self.has_content
    
    def enable_reset_zoom_button(self) -> bool:
        return self.has_content
    
    def must_display_toolbar(self) -> bool:
        return self.can_display_toolbar() and self.chart_toolbar_wanted


class EmbeddedGraph(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("scope-96x128.png")
    _NAME = "Embedded Graph"

    _graph_config_widget:GraphConfigWidget
    _splitter:QSplitter
    _xval_label:QLabel
    _signal_tree:GraphSignalTree
    _btn_acquire:QPushButton
    _btn_clear:QPushButton
    _feedback_label:FeedbackLabel
    _chartview:ScrutinyChartView
    _chart_toolbar:ScrutinyChartToolBar
    _xaxis:Optional[ScrutinyValueAxisWithMinMax]
    _yaxes:List[ScrutinyValueAxisWithMinMax]

    _left_pane:QWidget
    _center_pane:QWidget
    _right_pane:QWidget

    _state:EmbeddedGraphState

    def setup(self) -> None:
        layout = QVBoxLayout(self)
        self._state = EmbeddedGraphState(
            has_content=False,
            waiting_on_graph=False,
            chart_toolbar_wanted=True
        )
        

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
            self._btn_acquire = QPushButton("Acquire")
            self._btn_acquire.clicked.connect(self._btn_acquire_slot)
            self._btn_clear = QPushButton("Clear")
            self._btn_clear.clicked.connect(self._btn_clear_slot)

            start_pause_line_layout.addWidget(self._btn_acquire)
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
            self._xaxis = None
            self._yaxes = []
            #self._chartview.signals.context_menu_event.connect(self._chart_context_menu_slot)
            self._chartview.signals.zoombox_selected.connect(self._chartview_zoombox_selected_slot)
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

        self._apply_internal_state()

        
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
    
    def _apply_internal_state(self) -> None:
        """Update all the widgets based on our internal state variables"""
        self._btn_acquire.setEnabled(self._state.enable_startstop_button())
        self._btn_clear.setEnabled(self._state.enable_clear_button())
        self._chartview.allow_zoom(self._state.allow_zoom())
        self._chartview.allow_drag(self._state.allow_drag())

        if self._state.must_lock_signal_tree():
            self._signal_tree.lock()
        else:
            self._signal_tree.unlock()

        if self._state.must_display_toolbar():
            self._chart_toolbar.show()
        else:
            self._chart_toolbar.hide()

    def _update_datalogging_capabilities(self) -> None:
        self._graph_config_widget.configure_from_device_info(self.server_manager.get_device_info())

    def _btn_acquire_slot(self) -> None:
        """When the user pressed "Acquire" """
        # Get the config from the config widget. 
        # Then add the signals from the signal tree and send that to the server if all valid
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

        # Config is good. 
        self._feedback_label.clear()
        self._clear_graph()
        self._state.waiting_on_graph = True
        self._apply_internal_state()
        self._acquire(result.config)    # Request the server for that acquisition
        
    
    def _acquire(self, config:DataloggingConfig) -> None:
        # We chain 2 background request. 1 for the initial request, 2 to wait for completion.
        # Promises could be nice here, we don't have that.

        def bg_thread_start_datalog(client:ScrutinyClient) -> DataloggingRequest:
            return client.start_datalog(config)

        def qt_thread_datalog_started(request:Optional[DataloggingRequest], error:Optional[Exception]) -> None:
            # Callbak #1. The request is received and aknowledged by the server
            if error is not None:
                self._callback_request_failed(request=None, error=error)
                return
            assert request is not None

            # We have a pending request. Launch a background task to wait for completion.
            def bg_thread_wait_for_completion(client:ScrutinyClient) -> None:
                request.wait_for_completion()
            
            def qt_thread_request_completed(_:None, error:Optional[Exception]) -> None:
                # Callback #2. The acquisition is completed (success or failed)

                if error is not None:   # Exception while waiting
                    self._callback_request_failed(request, error)
                    return

                if not request.completed:   # Should not happen. Happens only when there is a timeout on wait_for_completion (we don't have one)
                    self._callback_request_failed(request, None, "Failed to complete")
                    return

                if not request.is_success:  # Didn't complete. The device or the server might be gone while waiting
                    self._callback_request_failed(request, None, request.failure_reason)
                    return
                
                self._callback_request_succeeded(request)   # SUCCESS!
            
            self.server_manager.schedule_client_request(
                user_func=bg_thread_wait_for_completion,
                ui_thread_callback=qt_thread_request_completed
            )

            self._feedback_label.set_info("Wating for trigger")
        
        self.server_manager.schedule_client_request(
            user_func= bg_thread_start_datalog,
            ui_thread_callback=qt_thread_datalog_started
        )

        self._feedback_label.set_info("Acquisition requested")


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
            

    def _callback_request_failed(self, request:Optional[DataloggingRequest], error:Optional[Exception], msg:str="Request failed") -> None:
        self._state.waiting_on_graph = False
        self._feedback_label.clear()

        if error:
            tools.log_exception(self.logger, error, msg)
        elif len(msg) > 0:
            self.logger.error(msg)

        feedback_str = msg
        if error:
            feedback_str += f" {error}"

        self._display_graph_error(feedback_str)
        self._apply_internal_state()

    def _callback_request_succeeded(self, request:DataloggingRequest) -> None:
        assert request.completed and request.is_success
        assert request.acquisition_reference_id is not None
        self._feedback_label.clear()

        self._apply_internal_state()

        def ephemerous_thread_download_data(client:ScrutinyClient) -> DataloggingAcquisition:
            assert request.acquisition_reference_id is not None
            return client.read_datalogging_acquisition(reference_id=request.acquisition_reference_id)
        
        def qt_thread_receive_acquisition_data(acquisition:Optional[DataloggingAcquisition], error:Optional[Exception]) -> None:
            if error is not None:
                self._callback_request_failed(request, error,  f"The acquisition succeeded, but downloading its data failed. The content is still available in the server database.\n Error {error}")
                return 

            assert acquisition is not None
            self._display_acquisition(acquisition)
            self._state.waiting_on_graph = False
            self._state.has_content = True
            self._apply_internal_state()

        self.server_manager.schedule_client_request(
            user_func=ephemerous_thread_download_data, 
            ui_thread_callback=qt_thread_receive_acquisition_data
            )

    def _btn_clear_slot(self) -> None:
        self._clear_graph()
        self._feedback_label.clear()


    def _clear_graph(self) -> None:
        self._chart_toolbar.hide()
        chart = self._chartview.chart()
        chart.removeAllSeries()
        if self._xaxis is not None:
            chart.removeAxis(self._xaxis)
        for yaxis in self._yaxes:
            chart.removeAxis(yaxis)
        
        self._xaxis=None
        self._yaxes.clear()
        
        self._state.has_content = False
        self._apply_internal_state()

    def _display_graph_error(self, message:str) -> None:
        # TODO : Big sad face and a message
        self._clear_graph()

    def _display_acquisition(self, acquisition:DataloggingAcquisition) -> None:
        self._clear_graph()
        signal_tree_model = self._signal_tree.model()
        signal_tree_model.clear()

        chart = self._chartview.chart()
        self._chart_toolbar.show()
        
        self._xaxis = ScrutinyValueAxisWithMinMax(chart)        
        self._xaxis.setTitleText(acquisition.xdata.name)
        self._xaxis.setTitleVisible(True)
        chart.setAxisX(self._xaxis)

        sdk_yaxes = acquisition.get_unique_yaxis_list()
        sdk2qt_axes:Dict[int, ScrutinyValueAxisWithMinMax] = {}
        sdk2tree_axes:Dict[int, AxisStandardItem] = {}
        for sdk_yaxis in sdk_yaxes:
            # Create the axis in the signal tree (right menu)
            axis_item = signal_tree_model.add_axis(sdk_yaxis.name)
            sdk2tree_axes[sdk_yaxis.axis_id] = axis_item
            # Create the axis in the graph
            qt_axis = ScrutinyValueAxisWithMinMax(chart)
            qt_axis.setTitleText(sdk_yaxis.name)
            qt_axis.setTitleVisible(True)
            sdk2qt_axes[sdk_yaxis.axis_id] = qt_axis
            chart.addAxis(qt_axis, Qt.AlignmentFlag.AlignRight)
            
            # Bind the graph axis with the signal tree axis.
            axis_item.attach_axis(qt_axis)
            self._yaxes.append(qt_axis) # Keeps all the references in a lsit for convenience.
    

        
        xseries_data = acquisition.xdata.get_data()
        for ydata in acquisition.ydata:     # For each dataset
            # Find the axis tied to that dataset
            qt_yaxis = sdk2qt_axes[ydata.axis.axis_id]
            axis_item = sdk2tree_axes[ydata.axis.axis_id]
            
            assert ydata.series.logged_watchable is not None
            wpath = ydata.series.logged_watchable.path
            wtype = ydata.series.logged_watchable.type
            series_item = ChartSeriesWatchableStandardItem(
                fqn=self.watchable_registry.FQN.make(watchable_type=wtype, path=wpath),
                watchable_type=wtype,
                text=ydata.series.name
            )

            series = ScrutinyLineSeries(chart)
            chart.addSeries(series)
            yseries_data = ydata.series.get_data()
            assert len(xseries_data) == len(yseries_data)
            
            qt_pointf_data = [QPointF(xseries_data[i], yseries_data[i]) for i in range(len(xseries_data))]
            series.replace(qt_pointf_data)
            series.attachAxis(self._xaxis)
            series.attachAxis(qt_yaxis)
            series.setName(ydata.series.name)
            
            qt_yaxis.update_minmax(min(yseries_data))
            qt_yaxis.update_minmax(max(yseries_data))
        
        self._xaxis.set_minval(min(xseries_data))
        self._xaxis.set_maxval(max(xseries_data))

        self._xaxis.autoset_range()
        for yaxis in self._yaxes:
            yaxis.autoset_range()


    def _chartview_zoombox_selected_slot(self, zoombox:QRectF) -> None:
        if not self._state.allow_zoom():
            return 
        #self._chartview.chart().hide_mouse_callout()

        # When we are paused, we want the zoom to stay within the range of that was latched when pause was called.
        # When not pause, saturate to min/max values
        assert self._xaxis is not None
        self._xaxis.apply_zoombox_x(zoombox)
        selected_axis_items = self._signal_tree.get_selected_axes(include_if_signal_is_selected=True)
        selected_axis_ids = [id(item.axis()) for item in selected_axis_items]
        for yaxis in self._yaxes:
            if id(yaxis) in selected_axis_ids or len(selected_axis_ids) == 0:
                # Y-axis is not bound by the value. we leave the freedom to the user to unzoom like crazy
                # We rely on the capacity to reset the zoom to come back to something reasonable if the user gets lost
                yaxis.apply_zoombox_y(zoombox)  
        self._chartview.update()
