#    embedded_graph_component.py
#        A component to configure, trigger, view and browse embedded datalogging.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from dataclasses import dataclass
from pathlib import Path
import functools
from datetime import datetime

from PySide6.QtWidgets import QVBoxLayout, QLabel, QWidget, QSplitter, QPushButton, QScrollArea, QHBoxLayout, QMenu, QTabWidget, QCheckBox, QMessageBox
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QContextMenuEvent, QKeyEvent, QResizeEvent

from scrutiny import sdk
from scrutiny.sdk import EmbeddedDataType
from scrutiny.sdk.datalogging import (
    DataloggingConfig, DataloggingRequest, DataloggingAcquisition, XAxisType, FixedFreqSamplingRate, DataloggerState, DataloggingStorageEntry
)
from scrutiny.sdk.client import ScrutinyClient

from scrutiny.gui import assets
from scrutiny.gui.tools import prompt
from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from scrutiny.gui.dashboard_components.embedded_graph.graph_config_widget import GraphConfigWidget
from scrutiny.gui.dashboard_components.embedded_graph.graph_browse_list_widget import GraphBrowseListWidget
from scrutiny.gui.dashboard_components.embedded_graph.chart_status_overlay import ChartStatusOverlay
from scrutiny.gui.widgets.base_chart import (
    ScrutinyChart, ScrutinyChartView, ScrutinyChartToolBar,  ScrutinyLineSeries, ScrutinyValueAxisWithMinMax
    )
from scrutiny.gui.widgets.graph_signal_tree import GraphSignalTree, ChartSeriesWatchableStandardItem, AxisStandardItem
from scrutiny.gui.widgets.feedback_label import FeedbackLabel

from scrutiny import tools
from scrutiny.tools.typing import *
from scrutiny.gui.tools.invoker import InvokeInQtThread
from scrutiny.gui.core.export_chart_csv import export_chart_csv_threaded


@dataclass
class EmbeddedGraphState:
    has_content:bool
    waiting_on_graph:bool
    chart_toolbar_wanted:bool
    has_failure_message:bool
    may_have_more_to_load:bool

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

    def can_load_more_acquisitions(self) -> bool:
        return self.may_have_more_to_load 

    def enable_load_more_button(self) -> bool:
        return self.can_load_more_acquisitions()

@dataclass
class InitialGraphListDownloadConditions:
    firmware_id:Optional[str]
class EmbeddedGraph(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("scope-96x128.png")
    _NAME = "Embedded Graph"

    Y_AXIS_MARGIN = 0.02
    """Margin used to autoset the Y-Axis based on the Y-data"""
    DOWNLOAD_ACQ_LIST_CHUNK_SIZE = 100
    """When browsing the existing acquisition, how many entries to fetch per call to the server"""

    # Chart common stuff 
    _left_pane:QWidget
    _center_pane:QWidget
    _right_pane:QWidget

    _splitter:QSplitter
    """3 section splitter separating left / center / right"""
    _xval_label:QLabel
    """The label used to display the X-Value when moving the graph cursor (red vertical line)"""
    _signal_tree:GraphSignalTree
    """The right side signal tree. contains the watchable we want to log / those present in the displayed graph"""
    _chartview:ScrutinyChartView
    """The QT element showing the chart"""
    _chart_toolbar:ScrutinyChartToolBar
    """Custom toolbar at the top of the graph selecting the zoom mode and cursor mode"""
    _xaxis:Optional[ScrutinyValueAxisWithMinMax]
    """The single X-Axis"""
    _yaxes:List[ScrutinyValueAxisWithMinMax]
    """The several Y-Axes"""
    _displayed_acquisition:Optional[DataloggingAcquisition]
    """The acquisition presently displayed by the chartview"""
    _chart_status_overlay:ChartStatusOverlay
    """An overlay we can put over the chart area to display a status message."""
    
    # Acquire stuff
    _graph_config_widget:GraphConfigWidget
    """The left pane widget that allow the user to configure its acquisition"""
    _btn_acquire:QPushButton
    """The Acquire button"""
    _btn_clear:QPushButton
    """The graph Clear button"""
    _acquire_feedback_label:FeedbackLabel
    """A label to display messages visible only in the "Acquire" tab """
    _pending_datalogging_request:Optional[DataloggingRequest]
    """The datalogging request presently being processed by the server. Is not None between a call to _acquire and a completion of the acquisition"""
    _request_to_ignore_completions:Dict[int, DataloggingRequest]
    """A map that list the datalogging request to ignore the failure from. It's a trick to avoid displaying a failure when the same user interrupt an 
    active acquisition with a new one. When that happen, the server will report that the previous acquisition failed with "Interrupted by new request" error. 
    We tell the user only if we are not the author of the new request"""

    # Browse stuff
    _graph_browse_list_widget:GraphBrowseListWidget
    """The list displaying the available acquisitions on the server"""
    _chk_browse_loaded_sfd_only:QCheckBox
    """A checkbox that filters the content of the acquisition list by keeping only those taken by the firmware presnetly loaded"""
    _browse_feedback_label:FeedbackLabel
    """A label to display messages visible only in the "Browse" tab"""
    _btn_delete_all:QPushButton
    """A button to delete all the acquisitions stored by the server"""
    _btn_load_more:QPushButton
    """A button to load more acquisitions from the server"""
    _oldest_acquisition_downloaded:Optional[datetime]
    """The oldest acquisition loaded. Used to download a new chunk of data when the user clicks "Load more" """

    _state:EmbeddedGraphState
    """Some state variables used to keep the UI consistent"""

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
            has_failure_message=False,
            may_have_more_to_load = True
        )

        self._teared_down = False
        self._displayed_acquisition = None
        self._pending_datalogging_request = None
        self._request_to_ignore_completions = {}
        self._oldest_acquisition_downloaded = None

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

        def make_acquire_left_pane() -> QWidget:
            self._graph_config_widget = GraphConfigWidget(self, 
                                                        watchable_registry=self.watchable_registry,
                                                        get_signal_dtype_fn=self._get_signal_size_list)
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            container_layout.setContentsMargins(0,0,0,0)

            clear_acquire_line = QWidget()
            clear_acquire_line_layout = QHBoxLayout(clear_acquire_line)
            self._btn_acquire = QPushButton("Acquire")
            self._btn_acquire.clicked.connect(self._btn_acquire_slot)
            self._btn_clear = QPushButton("Clear")
            self._btn_clear.clicked.connect(self._btn_clear_slot)

            clear_acquire_line_layout.addWidget(self._btn_clear)
            clear_acquire_line_layout.addWidget(self._btn_acquire)

            self._acquire_feedback_label = FeedbackLabel()

            container_layout.addWidget(self._graph_config_widget)
            container_layout.addWidget(clear_acquire_line)
            container_layout.addWidget(self._acquire_feedback_label)

            return container

        def make_browse_left_pane() -> QWidget:
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            
            self._chk_browse_loaded_sfd_only = QCheckBox("Loaded firmware only")
            self._chk_browse_loaded_sfd_only.setToolTip("Load acquisition taken with the same firmware that the device you're conencted to is using.")
            self._chk_browse_loaded_sfd_only.checkStateChanged.connect(self._checkbox_filter_sfd_checkstate_change_slot)
            if self.server_manager.get_loaded_sfd() is None:
                self._chk_browse_loaded_sfd_only.setDisabled(True)
                
            self._graph_browse_list_widget = GraphBrowseListWidget(self)
            self._btn_delete_all = QPushButton(assets.load_tiny_icon(assets.Icons.RedX), " Delete All", self)
            self._btn_load_more = QPushButton("Load more", self)
            self._browse_feedback_label = FeedbackLabel()

            btn_line = QWidget(self)
            btn_line_layout = QHBoxLayout(btn_line)
            btn_line_layout.addWidget(self._btn_load_more)
            btn_line_layout.addWidget(self._btn_delete_all)

            self._graph_browse_list_widget.signals.delete.connect(self._request_delete_single_slot)
            self._graph_browse_list_widget.signals.rename.connect(self._request_rename_slot)
            self._graph_browse_list_widget.signals.display.connect(self._browse_display_acquisition_slot)
            self._btn_delete_all.clicked.connect(self._btn_delete_all_clicked_slot)
            self._btn_load_more.clicked.connect(self._btn_load_more_clicked_slot)

            container_layout.addWidget(self._chk_browse_loaded_sfd_only)
            container_layout.addWidget(self._graph_browse_list_widget)
            container_layout.addWidget(btn_line)
            container_layout.addWidget(self._browse_feedback_label)

            return container

        def make_left_pane() -> QWidget:

            acquire_tab_content = make_acquire_left_pane()
            browse_tab_content = make_browse_left_pane()

            tab = QTabWidget(self)
            tab.addTab(acquire_tab_content, "Acquire")
            tab.addTab(browse_tab_content, "Browse")

            def current_changed_slot(index:int) -> None:
                if index == 0:
                    self._acquire_tab_visible_slot()
                elif index == 1:
                    self._browse_tab_visible_slot()

            tab.currentChanged.connect(current_changed_slot)
            
            left_pane_scroll = QScrollArea(self)
            left_pane_scroll.setWidget(tab)
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
        self.server_manager.signals.datalogging_storage_updated.connect(self._datalogging_storage_updated_slot)
        self.server_manager.signals.sfd_loaded.connect(self._sfd_loaded_slot)
        self.server_manager.signals.sfd_unloaded.connect(self._sfd_unloaded_slot)
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
        """Virtual func. For dashboard export"""
        raise NotImplementedError()

    def load_state(self, state: Dict[Any, Any]) -> None:
        """Virtual func. For dashboard reload"""
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
        
        self._btn_load_more.setEnabled(self._state.enable_load_more_button())
        
        self._chart_status_overlay.setVisible(self._state.must_show_overlay())

    def _update_datalogging_capabilities(self) -> None:
        """Update the UI with new datalogging capabilities broadcast by the server"""
        self._graph_config_widget.configure_from_device_info(self.server_manager.get_device_info())

    def _registry_changed_slot(self) -> None:
        """Called when the server manager has finished making a change to the registry"""
        if not self._state.has_content: # We are not inspecting data.
            self._signal_tree.update_all_availabilities()

    def _datalogging_state_changed_slot(self) -> None:
        """When the server tells us that the datalogger has changed state"""
        self._update_acquiring_overlay()

    def _sfd_loaded_slot(self) -> None:
        """Called when the server loads a SFD"""
        self._enable_sfd_filter()   # In browse tab

    def _sfd_unloaded_slot(self) -> None:
        """Called when the server unloads a SFD"""
        self._disable_sfd_filter()  # In browse tab


# region Chart handling

    def _clear_graph(self) -> None:
        """Remove the acquisition presently displayed in the chartview"""
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
        """Display a big error message in the chart area"""
        self._clear_graph()
        self._chart_status_overlay.set(assets.Icons.Error, message)
        self._state.has_failure_message = True
        self._apply_internal_state()

    def _clear_graph_error(self) -> None:
        """Remove the big error message in the chart area"""
        self._chart_status_overlay.set(None, "")
        self._state.has_failure_message = False
        self._apply_internal_state()

    def _display_acquisition(self, acquisition:DataloggingAcquisition) -> None:
        """Display a datalogging acquisition in the chartview"""
        # Empty the chart area
        self._clear_graph()
        self._chart_status_overlay.set(None, "")
        self._chart_status_overlay.hide()
        
        # Update state variables
        self._state.has_failure_message = False
        self._state.waiting_on_graph = False
        self._state.has_content = True

        # Todo, we could reload a SFD when downloading an acquisiton from a different SFD
        self._displayed_acquisition = acquisition

        # Since we put a graph, the signal tree (on the right) needs to be in sync with the graph content.
        # We start by clearing the signal tree and refill it with the signals from the acquisition
        signal_tree_model = self._signal_tree.model()
        signal_tree_model.removeRows(0, signal_tree_model.rowCount())

        chart = self._chartview.chart()
        self._chart_toolbar.show()
        
        # Sets the X-Axis
        self._xaxis = ScrutinyValueAxisWithMinMax(chart)        
        self._xaxis.setTitleText(acquisition.xdata.name)
        self._xaxis.setTitleVisible(True)
        chart.setAxisX(self._xaxis)

        sdk_yaxes = acquisition.get_unique_yaxis_list()         # The axes as defined by the acquisition object
        sdk2qt_axes:Dict[int, ScrutinyValueAxisWithMinMax] = {} # A mapping between the acquisition axes and the QT Chart axes
        sdk2tree_axes:Dict[int, AxisStandardItem] = {}          # A mapping between the acquisition axes and the axes displayed in the signal tree
        
        # Create the axes (Chart + Signal tree)
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
            self._yaxes.append(qt_axis) # Keeps all the references in a list for convenience.

        # Fill the axes with data
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
            
            # if this is not none, the x-axis was a watchable.
            # We sort according to the X-Value so that the x-axis is monotonic.
            # Moving graph cursor expect monotonic data. 
            # It's also faster to search and avoid left right lines in the graph
            if acquisition.xdata.logged_watchable is not None:
                qt_pointf_data.sort(key=lambda p: p.x())

            series.replace(qt_pointf_data)
            series.attachAxis(self._xaxis)
            series.attachAxis(qt_yaxis)
            series.setName(ydata.series.name)
            
            # Update, do not set. Axes are shared by many datasets
            qt_yaxis.update_minmax(min(yseries_data))
            qt_yaxis.update_minmax(max(yseries_data))
        
        # Set min/max. Only 1 dataset for the X-Axis
        self._xaxis.set_minval(min(xseries_data))
        self._xaxis.set_maxval(max(xseries_data))

        self._xaxis.autoset_range()
        for yaxis in self._yaxes:
            yaxis.autoset_range(margin_ratio=self.Y_AXIS_MARGIN)

        # Put the chart toolbar in a correct state
        self._state.allow_chart_toolbar()
        self._chart_toolbar.disable_chart_cursor()
        
        # Enable the chart cursor so it can display values in the signal tree
        def update_xval(val:float, enabled:bool) -> None:
            self._xval_label.setText(f"{acquisition.xdata.name} : {val}")
            self._xval_label.setVisible(enabled)
        self._chartview.configure_chart_cursor(self._signal_tree, update_xval)

        self._apply_internal_state()    # UI update based on the state variables


    def _chartview_zoombox_selected_slot(self, zoombox:QRectF) -> None:
        """When the user changes the zoom with its mouse. Either a rectangle drawn (rubberband) or a wheel event.
        This signals comes from the Scrutiny extended Chartview"""

        if not self._state.allow_zoom():
            return 

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

        context_menu.addSection("Content")
        #Clear
        clear_chart_action = context_menu.addAction(assets.load_tiny_icon(assets.Icons.RedX), "Clear")
        clear_chart_action.triggered.connect(self._clear_graph)
        clear_chart_action.setEnabled(self._state.enable_clear_button())

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
        """A watchable has been added/remove from the watchable tree"""
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

# endregion 

# region Acquire Tab

    def _get_signal_size_list(self) -> List[EmbeddedDataType]:
        """This function provide all the embedded data type of the signals presently in the signal tree.
        Used to estimate the duration of the acquisition."""

        outlist:List[EmbeddedDataType] = []
        axes = self._signal_tree.get_signals()
        for axis in axes:
            for item in axis.signal_items:
                watchable = self.watchable_registry.get_watchable_fqn(item.fqn)  # Might be unavailable
                if watchable is None:
                    return []
                outlist.append(watchable.datatype)

        return outlist
            
    def _acquire_tab_visible_slot(self) -> None:
        """When the "Acquire" tab become visible"""
        pass    # Nothing to do

    def _btn_acquire_slot(self) -> None:
        """When the user presses the "Acquire" button """
        # Get the config from the config widget. 
        # Then add the signals from the signal tree and send that to the server if all valid
        result = self._graph_config_widget.validate_and_get_config()
        if not result.valid:
            assert result.error is not None
            self._acquire_feedback_label.set_error(result.error)
            return 
        assert result.config is not None
        
        # Check that we have watchables in the signal tree
        self._acquire_feedback_label.clear()
        axes_signal = self._signal_tree.get_signals()
        if len(axes_signal) == 0:   # check for axes
            self._acquire_feedback_label.set_error("No signals to acquire")
            return
        
        nb_signals = 0
        for axis in axes_signal:    # Check for axes content
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
            self._acquire_feedback_label.set_error("No signals to acquire")
            return

        # Starting form here,  the config given by the user is valid. We need to request the server now
        self._acquire_feedback_label.clear()
        self._clear_graph()        
        self._acquire(result.config)    # Request the server for that acquisition
        
    def _acquire(self, config:DataloggingConfig) -> None:
        """Request the server to make a datalogging acquisition"""
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
                self._callback_acquire_request_failed(request=None, error=error, msg="")
                return
            assert request is not None

            self.logger.debug(f"Datalog accepted. Request {request.request_token}")

            if self._pending_datalogging_request is not None:
                # We use a dict instead of a set of id to keep a reference to the object so it's kept alive and ther eis no id reuse issue.
                self._request_to_ignore_completions[id(self._pending_datalogging_request)] = self._pending_datalogging_request
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
                
                self._pending_datalogging_request = None
                if error is not None:   # Exception while waiting
                    self._callback_acquire_request_failed(request, error, msg="")   # The message will be the exception
                    return

                if not request.completed:   # Should not happen. Happens only when there is a timeout on wait_for_completion (we don't have one)
                    self._callback_acquire_request_failed(request, None, "Failed to complete")
                    return

                if not request.is_success:  # Didn't complete. The device or the server might be gone while waiting
                    self._callback_acquire_request_failed(request, None, request.failure_reason)
                    return
                
                self._callback_acquire_request_succeeded(request)   # SUCCESS!
            
            self._pending_datalogging_request = request
            
            self.server_manager.schedule_client_request(
                user_func=bg_thread_wait_for_completion,
                ui_thread_callback=qt_thread_request_completed
            )

            self._acquire_feedback_label.clear()
            self._apply_internal_state()
        
        self.server_manager.schedule_client_request(
            user_func= bg_thread_start_datalog,
            ui_thread_callback=qt_thread_datalog_started
        )

        self._acquire_feedback_label.set_info("Acquisition requested")


    def _update_acquiring_overlay(self) -> None:
        """When an acquisition is in progress, an overlay on the chart display the progress. This method updates the message
        when the server informs the UI that the datalogger state changed"""

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

    def _callback_acquire_request_failed(self, 
                                 request:Optional[DataloggingRequest], 
                                 error:Optional[Exception], 
                                 msg:str="Request failed") -> None:
        """Our acquisition failed. Tell the user why"""
        self._state.waiting_on_graph = False
        self._acquire_feedback_label.clear()

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

    def _callback_acquire_request_succeeded(self, request:DataloggingRequest) -> None:
        """Our acquisition succeeded. Download and display the content right away"""
        assert request.completed and request.is_success
        assert request.acquisition_reference_id is not None
        self._acquire_feedback_label.clear()
        self._graph_config_widget.update_autoname()

        self._apply_internal_state()    # Update the UI

        def bg_thread_download_data(client:ScrutinyClient) -> DataloggingAcquisition:
            assert request.acquisition_reference_id is not None
            return client.read_datalogging_acquisition(reference_id=request.acquisition_reference_id)
        
        def qt_thread_receive_acquisition_data(acquisition:Optional[DataloggingAcquisition], error:Optional[Exception]) -> None:
            if error is not None:
                self._callback_acquire_request_failed(request, error,  f"The acquisition succeeded, but downloading its data failed. The content is still available in the server database.\n Error {error}")
                return 

            assert acquisition is not None
            self._display_acquisition(acquisition)

        self.server_manager.schedule_client_request(
            user_func=bg_thread_download_data, 
            ui_thread_callback=qt_thread_receive_acquisition_data
            )

    def _btn_clear_slot(self) -> None:
        """When the "Clear" button is pressed """
        self._clear_graph()
        self._acquire_feedback_label.clear()

# endregion

# region Browse Tab
    def _browse_tab_visible_slot(self) -> None:
        """When the user make "Browse" tab visible"""
        # We initiate the downlaod of a first chunk of acquisition list
        self._do_initial_graph_list_download()

    def _datalogging_storage_updated_slot(self, change_type:sdk.DataloggingListChangeType, reference_id:Optional[str]) -> None:
        """The server informs us that a change was made to the datalogging storage. We use ths to update our list, even if this GUI 
        is the initiator of the change."""

        if change_type == sdk.DataloggingListChangeType.DELETE_ALL:
            self._do_initial_graph_list_download()
        elif change_type == sdk.DataloggingListChangeType.DELETE:
            if reference_id is not None:
                self._graph_browse_list_widget.remove_by_reference_id(reference_id)
        elif change_type == sdk.DataloggingListChangeType.UPDATE:
            if reference_id is not None:
                def bg_thread_update(client:ScrutinyClient) -> Optional[DataloggingStorageEntry]:
                    return client.read_datalogging_acquisitions_metadata(reference_id)
                def qt_thread_update(entry:Optional[DataloggingStorageEntry], error:Optional[Exception]) -> None:
                    if entry is not None:
                        self._graph_browse_list_widget.update_storage_entry(entry)
                
                self.server_manager.schedule_client_request(bg_thread_update, qt_thread_update)
        elif change_type == sdk.DataloggingListChangeType.NEW:
            if reference_id is not None:
                def bg_thread_new(client:ScrutinyClient) -> Optional[DataloggingStorageEntry]:
                    return client.read_datalogging_acquisitions_metadata(reference_id)
                def qt_thread_new(entry:Optional[DataloggingStorageEntry], error:Optional[Exception]) -> None:
                    if entry is not None:
                        self._graph_browse_list_widget.add_storage_entries([entry])
                
                self.server_manager.schedule_client_request(bg_thread_new, qt_thread_new)
        else:
            self.logger.warning(f"Unsupported change type {change_type}")

    def _enable_sfd_filter(self) -> None:
        """Make the checkbox to filter per firmware ID available"""
        self._chk_browse_loaded_sfd_only.setEnabled(True)
        self._chk_browse_loaded_sfd_only.setCheckState(Qt.CheckState.Unchecked)

    def _disable_sfd_filter(self) -> None:
        """Make the checkbox to filter per firmware ID unavailable"""
        self._chk_browse_loaded_sfd_only.setDisabled(True)
        self._chk_browse_loaded_sfd_only.setCheckState(Qt.CheckState.Unchecked)

    def _browse_display_acquisition_slot(self, reference_id:str) -> None:
        """When the user request to load an acquisition and display it in the graph viewer"""
        def bg_thread_download(client:ScrutinyClient) -> DataloggingAcquisition:
            return client.read_datalogging_acquisition(reference_id)

        def qt_thread_show(acq:Optional[DataloggingAcquisition], error:Optional[Exception]) -> None:
            if acq is not None and error is None:
                self._display_acquisition(acq)
            else:
                self._display_graph_error("Cannot show graph: " + str(error))
        
        self.server_manager.schedule_client_request(bg_thread_download, qt_thread_show )

    def _request_rename_slot(self, reference_id:str, new_name:str) -> None:
        """The user wants to rename an acquisition. Signal comes from the list widget"""

        def bg_thread_rename(client:ScrutinyClient) -> None: 
            client.update_datalogging_acquisition(reference_id, name=new_name)
        
        def qt_thread_complete(_:None, error:Optional[Exception]) -> None:
            if error is not None:
                self._browse_feedback_label.set_error(f'Failed to rename acquisition to "{new_name}". {error}')
            else:
                self._browse_feedback_label.clear()
        
        self.server_manager.schedule_client_request(bg_thread_rename, qt_thread_complete)

    def _request_delete_single_slot(self, reference_ids:List[str]) -> None:
        """Called when the user requests to delete a single acquisition from the server storage"""
        self._browse_feedback_label.set_info("Deleting...")
        success_count = tools.MutableInt(0)

        def bg_thread_delete(reference_id:str, client:ScrutinyClient) -> None:    
            client.delete_datalogging_acquisition(reference_id)
        
        def qt_thread_complete(_:None, error:Optional[Exception]) -> None:
            if error is not None:
                self._browse_feedback_label.set_error(f"Failed to delete. {error}")
            else:
                success_count.val += 1
                if len(reference_ids) == success_count.val: 
                    self._browse_feedback_label.clear()
        
        for reference_id in reference_ids:
            partial = functools.partial(bg_thread_delete, reference_id)
            self.server_manager.schedule_client_request(partial, qt_thread_complete)

    
    def _do_initial_graph_list_download(self) -> None:
        """Reset the content of the available acquisitions and downloads the first page of data"""
        self._oldest_acquisition_downloaded = None
        self._state.may_have_more_to_load = True
        self._graph_browse_list_widget.clear()
        self._browse_feedback_label.set_info("Downloading...")

        # If there is a firmware loaded and the user wants to filter by it.
        firmware_id:Optional[str] = None
        loaded_sfd = self.server_manager.get_loaded_sfd() 
        if loaded_sfd is not None and self._chk_browse_loaded_sfd_only.checkState() == Qt.CheckState.Checked:
            firmware_id = loaded_sfd.firmware_id
        
        self._initial_graph_list_download_conditions = InitialGraphListDownloadConditions(
            firmware_id = firmware_id
        )

        # Launch download
        def bg_thread_download(client:ScrutinyClient) -> List[DataloggingStorageEntry]:    
            return client.list_stored_datalogging_acquisitions(
                firmware_id=self._initial_graph_list_download_conditions.firmware_id,   # Can be None
                count=self.DOWNLOAD_ACQ_LIST_CHUNK_SIZE
                )
        
        def qt_thread_receive(result:Optional[List[DataloggingStorageEntry]], error:Optional[Exception]) -> None:
            if result is not None:
                self._receive_acquisition_list(result)
                self._browse_feedback_label.clear()
                self._graph_browse_list_widget.autosize_columns()
            else:
                msg = "Failed to download the datalogging data."
                if error is not None:
                    msg += f" {error}"
                self._browse_feedback_label.set_error(msg)
            self._apply_internal_state()

        self.server_manager.schedule_client_request(bg_thread_download, qt_thread_receive)

    def _checkbox_filter_sfd_checkstate_change_slot(self, checkstate:Qt.CheckState) -> None:
        """When the checkbox to filter by firmware ID is checked/unchecked """
        self._do_initial_graph_list_download()  # Just relaunch a new download from scratch. The checkbox is checked inside

    def _btn_delete_all_clicked_slot(self) -> None:
        """ The "Delete All" button has been pressed """
        msgbox = QMessageBox(self)
        msgbox.setIcon(QMessageBox.Icon.Warning)
        msgbox.setWindowTitle("Are you sure?")
        msgbox.setText("You are about to delete all datalogging acquisition on the server.\nProceed?")
        msgbox.setStandardButtons(QMessageBox.StandardButton.No | QMessageBox.StandardButton.Yes)
        msgbox.setDefaultButton(QMessageBox.StandardButton.No)

        msgbox.setModal(True)
        reply = msgbox.exec()   # Ask the user to confirm

        if reply == QMessageBox.StandardButton.Yes:
            self._request_delete_all()

    def _request_delete_all(self) -> None:
        """Called when the user request to delete all the acquisitions in the server storage"""
        self._browse_feedback_label.set_info("Clearing storage...")
        def bg_thread_clear(client:ScrutinyClient) -> None:    
            client.clear_datalogging_storage()
        
        def qt_thread_complete(_:None, error:Optional[Exception]) -> None:
            if error is not None:
                msg = f"Failed to clear the datalogging storage. {error}"
                self._browse_feedback_label.set_error(msg)
            else:
                self._browse_feedback_label.clear()
        
        self.server_manager.schedule_client_request(bg_thread_clear, qt_thread_complete)

    def _btn_load_more_clicked_slot(self) -> None:
        """ When the "Load more" button has been clicked"""
        if not self._state.can_load_more_acquisitions():
            return
        assert self._oldest_acquisition_downloaded is not None
        
        self._browse_feedback_label.set_info("Downloading...")
        def bg_thread_download(client:ScrutinyClient) -> List[DataloggingStorageEntry]:    
            return client.list_stored_datalogging_acquisitions(
                firmware_id=self._initial_graph_list_download_conditions.firmware_id,   # Can be None. Repeat what we did in the initial download
                count=self.DOWNLOAD_ACQ_LIST_CHUNK_SIZE,
                before_datetime=self._oldest_acquisition_downloaded # This is a subsequent download. Start from the last one received
                )
        
        def qt_thread_receive(result:Optional[List[DataloggingStorageEntry]], error:Optional[Exception]) -> None:
            if result is not None:
                self._receive_acquisition_list(result)
                self._browse_feedback_label.clear()
            else:
                msg = "Failed to download the datalogging data."
                if error is not None:
                    msg += f" {error}"
                self._browse_feedback_label.set_error(msg)
            self._apply_internal_state()

        self.server_manager.schedule_client_request(bg_thread_download, qt_thread_receive)

    def _receive_acquisition_list(self, result:List[DataloggingStorageEntry]) -> None:
        """When we receive a chunk of acquisition metadata entries. We add the data to the actual list"""
        if len(result) < self.DOWNLOAD_ACQ_LIST_CHUNK_SIZE:
            self._state.may_have_more_to_load = False
        if len(result) > 0:
            self._graph_browse_list_widget.add_storage_entries(result)
            self._oldest_acquisition_downloaded = min([x.timestamp for x in result])
# endregion
