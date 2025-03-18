#    embedded_graph_component.py
#        A component to configure, trigger, view and browse embedded datalogging.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from dataclasses import dataclass
from pathlib import Path
from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from typing import Dict, Any

from PySide6.QtWidgets import QVBoxLayout, QLabel, QWidget, QSplitter, QPushButton, QScrollArea, QHBoxLayout, QMenu
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QContextMenuEvent, QKeyEvent, QResizeEvent


from scrutiny import sdk
from scrutiny.sdk import EmbeddedDataType
from scrutiny.sdk.datalogging import DataloggingConfig, DataloggingRequest, DataloggingAcquisition, XAxisType, FixedFreqSamplingRate, DataloggerState
from scrutiny.sdk.client import ScrutinyClient

from scrutiny.gui import assets
from scrutiny.gui.tools import prompt
from scrutiny.gui.dashboard_components.embedded_graph.graph_config_widget import GraphConfigWidget
from scrutiny.gui.dashboard_components.embedded_graph.chart_status_overlay import ChartStatusOverlay
from scrutiny.gui.dashboard_components.common.base_chart import (
    ScrutinyChart, ScrutinyChartView, ScrutinyChartToolBar,  ScrutinyLineSeries, ScrutinyValueAxisWithMinMax
    )
from scrutiny.gui.dashboard_components.common.graph_signal_tree import GraphSignalTree, ChartSeriesWatchableStandardItem, AxisStandardItem
from scrutiny.gui.widgets.feedback_label import FeedbackLabel

from scrutiny import tools
from scrutiny.tools.typing import *
from scrutiny.gui.tools.invoker import InvokeInQtThread
from scrutiny.gui.dashboard_components.common.export_chart_csv import export_chart_csv_threaded


@dataclass
class EmbeddedGraphState:
    has_content:bool
    waiting_on_graph:bool
    chart_toolbar_wanted:bool
    has_failure_message:bool

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
    
    def must_force_signal_tree_element_available(self) -> bool:
        return self.has_content
    
    def must_show_overlay(self) -> bool:
        return self.waiting_on_graph or self.has_failure_message

    def enable_clear_button(self) -> bool:
        return self.has_content or self.has_failure_message

    def enable_acquire_button(self) -> bool:
        return True

    def can_display_toolbar(self) -> bool:
        return self.has_content
    
    def enable_reset_zoom_button(self) -> bool:
        return self.has_content
    
    def must_display_toolbar(self) -> bool:
        return self.can_display_toolbar() and self.chart_toolbar_wanted and self.has_content
    
    def hide_chart_toolbar(self) -> None:
        self.chart_toolbar_wanted = False
    
    def allow_chart_toolbar(self) -> None:
        self.chart_toolbar_wanted = True

class EmbeddedGraph(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("scope-96x128.png")
    _NAME = "Embedded Graph"

    Y_AXIS_MARGIN = 0.02

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
    _displayed_acquisition:Optional[DataloggingAcquisition]
    _chart_status_overlay:ChartStatusOverlay
    _pending_request:Optional[DataloggingRequest]
    _request_to_ignore_completions:Dict[int, DataloggingRequest]

    _left_pane:QWidget
    _center_pane:QWidget
    _right_pane:QWidget

    _state:EmbeddedGraphState

    def setup(self) -> None:
        layout = QVBoxLayout(self)
        margins = layout.contentsMargins()
        margins.setLeft(0)
        margins.setRight(0)
        layout.setContentsMargins(margins)
        self._state = EmbeddedGraphState(
            has_content=False,
            waiting_on_graph=False,
            chart_toolbar_wanted=True,
            has_failure_message=False
        )

        self._teared_down = False
        self._displayed_acquisition = None
        self._pending_request = None
        self._request_to_ignore_completions = {}

        def make_right_pane() -> QWidget:
            right_pane = QWidget()
            right_pane_layout = QVBoxLayout(right_pane)
            right_pane_layout.setContentsMargins(0,0,0,0)

            self._xval_label = QLabel()

            # Series on continuous graph don't have their X value aligned. 
            # We can only show the value next to each point, not all together in the tree
            self._signal_tree = GraphSignalTree(self, watchable_registry=self.watchable_registry, has_value_col=True)
            self._signal_tree.signals.selection_changed.connect(self._signal_tree_selection_changed_slot)
            self._signal_tree.signals.content_changed.connect(self._signal_tree_content_changed_slot)

            self._xval_label.setVisible(False)
            right_pane_layout.addWidget(self._xval_label)
            right_pane_layout.addWidget(self._signal_tree)

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
            self._chartview.signals.context_menu_event.connect(self._chart_context_menu_slot)
            self._chartview.signals.zoombox_selected.connect(self._chartview_zoombox_selected_slot)
            self._chartview.signals.key_pressed.connect(self._chartview_key_pressed_slot)
            self._chartview.signals.resized.connect(self._chartview_resized_slot)
            self._chartview.set_interaction_mode(ScrutinyChartView.InteractionMode.SELECT_ZOOM)
            self._chart_toolbar = ScrutinyChartToolBar(self._chartview)
            self._chart_toolbar.hide()

            self._chart_status_overlay = ChartStatusOverlay(chart)
            self._chart_status_overlay.hide()

            return self._chartview

        def make_left_pane() -> QWidget:
            self._graph_config_widget = GraphConfigWidget(self, 
                                                        watchable_registry=self.watchable_registry,
                                                        get_signal_dtype_fn=self._get_signal_size_list)

            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            container_layout.setContentsMargins(0,0,0,0)
            
            start_pause_line = QWidget()
            start_pause_line_layout = QHBoxLayout(start_pause_line)
            self._btn_acquire = QPushButton("Acquire")
            self._btn_acquire.clicked.connect(self._btn_acquire_slot)
            self._btn_clear = QPushButton("Clear")
            self._btn_clear.clicked.connect(self._btn_clear_slot)

            start_pause_line_layout.addWidget(self._btn_clear)
            start_pause_line_layout.addWidget(self._btn_acquire)

            self._feedback_label = FeedbackLabel()

            container_layout.addWidget(self._graph_config_widget)
            container_layout.addWidget(start_pause_line)
            container_layout.addWidget(self._feedback_label)
            
            left_pane_scroll = QScrollArea(self)
            left_pane_scroll.setWidget(container)
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
        self.server_manager.signals.registry_changed.connect(self._registry_changed_slot)
        self.server_manager.signals.datalogging_state_changed.connect(self._datalogging_state_changed_slot)
        self._update_datalogging_capabilities()

        self._graph_config_widget.set_axis_type(XAxisType.MeasuredTime)
        rate = self._graph_config_widget.get_selected_sampling_rate()
        if rate is not None and isinstance(rate, FixedFreqSamplingRate):
            self._graph_config_widget.set_axis_type(XAxisType.IdealTime)

        self._apply_internal_state()

        
    def ready(self) -> None:
        """Called when the component is inside the dashboard and its dimensions are computed"""
        # Make the right menu as small as possible. Only works after the widget is loaded. we need the ready() function for that
        self._splitter.setSizes([self._left_pane.minimumWidth(), self.width(), self._right_pane.minimumWidth()])
        

    def teardown(self) -> None:
        self._teared_down = True

    def get_state(self) -> Dict[Any, Any]:
        raise NotImplementedError()

    def load_state(self, state: Dict[Any, Any]) -> None:
        raise NotImplementedError()
    
    def _apply_internal_state(self) -> None:
        """Update all the widgets based on our internal state variables"""
        self._btn_acquire.setEnabled(self._state.enable_acquire_button())
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
        
        if self._state.must_force_signal_tree_element_available():
            self._signal_tree.set_all_available()
        else:
            self._signal_tree.update_all_availabilities()
        
        self._chart_status_overlay.setVisible(self._state.must_show_overlay())

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
        self._acquire(result.config)    # Request the server for that acquisition
        
    def _acquire(self, config:DataloggingConfig) -> None:
        # We chain 2 background request. 1 for the initial request, 2 to wait for completion.
        # Promises could be nice here, we don't have that.

        self._state.waiting_on_graph = True
        self._chart_status_overlay.set(assets.Icons.Trigger, "Configuring")
        self._apply_internal_state()

        self.logger.debug(f"Requesting datalog for config {config}")

        def bg_thread_start_datalog(client:ScrutinyClient) -> DataloggingRequest:
            return client.start_datalog(config)

        def qt_thread_datalog_started(request:Optional[DataloggingRequest], error:Optional[Exception]) -> None:
            # Callbak #1. The request is received and aknowledged by the server

            if self._teared_down:
                return  # Silent exit

            if error is not None:
                self._callback_request_failed(request=None, error=error, msg="")
                return
            assert request is not None

            self.logger.debug(f"Datalog accepted. Request {request.request_token}")

            if self._pending_request is not None:
                # We use a dict instead of a set of id to keep a reference to the object so it's kept alive and ther eis no id reuse issue.
                self._request_to_ignore_completions[id(self._pending_request)] = self._pending_request
            else:
                self._request_to_ignore_completions.clear()

            self._chart_status_overlay.set(assets.Icons.Trigger, "Waiting for trigger...")

            # We have a pending request. Launch a background task to wait for completion.
            def bg_thread_wait_for_completion(client:ScrutinyClient) -> None:
                request.wait_for_completion()
            
            def qt_thread_request_completed(_:None, error:Optional[Exception]) -> None:
                # Callback #2. The acquisition is completed (success or failed)

                if self._teared_down:
                    return # Silent exit
                
                self.logger.debug(f"Request {request.request_token} completed")
                if id(request) in self._request_to_ignore_completions:
                    del self._request_to_ignore_completions[id(request)]
                    self.logger.debug(f"Ignoring completion of {request.request_token}")
                    return 
                
                self._pending_request = None
                if error is not None:   # Exception while waiting
                    self._callback_request_failed(request, error, msg="")   # The message will be the exception
                    return

                if not request.completed:   # Should not happen. Happens only when there is a timeout on wait_for_completion (we don't have one)
                    self._callback_request_failed(request, None, "Failed to complete")
                    return

                if not request.is_success:  # Didn't complete. The device or the server might be gone while waiting
                    self._callback_request_failed(request, None, request.failure_reason)
                    return
                
                self._callback_request_succeeded(request)   # SUCCESS!
            
            self._pending_request = request
            
            self.server_manager.schedule_client_request(
                user_func=bg_thread_wait_for_completion,
                ui_thread_callback=qt_thread_request_completed
            )

            self._feedback_label.clear()
            self._apply_internal_state()
        
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
            
    def _registry_changed_slot(self) -> None:
        """Called when the server manager has finished making a change to the registry"""
        if not self._state.has_content: # We are not inspecting data.
            self._signal_tree.update_all_availabilities()

    def _datalogging_state_changed_slot(self) -> None:
        self._update_acquiring_overlay()

    def _update_acquiring_overlay(self) -> None:
        info = self.server_manager.get_server_info()
        if info is None:
            return 
        if self._state.waiting_on_graph:
            if info.datalogging.state == DataloggerState.Standby:
                self._chart_status_overlay.set(None, "")
            elif info.datalogging.state == DataloggerState.WaitForTrigger:
                self._chart_status_overlay.set(assets.Icons.Trigger, "Waiting for trigger...")
            elif info.datalogging.state == DataloggerState.Acquiring:
                s = "Acquiring"
                ratio = info.datalogging.completion_ratio
                if ratio is not None:
                    percent = int(round(max(min(ratio, 1), 0) * 100)) 
                    s += f" ({int(percent)}%)"
                self._chart_status_overlay.set(assets.Icons.Trigger, s)

    def _callback_request_failed(self, 
                                 request:Optional[DataloggingRequest], 
                                 error:Optional[Exception], 
                                 msg:str="Request failed") -> None:
        self._state.waiting_on_graph = False
        self._feedback_label.clear()

        if error:
            tools.log_exception(self.logger, error, msg)
        elif len(msg) > 0:
            self.logger.error(msg)

        feedback_str = msg
        if error:
            feedback_str += f"\n{error}"
        feedback_str = feedback_str.strip()

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

        self.server_manager.schedule_client_request(
            user_func=ephemerous_thread_download_data, 
            ui_thread_callback=qt_thread_receive_acquisition_data
            )

    def _btn_clear_slot(self) -> None:
        self._clear_graph()
        self._feedback_label.clear()


    def _clear_graph(self) -> None:
        self._clear_graph_error()
        self._chart_toolbar.disable_chart_cursor()
        chart = self._chartview.chart()

        # Unbind the signal tree to the chart
        axes_content = self._signal_tree.get_signals()
        for axis_item in axes_content:
            if axis_item.axis_item.axis_attached():
                axis_item.axis_item.detach_axis()
            for signal_item in axis_item.signal_items:
                if signal_item.series_attached():
                    signal_item.detach_series()

        # Clear the graph content
        chart.removeAllSeries()
        if self._xaxis is not None:
            chart.removeAxis(self._xaxis)
        for yaxis in self._yaxes:
            chart.removeAxis(yaxis)


        # Update internal variables
        self._xaxis=None
        self._yaxes.clear()
        
        self._signal_tree.unlock()
        self._state.has_content = False
        self._displayed_acquisition = None
        self._apply_internal_state()

    def _display_graph_error(self, message:str) -> None:
        self._clear_graph()
        self._chart_status_overlay.set(assets.Icons.Error, message)
        self._state.has_failure_message = True
        self._apply_internal_state()

    def _clear_graph_error(self) -> None:
        self._chart_status_overlay.set(None, "")
        self._state.has_failure_message = False
        self._apply_internal_state()

    def _display_acquisition(self, acquisition:DataloggingAcquisition) -> None:
        self._clear_graph()
        self._chart_status_overlay.set(None, "")
        self._chart_status_overlay.hide()
        self._state.has_failure_message = False
        self._state.waiting_on_graph = False
        self._state.has_content = True
        

        # Todo, we could reload a SFD when downloading an acquisiton from a different SFD
        self._displayed_acquisition = acquisition

        signal_tree_model = self._signal_tree.model()
        signal_tree_model.removeRows(0, signal_tree_model.rowCount())

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
            series = ScrutinyLineSeries(chart)
            chart.addSeries(series)
            
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

            axis_item.appendRow(signal_tree_model.make_watchable_item_row(series_item))
            
            # Bind the graph to the item tree
            axis_item.attach_axis(qt_axis)
            series_item.attach_series(series)
            
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
            yaxis.autoset_range(margin_ratio=self.Y_AXIS_MARGIN)

        self._state.allow_chart_toolbar()
        self._chart_toolbar.disable_chart_cursor()
        
        def update_xval(val:float, enabled:bool) -> None:
            self._xval_label.setText(f"{acquisition.xdata.name} : {val}")
            self._xval_label.setVisible(enabled)
        self._chartview.configure_chart_cursor(self._signal_tree, update_xval)

        self._apply_internal_state()


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


    def _chart_context_menu_slot(self, chartview_event:QContextMenuEvent) -> None:
        """Slot called when the user right click the chartview. Create a context menu and display it.
        This event is forwarded by the chartview through a signal."""
        context_menu = QMenu(self)

        context_menu.addSection("Zoom")

        # Reset zoom
        reset_zoom_action = context_menu.addAction(assets.load_tiny_icon(assets.Icons.Zoom100), "Reset zoom")
        reset_zoom_action.triggered.connect(self._reset_zoom_slot)
        reset_zoom_action.setEnabled(self._state.enable_reset_zoom_button())

        context_menu.addSection("Visibility")
        # Chart toolbar
        if self._chart_toolbar.isVisible():
            def hide_chart_toolbar() -> None:
                self._state.hide_chart_toolbar()
                self._apply_internal_state()
            show_hide_toolbar = context_menu.addAction(assets.load_tiny_icon(assets.Icons.EyeBar), "Hide toolbar")
            show_hide_toolbar.triggered.connect(hide_chart_toolbar)
        else:
            def allow_chart_toolbar() -> None:
                self._state.allow_chart_toolbar()
                self._apply_internal_state()
            show_hide_toolbar = context_menu.addAction(assets.load_tiny_icon(assets.Icons.Eye), "Show toolbar")
            show_hide_toolbar.triggered.connect(allow_chart_toolbar)
        show_hide_toolbar.setEnabled(self._state.can_display_toolbar())


        context_menu.addSection("Export")
        # Save image
        save_img_action = context_menu.addAction(assets.load_tiny_icon(assets.Icons.Image), "Save as image")
        save_img_action.triggered.connect(self._save_image_slot)
        save_img_action.setEnabled(self._state.allow_save_image())

        # Save CSV
        save_csv_action = context_menu.addAction(assets.load_tiny_icon(assets.Icons.CSV), "Save as CSV")
        save_csv_action.triggered.connect(self._save_csv_slot)
        save_csv_action.setEnabled(self._state.allow_save_csv())

        context_menu.popup(self._chartview.mapToGlobal(chartview_event.pos()))


    def _reset_zoom_slot(self) -> None:
        """Right-click -> Reset zoom"""
        self._chartview.chart().hide_mouse_callout()
        if self._xaxis is not None:
            self._xaxis.autoset_range()
        for yaxis in self._yaxes:
            yaxis.autoset_range(margin_ratio=self.Y_AXIS_MARGIN)
        self._chartview.update()


    def _save_image_slot(self) -> None:
        """When the user right-click the graph then click "Save as image" """
        if not self._state.allow_save_image():
            return 
        
        filepath:Optional[Path] = None
        toolbar_wanted = self._state.chart_toolbar_wanted

        try:
            # Hide toolbar and stats overlay, take the snapshot and put them back if needed
            self._state.chart_toolbar_wanted = False
            self._apply_internal_state()
            self._chartview.update()
            pix = self._chartview.grab()
            self._state.chart_toolbar_wanted = toolbar_wanted
            self._apply_internal_state()
            self._chartview.update()

            filepath = prompt.get_save_filepath_from_last_save_dir(self, ".png")
            if filepath is None:
                return
            pix.save(str(filepath), 'png', 100)
        except Exception as e:
            logfilepath = "<noname>" if filepath is None else str(filepath)
            tools.log_exception(self.logger, e, f"Error while saving graph into {logfilepath}")
            prompt.exception_msgbox(self, e, "Failed to save", f"Failed to save the graph to {logfilepath}")


    def _save_csv_slot(self) -> None:
        """When the user right-click the graph then click "Save as CSV" """
        if not self._state.allow_save_csv():
            return
        
        assert self._displayed_acquisition is not None

        filepath = prompt.get_save_filepath_from_last_save_dir(self, ".csv")
        if filepath is None:
            return
        
        def finished_callback(exception:Optional[Exception]) -> None:
            # This runs in a different thread
            if exception is not None:
                tools.log_exception(self.logger, exception, f"Error while saving graph into {filepath}" )
                InvokeInQtThread(lambda: prompt.exception_msgbox(self, exception, "Failed to save", f"Failed to save the graph to {filepath}"))
        
        loaded_sfd = self.server_manager.get_loaded_sfd()
        connected_device_info = self.server_manager.get_device_info()

        graph_sfd:Optional[sdk.SFDInfo] = None
        if loaded_sfd is not None and self._displayed_acquisition.firmware_id ==loaded_sfd.firmware_id:
            graph_sfd = loaded_sfd
        
        graph_device_info:Optional[sdk.DeviceInfo] = None
        if connected_device_info is not None and self._displayed_acquisition.firmware_id == connected_device_info.device_id:
            graph_device_info = connected_device_info

        # Todo : Add visual "saving..." feedback ?
        export_chart_csv_threaded(
            datetime_zero_sec = self._displayed_acquisition.acq_time,
            filename = filepath, 
            signals = self._signal_tree.get_signals(), 
            finished_callback = finished_callback,
            device = graph_device_info,
            sfd = graph_sfd
            )


    def _signal_tree_selection_changed_slot(self) -> None:
        """Whent he user selected/deselected a signal in the right menu"""
        self.update_emphasize_state()

    def _signal_tree_content_changed_slot(self) -> None:
        self._graph_config_widget.update_content()

    def update_emphasize_state(self) -> None:
        """Read the items in the SignalTree object (right menu with axis) and update the size/boldness of the graph series
        based on wether they are selected or not"""
        emphasized_yaxes_id:Set[int] = set()
        selected_index = self._signal_tree.selectedIndexes()
        axes_content = self._signal_tree.get_signals()
        for axis_item in axes_content:
            for signal_item in axis_item.signal_items:
                if signal_item.series_attached():
                    series = self._get_item_series(signal_item)
                    if signal_item.index() in selected_index:
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

    def _get_item_series(self, item:ChartSeriesWatchableStandardItem) -> ScrutinyLineSeries:
        """Return the series tied to a Tree Item (right menu)"""
        return cast(ScrutinyLineSeries, item.series())

    def _get_series_yaxis(self, series:ScrutinyLineSeries) -> ScrutinyValueAxisWithMinMax:
        """Return the Y-Axis tied to a series"""
        return cast(ScrutinyValueAxisWithMinMax, self._chartview.chart().axisY(series))

    def _chartview_key_pressed_slot(self, event:QKeyEvent) -> None:
        """Chartview Event forwarded through a signal"""
        if event.key() == Qt.Key.Key_Escape:
            self._signal_tree.clearSelection()

    def _chartview_resized_slot(self, event:QResizeEvent) -> None:
        """Chartview Event forwarded through a signal"""
        self._chart_status_overlay.adjust_sizes()
