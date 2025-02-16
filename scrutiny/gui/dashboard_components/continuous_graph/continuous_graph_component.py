#    continuous_graph_component.py
#        A component that makes a real time graphs of the values streamed by the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from datetime import datetime
import functools
import math
from pathlib import Path
import logging
from dataclasses import dataclass
import re
import os

from PySide6.QtGui import QPainter, QFontMetrics, QFont, QColor, QContextMenuEvent, QKeyEvent
from PySide6.QtWidgets import (QHBoxLayout, QSplitter, QWidget, QVBoxLayout,  QMenu, QSizePolicy,
                               QPushButton, QFormLayout, QSpinBox, QGraphicsItem, QStyleOptionGraphicsItem,
                               QLineEdit, QCheckBox, QGroupBox)
from PySide6.QtCore import Qt, QItemSelectionModel, QPointF, QTimer, QRectF, QRect

from scrutiny import sdk
from scrutiny import tools
from scrutiny.gui import assets
from scrutiny.gui.app_settings import app_settings
from scrutiny.gui.tools import prompt
from scrutiny.gui.tools.invoker import InvokeQueued, InvokeInQtThread
from scrutiny.gui.tools.min_max import MinMax
from scrutiny.gui.core.definitions import WidgetState
from scrutiny.gui.core.watchable_registry import WatchableRegistryNodeNotFoundError, ValueUpdate
from scrutiny.gui.widgets.feedback_label import FeedbackLabel
from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from scrutiny.gui.dashboard_components.common.graph_signal_tree import GraphSignalTree, ChartSeriesWatchableStandardItem
from scrutiny.gui.dashboard_components.common.export_chart_csv import export_chart_csv_threaded, make_csv_headers
from scrutiny.gui.dashboard_components.common.base_chart import (
    ScrutinyLineSeries, ScrutinyValueAxisWithMinMax, ScrutinyChartCallout, ScrutinyChartView, ScrutinyChart,
    ScrutinyChartToolBar)
from scrutiny.gui.dashboard_components.continuous_graph.decimator import GraphMonotonicNonUniformMinMaxDecimator
from scrutiny.gui.core.preferences import gui_preferences
from scrutiny.sdk.listeners.csv_logger import CSVLogger, CSVConfig
from scrutiny.tools.profiling import VariableRateExponentialAverager

from typing import Dict, Any, Union, List, Optional, cast, Set, Generator

class CsvLoggingMenuWidget(QWidget):
    _chk_enable:QCheckBox
    _txt_folder:QLineEdit
    _txt_filename_pattern:QLineEdit
    _spin_max_line_per_file:QSpinBox
    _gb_content:QGroupBox

    def __init__(self, parent:QWidget):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)

        self._chk_enable = QCheckBox("Log to CSV", self)
        self._gb_content = QGroupBox(self)
        self._gb_content.setVisible(False)
        layout.addWidget(self._chk_enable)
        layout.addWidget(self._gb_content)
        self._txt_folder = QLineEdit(self)
        self._txt_filename_pattern = QLineEdit(self)
        self._spin_max_line_per_file = QSpinBox(self)
        self._spin_max_line_per_file.setMinimum(1000)
        self._spin_max_line_per_file.setMaximum(1000000)
        self._spin_max_line_per_file.setValue(10000)
        self._btn_browse = QPushButton("...", self)
        self._txt_folder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._btn_browse.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        self._btn_browse.setMinimumWidth(20)
        self._btn_browse.setMaximumWidth(40)

        self._btn_browse.clicked.connect(self._browse_clicked_slot)

        filebrowse_line = QWidget()
        filebrowse_layout = QHBoxLayout(filebrowse_line)
        filebrowse_layout.setContentsMargins(0,0,0,0)
        filebrowse_layout.addWidget(self._txt_folder)
        filebrowse_layout.addWidget(self._btn_browse)

        gb_layout = QFormLayout(self._gb_content)

        gb_layout.addRow("Folder", filebrowse_line)
        gb_layout.addRow("File prefix", self._txt_filename_pattern)
        gb_layout.addRow("Lines/file", self._spin_max_line_per_file)

        self._chk_enable.checkStateChanged.connect(self._check_state_changed_slot)


    def _check_state_changed_slot(self, state:Qt.CheckState) -> None:
        if state == Qt.CheckState.Checked:
            self._gb_content.setVisible(True)
        else:
            self._gb_content.setVisible(False)

    def _browse_clicked_slot(self) -> None:
        actual_folder:Optional[Path] = None # USe last save dir if None
        if os.path.isdir(self._txt_folder.text()):
            actual_folder = Path(os.path.normpath(self._txt_folder.text()))
            actual_folder = actual_folder.absolute()

        folder = prompt.get_save_folderpath_from_last_save_dir(self, "Select a folder", save_dir=actual_folder)
        if folder is not None:
            self._txt_folder.setText(str(folder))
    
    def require_csv_logging(self) -> bool:
        return self._chk_enable.isChecked()

    def validate(self) -> None:
        folder = self._txt_folder.text()
        if len(folder) == 0:
            raise ValueError("No folder selected")
        filename_pattern = self._txt_filename_pattern.text()
        if len(filename_pattern) == 0:
            raise ValueError("No filename prefix provided")

        valid_filename = re.compile(r"^[A-Za-z0-9\._\-\(\)]+$")
        if not valid_filename.match(filename_pattern):
            raise ValueError("Invalid characters in filename")
        
        folder = os.path.normpath(folder)
        if not os.path.isabs(folder):
            folder = os.path.normpath(os.path.abspath(folder))

        if not os.path.isdir(folder):
            raise FileNotFoundError(f"Folder {folder} does not exist")

        self._txt_folder.setText(folder)
    
    def make_csv_logger(self, logging_logger:Optional[logging.Logger] = None)  -> CSVLogger:
        # Validation happens inside the constructor
        self.validate()

        csv_config = CSVConfig(
            delimiter=',',
            newline='\n'
        )

        return CSVLogger(
            folder = self._txt_folder.text(),
            filename = self._txt_filename_pattern.text(),
            lines_per_file = self._spin_max_line_per_file.value(),
            datetime_format=gui_preferences.global_namespace().long_datetime_format(),
            csv_config=csv_config,
            convert_bool_to_int=True,
            logger=logging_logger,
            file_part_0pad=4
        )

class RealTimeScrutinyLineSeries(ScrutinyLineSeries):
    """Extension of a LineSeries that is meant to display data in real time.
    It has support for decimation and some fancy tricks to kep tracks of min/max
    value with minimal CPU computation"""

    _decimator:GraphMonotonicNonUniformMinMaxDecimator
    """The decimator that keeps the whole dataset and also provides a decimated version of it"""
    _x_minmax:MinMax
    """Min/Max trackerfor the X values"""
    _y_minmax:MinMax
    """Min/Max trackerfor the Y values"""
    _dirty:bool
    """Flag indicating that the output of the decimator has new data ready to be flushed to the chart"""

    def __init__(self, *args:Any, **kwargs:Any) -> None:
        super().__init__(*args, **kwargs)
        self._decimator = GraphMonotonicNonUniformMinMaxDecimator()
        self._x_minmax = MinMax()
        self._y_minmax = MinMax()
        self._dirty = False

    def set_x_resolution(self, resolution:float) -> bool:
        """Set the X width used by the decimator. All the points within a moving window of this size will be clustered together"""
        changed = self._decimator.set_x_resolution(resolution)
        if changed:            
            self._dirty = True
        return changed
    
    def decimation_factor(self) -> float:
        """Provides an estimation of the decimation factor"""
        return self._decimator.decimation_factor()
    
    def count_decimated_points(self) -> int:
        """Count the number of points at the output of the decimator"""
        return len(self._decimator.get_decimated_buffer())

    def count_all_points(self) -> int:
        """Count the number of points at the input of the decimator (full dataset)"""
        return len(self._decimator.get_input_buffer())

    def add_point(self, point:QPointF) -> int:
        """Adds a point to the decimator input. New output points may or may not be available after

        :param point: The point to add
        :return: The number of new points available at the output. May be bigger than 1
        """
        n = self._decimator.add_point(point)    # Can have 2 points out for a single in (min/max)
        if n > 0:
            # New data available at the output. update the min/max in real time for axis autorange
            start_index = len(self._decimator.get_decimated_buffer())-n     # Avoid negative slice. Not all container supports it
            for p in self._decimator.get_decimated_buffer()[start_index:]:
                self._y_minmax.update(p.y())
                self._x_minmax.update_max(p.x())
            self._dirty=True
        return n
    
    def delete_up_to_x_without_flushing(self, x:float) -> None:
        """Delete both input and output data up to a value of X specified. Assumes a monotonic X axis
        
        :param x: The minimum X value allowed. Any points with a X value smaller than this will get deleted
        
        """
        in_deleted, out_deleted = self._decimator.delete_data_up_to_x(x)
        if out_deleted > 0: # That affects the visible graph
            self._dirty = True
    
    def get_last_x(self) -> Optional[float]:
        """Return the most recent point from the input buffer"""
        buffer = self._decimator.get_input_buffer()
        if len(buffer) == 0:
            return None
        return buffer[-1].x()

    def get_first_x(self) -> Optional[float]:
        """Return the oldest point from the input buffer"""
        buffer = self._decimator.get_input_buffer()
        if len(buffer) == 0:
            return None
        return buffer[0].x()
    
    def get_last_decimated_x(self) -> Optional[float]:
        """Return the most recent point fromthe output buffer (decimated buffer)"""
        buffer = self._decimator.get_decimated_buffer()
        if len(buffer) == 0:
            return None
        return buffer[-1].x()

    def get_first_decimated_x(self) -> Optional[float]:
        """Return the oldest point fromthe output buffer (decimated buffer)"""
        buffer = self._decimator.get_decimated_buffer()
        if len(buffer) == 0:
            return None
        return buffer[0].x()

    def flush_decimated(self) -> None:
        """Copy the decimator output buffer (decimated) into the chart buffer for display"""
        self.replace(self._decimator.get_decimated_buffer())
        self._dirty = False
    
    def flush_full_dataset(self) -> None:
        """Copy the decimator input buffer (full dataset) into the chart buffer for display"""
        self.replace(self._decimator.get_input_buffer())

    def is_dirty(self) -> bool:
        return self._dirty

    def stop_decimator(self) -> None:
        """Stops the decimator, Any input pointed being held for decimation will be moved to the output"""
        self._decimator.force_flush_pending()

    def recompute_minmax(self) -> None:
        """Recompute the min/max values of the whole dataset"""

        # Since the decimator always keeps the min/max of a cluster, we can safely use the decimated buffer to 
        # accurately compute the min/max of the whole dataset. We need to take in account the few points at the
        # end of the input buffer not yet moved to the output
        decimated_buffer = self._decimator.get_decimated_buffer()       # The output buffer
        unprocessed_inputs = self._decimator.get_unprocessed_input()    # The few most recent points at the input buffer
        
        self._x_minmax.clear()
        self._y_minmax.clear()

        # Tests have shown that it is ~2x faster to iterate twice (1 to extract the right value, second to run the min/max function) than
        # iterate once with a key specifier
        self._x_minmax.update_from_many([p.x() for p in decimated_buffer])  
        self._y_minmax.update_from_many([p.y() for p in decimated_buffer])

        self._x_minmax.update_from_many([p.x() for p in unprocessed_inputs])
        self._y_minmax.update_from_many([p.y() for p in unprocessed_inputs])

    def x_min(self) -> Optional[float]:
        """The smallest X value in the whole dataset"""
        return self._x_minmax.min()
    
    def x_max(self) -> Optional[float]:
        """The largest X value in the whole dataset"""
        return self._x_minmax.max()
    
    def y_min(self) -> Optional[float]:
        """The smallest Y value in the whole dataset"""
        return self._y_minmax.min()
    
    def y_max(self) -> Optional[float]:
        """The largest Y value in the whole dataset"""
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
            refresh_rate_str = "N/A"
            if self._stats.repaint_rate.is_enabled():
                refresh_rate_str = "%0.1f/sec" % self._stats.repaint_rate.get_value()
            opengl_enabled_str = "Enabled" if self._stats.opengl else "Disabled"
            lines = [
                "Decimation: %0.1fx" % self._stats.decimation_factor,
                "Visible points: %d/%d" % (self._stats.visible_points, self._stats.total_points),
                "OpenGL: %s" % opengl_enabled_str,
                "Refresh rate: %s" % refresh_rate_str 
            ]
            self._text =  '\n'.join(lines)

        def _compute_geometry(self) -> None:
            self.prepareGeometryChange()
            metrics = QFontMetrics(self._font)
            self._text_rect = QRectF(metrics.boundingRect(QRect(0, 0, 200, 100), Qt.AlignmentFlag.AlignLeft, self._text))
            self._bounding_box = QRectF(self._text_rect.adjusted(0,0,0,0))

        def boundingRect(self) -> QRectF:
            return self._bounding_box

        def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget]=None) -> None:
            painter.fillRect(self._text_rect, QColor(0xC8, 0xE8, 0xFF, 50))
            painter.setPen(QColor(0,0,0))
            painter.drawText(self._text_rect, self._text)


    visible_points:int
    """Number of points drawn on the chart"""
    total_points:int
    """Number of points stored in memory that could go on the graph (does not include points so old that they get removed)"""
    decimation_factor:float
    """Ratio of visible points/total points"""
    opengl:bool
    """Says if OpenGL is activated"""
    repaint_rate:VariableRateExponentialAverager
    """Estimated repaint rate in number of repaint/sec"""
    _overlay:Overlay
    """The GraphicItem overlay being displayed on top of the chart"""
    _allow_show_overlay:bool
    """A flag enabling/disabling the overlay"""

    def __init__(self, draw_zone:Optional[QGraphicsItem] = None) -> None:
        self._allow_show_overlay = True
        self._overlay = self.Overlay(draw_zone, self)
        self.repaint_rate = VariableRateExponentialAverager(time_estimation_window=0.2, tau=1, near_zero=0.01)
        self.clear()

    def clear(self) -> None:
        self.opengl = False
        self.visible_points = 0
        self.total_points = 0
        self.decimation_factor = 1

    def show_overlay(self) -> None:
        if self._allow_show_overlay:
            self._overlay.show()
            self._overlay.update_content()

    def hide_overlay(self) -> None:
        self._overlay.hide()

    def update_overlay(self) -> None:
        self._overlay.update_content()

    def overlay(self) -> Overlay:
        return self._overlay

    def allow_overlay(self) -> None:
        self._allow_show_overlay = True
        self.show_overlay()

    def disallow_overlay(self) -> None:
        self._allow_show_overlay = False
        self.hide_overlay()
    
    def is_overlay_allowed(self) -> bool:
        return self._allow_show_overlay

@dataclass
class ContinuousGraphState:
    acquiring:bool
    """We are subscribed to new data update. Data are being actively streamed by the server and points are logged"""
    paused:bool
    """Values are still streamed by the server and logged in memory but are not displayed on the graph allowing the user to inspect."""
    has_content:bool
    """Indicates that the graph is non-empty."""
    use_opengl:bool
    """Indicates that we are using opengl. Coming from an application wide parameter"""
    
    def autoscale_enabled(self) -> bool:
        return self.acquiring and not self.paused and self.has_content
    
    def has_non_moving_content(self) -> bool:
        if not self.has_content:
            return False
        
        if self.acquiring and not self.paused:
            return False
        
        return True
    
    def has_moving_content(self) -> bool:
        if not self.has_content:
            return False
        
        return self.acquiring and not self.paused
    
    def should_use_decimated_data(self) -> bool:
        return self.has_moving_content()

    def allow_save_csv(self) -> bool:
        return self.has_non_moving_content()

    def allow_save_image(self) -> bool:
        return self.has_non_moving_content()
    
    def allow_zoom(self) -> bool:
        return self.has_non_moving_content()

    def must_lock_signal_tree(self) -> bool:
        return self.has_content
    
    def require_flush_on_resolution_change(self) -> bool:
        return not self.paused
    
    def should_display_overlay(self) -> bool:
        return self.has_content
    
    def enable_clear_button(self) -> bool:
        return self.has_content and not self.acquiring

    def enable_pause_button(self) -> bool:
        return self.acquiring
    
    def enable_startstop_button(self) -> bool:
        return True
    
    def must_display_toolbar(self) -> bool:
        return self.has_non_moving_content()

    def allow_display_callout(self) -> bool:
        return self.has_non_moving_content()
    
    def enable_reset_zoom_button(self) -> bool:
        return self.has_content

    def enable_showhide_stats_button(self) -> bool:
        return self.has_content
    
    def enable_csv_logging_menu(self) -> bool:
        return not self.acquiring

class ContinuousGraphComponent(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("graph-96x128.png")
    _NAME = "Continuous Graph"

    DEFAULT_GRAPH_MAX_WIDTH=30
    MAX_SIGNALS=32
    Y_AXIS_MARGIN = 0.02
    
    _state:ContinuousGraphState
    """The state variable used to change the behavior of the component """
    _chartview:ScrutinyChartView
    """The QT chartview"""
    _chart_toolbar:ScrutinyChartToolBar
    """The toolbar that let the user control the zoom"""
    _callout:ScrutinyChartCallout
    """A callout (popup bubble) that shows the values on hover"""
    _signal_tree:GraphSignalTree
    """The right menu with axis and signal"""
    _btn_start_stop:QPushButton
    """The start/stop button"""
    _btn_pause:QPushButton
    """The Pause button"""
    _btn_clear:QPushButton
    """The "clear" button"""
    _spinbox_graph_max_width:QSpinBox
    """Spinbox to select the X-size of the graph in the GUI"""
    _csv_log_menu:CsvLoggingMenuWidget
    """The widget with all the configurations for the CSV logger"""
    _feedback_label:FeedbackLabel
    """A label to report error to the user"""
    _splitter:QSplitter
    """The splitter between the graph and the signal/axis tree"""
    _serverid2sgnal_item:Dict[str, ChartSeriesWatchableStandardItem]
    """A dictionnary mapping server_id associated with ValueUpdates broadcast by the server to their respective signal (a tree item, which has a reference to the chart series) """
    _callout_hide_timer:QTimer
    """A timer to trigger the hiding of the graph callout. Avoid fast show/hide"""
    _first_val_dt:Optional[datetime]
    """The server timestamp of the first value gotten. Used to offset the ValueUpdates timestamps to 0"""
    _graph_maintenance_timer:QTimer
    """A timer to periodically remove data and do some non-real time computation"""
    _graph_max_width:float
    """The maximum width of the X-Axis (max-min). Used to delete expired data"""
    _y_minmax_recompute_index:int
    """A persistent index used to recompute the minmax of all the Y serie sin round robin fashion. Used this index to reduce the CPU load by doing 1 series per call"""
    _x_resolution:float
    """The actual X resolution in sec. This value is given to the series decimator"""
    _stats:GraphStatistics
    """Graph statistics displayed to the user in real time"""
    _xaxis:ScrutinyValueAxisWithMinMax
    """The single time X-Axis"""
    _yaxes:List[ScrutinyValueAxisWithMinMax]
    """All the Y-Axes defined by the user"""
    _graph_sfd:Optional[sdk.SFDInfo]
    """The Scrutiny Firmware Description loaded when starting the acquisition"""
    _graph_device_info:Optional[sdk.DeviceInfo]
    """The details about the device when starting the acquisition"""
    _last_decimated_flush_paint_in_progress:bool
    """A flag indicated that the repaint event following a data flush has not been completed yet. 
    Used for auto-throttling of the repaint rate when the CPU is overloaded"""
    _csv_logger:Optional[CSVLogger]
    """The CSV logger that will save value update to disk in real time. Runs in the UI thread."""

    def setup(self) -> None:
        self._serverid2sgnal_item = {}
        self._xaxis = ScrutinyValueAxisWithMinMax(self)
        self._xaxis.setTitleText("Time [s]")
        self._xaxis.setTitleVisible(True)
        self._xaxis.deemphasize()   # Default state
        self._yaxes = []
        self._x_resolution = 0
        self._graph_sfd = None
        self._graph_device_info = None
        self._last_decimated_flush_paint_in_progress = False
        self._csv_logger = None
        self._first_val_dt = None
        self._y_minmax_recompute_index=0

        self._state = ContinuousGraphState(
            acquiring=False,
            paused=False,
            has_content=False,
            use_opengl=app_settings().opengl_enabled
        )
    
        
        def make_right_side() -> QWidget:
            right_side = QWidget()
            right_side_layout = QVBoxLayout(right_side)

            # Series on continuous graph don't have their X value aligned. 
            # We can only show the value next to each point, not all together in the tree
            self._signal_tree = GraphSignalTree(self, watchable_registry=self.watchable_registry, has_value_col=False)
            self._signal_tree.setMinimumWidth(150)
            self._signal_tree.signals.selection_changed.connect(self._selection_changed_slot)

            self._btn_start_stop = QPushButton("")
            self._btn_start_stop.clicked.connect(self._btn_start_stop_slot)
            self._btn_pause = QPushButton("Pause")
            self._btn_pause.clicked.connect(self._btn_pause_slot)
            self._btn_clear = QPushButton("Clear")
            self._btn_clear.clicked.connect(self._btn_clear_slot)
            
            param_widget = QWidget()
            param_layout = QFormLayout(param_widget)

            self._spinbox_graph_max_width = QSpinBox(self)
            self._spinbox_graph_max_width.setMaximum(600)
            self._spinbox_graph_max_width.setMinimum(0)
            self._spinbox_graph_max_width.setValue(self.DEFAULT_GRAPH_MAX_WIDTH)
            self._spinbox_graph_max_width.valueChanged.connect(self._spinbox_graph_max_width_changed_slot)
            self._spinbox_graph_max_width.setKeyboardTracking(False)

            param_layout.addRow("Graph width (s)", self._spinbox_graph_max_width)

            self._feedback_label = FeedbackLabel()
            self._feedback_label.text_label().setWordWrap(True)
            self._graph_maintenance_timer = QTimer()
            self._graph_maintenance_timer.setInterval(1000)
            self._graph_maintenance_timer.timeout.connect(self._graph_maintenance_timer_slot)
            self._csv_log_menu = CsvLoggingMenuWidget(self)

            start_pause_line = QWidget()
            start_pause_line_layout = QHBoxLayout(start_pause_line)
            start_pause_line_layout.setContentsMargins(0,0,0,0)
            start_pause_line_layout.addWidget(self._btn_start_stop)
            start_pause_line_layout.addWidget(self._btn_pause)

            right_side_layout.addWidget(self._signal_tree)
            right_side_layout.addWidget(self._csv_log_menu)
            right_side_layout.addWidget(param_widget)
            right_side_layout.addWidget(start_pause_line)
            right_side_layout.addWidget(self._btn_clear)
            right_side_layout.addWidget(self._feedback_label)

            return right_side

        def make_left_side() -> QWidget:
            chart = ScrutinyChart()
            chart.layout().setContentsMargins(0,0,0,0)
            chart.setAxisX(self._xaxis)
            self._stats = GraphStatistics(chart)
            self._stats.overlay().setPos(0,0)
            
            self._chartview = ScrutinyChartView(self)
            self._chartview.setChart(chart)
            self._chartview.signals.context_menu_event.connect(self._chart_context_menu_slot)
            self._chartview.signals.paint_finished.connect(self._paint_finished_slot)
            self._chartview.signals.zoombox_selected.connect(self._chartview_zoombox_selected_slot)
            self._chartview.signals.key_pressed.connect(self._chartview_key_pressed_slot)
            self._chartview.set_interaction_mode(ScrutinyChartView.InteractionMode.SELECT_ZOOM)

            self._chart_toolbar = ScrutinyChartToolBar(chart) 
            self._chart_toolbar.set_chartview(self._chartview)       
            
            self._callout = ScrutinyChartCallout(chart)
            self._callout_hide_timer = QTimer()
            self._callout_hide_timer.setInterval(250)
            self._callout_hide_timer.setSingleShot(True)
            self._callout_hide_timer.timeout.connect(self._callout_hide_timer_slot)

            left_side = QWidget()
            left_side_layout = QVBoxLayout(left_side)
            left_side_layout.setContentsMargins(0,0,0,0)
            left_side_layout.addWidget(self._chartview)

            return left_side
        
        
        right_side = make_right_side()
        left_side = make_left_side()

        self._splitter = QSplitter(self)
        self._splitter.setOrientation(Qt.Orientation.Horizontal)
        self._splitter.setContentsMargins(0,0,0,0)
        self._splitter.setHandleWidth(5)
        self._splitter.addWidget(left_side)
        self._splitter.addWidget(right_side)
        self._splitter.setCollapsible(0, False) # Cannot collapse the graph
        self._splitter.setCollapsible(1, True)  # Can collapse the right menu

        layout = QHBoxLayout(self)
        layout.addWidget(self._splitter)

        # App integration
        self.server_manager.signals.registry_changed.connect(self._registry_changed_slot)
        self.watchable_registry.register_watcher(self.instance_name, self._val_update_callback, self._unwatch_callback)
        self._apply_internal_state()
        
    def ready(self) -> None:
        """Called when the component is inside the dashboard and its dimensions are computed"""
        # Make the right menu as small as possible. Only works after the widget is loaded. we need the ready() function for that
        self._splitter.setSizes([self.width(), self._signal_tree.minimumWidth()])
        self._apply_internal_state()

    def teardown(self) -> None:
        """Called when the component is removed from the dashboard"""
        self.watchable_registry.unregister_watcher(self._watcher_id())

    def get_state(self) -> Dict[Any, Any]:
        """For dashboard save"""
        raise NotImplementedError("Not implemented")

    def load_state(self, state: Dict[Any, Any]) -> None:
        """For dashboard reload"""
        raise NotImplementedError("Not implemented")

    def visibilityChanged(self, visible:bool) -> None:
        """Called when the dashboard component is either hidden or showed"""
        self._chartview.setEnabled(visible)
            

    # region Controls
    def clear_graph(self) -> None:
        """Delete the graph content and reset the state to of the component to a vanilla state"""
        self._chartview.chart().removeAllSeries()
        self._callout.hide()
        self._clear_stats_and_hide()
        
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
        self._state.has_content = False
        self._first_val_dt = None
        self._graph_sfd = None
        self._graph_device_info = None
        self._last_decimated_flush_paint_in_progress = False
    
    def stop_acquisition(self) -> None:
        """Stop a an ongoing acquisition"""
        self._stop_periodic_graph_maintenance()     # Not required anymore 
        self.watchable_registry.unwatch_all(self._watcher_id()) # Stops to flow of values
        self._state.acquiring = False
        self._state.paused = False
        
        if self._csv_logger is not None:
            self._csv_logger.stop()
            self._csv_logger = None
        
        if not self._feedback_label.is_error():
            self._feedback_label.clear()    # Remove CSV saving message

        self._chartview.setDisabled(True)   # Disable while we do lots of operations on the graph 

        for series in self._all_series():
            series.stop_decimator()         # Flush pending data to the output. Not necessary, future proofing here
            series.flush_full_dataset()     # When stopped, the user wants to see everything.CPU can handle a single draw. Require all data for CSV export.
        
        self._recompute_xaxis_minmax_and_delete_old_data()              # Doesn't change the range, just finds the min/max
        self._round_robin_recompute_single_series_min_max(full=True)    # Update a single series at a time to reduce the load on the CPU
        self._update_yaxes_minmax_based_on_series_minmax()              # Recompute min/max. Only way to shrink the scale reliably.

        self.disable_repaint_rate_measurement()
        self._chartview.setEnabled(True)
        self._maybe_enable_opengl_drawing(False)    # Required for callout to work
        self._apply_internal_state()

    def start_acquisition(self) -> None:
        """Start a graph acquisition"""
        if self._state.acquiring:
            return
        
        if self._spinbox_graph_max_width.value() == 0:
            self._report_error("Invalid graph width")
            return 
        
        self._graph_max_width = float(self._spinbox_graph_max_width.value())    # User input
        try:
            self.clear_graph()
            signals = self._signal_tree.get_signals()   # Read the tree on the right menu
            if len(signals) == 0:
                self._report_error("No signals")
                return
        
            if len(signals) > self.MAX_SIGNALS:
                self._report_error(f"Too many signals. Max={self.MAX_SIGNALS}")
                return
            
            self._xaxis.setRange(0, 1)
            for axis in signals:    # For each axes
                yaxis = ScrutinyValueAxisWithMinMax(self)
                axis.axis_item.attach_axis(yaxis)
                yaxis.setTitleText(axis.axis_name)
                yaxis.setTitleVisible(True)
                self._yaxes.append(yaxis)
                self._chartview.chart().addAxis(yaxis, Qt.AlignmentFlag.AlignRight)
                
                for signal_item in axis.signal_items:   # For each watchable under that axis
                    try:
                        # We will use that server ID to lookup the right chart series on value update broadcast by the server
                        server_id = self.watchable_registry.watch_fqn(self._watcher_id(), signal_item.fqn)
                    except WatchableRegistryNodeNotFoundError as e:
                        self._report_error(f"Signal {signal_item.text()} is not available.")
                        self.watchable_registry.unwatch_all(self._watcher_id())
                        self.clear_graph()
                        return
                    
                    series = RealTimeScrutinyLineSeries(self)
                    self._chartview.chart().addSeries(series)
                    signal_item.attach_series(series)
                    signal_item.show_series()
                    self._serverid2sgnal_item[server_id] = signal_item  # The main lookup
                    series.setName(signal_item.text())
                    series.attachAxis(self._xaxis)
                    series.attachAxis(yaxis)

                    # Click is used to make a line bold when we click. # Hovered to display a callout (only when the graph paused/stopped)
                    series.clicked.connect(functools.partial(self._series_clicked_slot, signal_item))
                    series.hovered.connect(functools.partial(self._series_hovered_slot, signal_item))

            # Latch the device details and loaded SFD so that we can write the info into CSV output, even if it disconnect during the acquisition
            self._graph_sfd = self.server_manager.get_loaded_sfd()
            self._graph_device_info = self.server_manager.get_device_info()

            # Create the continuous CSV logger if required
            self._csv_logger = None
            if self._csv_log_menu.require_csv_logging():
                try:
                    self._csv_logger = self._csv_log_menu.make_csv_logger(logging_logger=self.logger)
                    self._configure_and_start_csv_logger()
                    gui_preferences.global_namespace().set_last_save_dir(self._csv_logger.get_folder())
                except Exception as e:
                    self._csv_logger = None
                    self._report_error(f"Cannot start CSV logging. {e}" )
                    self.watchable_registry.unwatch_all(self._watcher_id())
                    self.clear_graph()
                    return
                
            # Everything went well. Update state variables
            self._state.has_content = True
            self._state.paused = False
            self._state.acquiring = True

            self._first_val_dt = None
            self._last_decimated_flush_paint_in_progress=False
            self._maybe_enable_opengl_drawing(True)   # Reduce CPU usage a lot
            self._change_x_resolution(0)    # 0 mean no decimation
            self.update_emphasize_state()
            self.enable_repaint_rate_measurement()
            
            self._start_periodic_graph_maintenance()
            self._clear_feedback()
            self._apply_internal_state()
            self.show_stats()
        except Exception as e:
            tools.log_exception(self.logger, e, "Failed to start the acquisition")
            self.stop_acquisition()
    
    def pause(self) -> None:
        """Pause the real time graph. Flush non-decimated background data buffer to the QChart and prevent further updates."""
        if self._state.paused:
            return 
        
        for series in self._all_series():
            series.flush_full_dataset()
        self.disable_repaint_rate_measurement()
        self._maybe_enable_opengl_drawing(False)
        self._latch_all_axis_range()
        self._state.paused=True
        self._apply_internal_state()

    def unpause(self) -> None:
        """Unpause the real time graph. Flush decimated background data buffer to the QChart and update periodically"""
        if not self._state.paused:
            return
            
        for series in self._all_series():
            series.flush_decimated()
        self._last_decimated_flush_paint_in_progress = True
        self.enable_repaint_rate_measurement()
        self._maybe_enable_opengl_drawing(True)
        self._state.paused=False
        self._apply_internal_state()

    def update_emphasize_state(self) -> None:
        """Read the items in the SignalTree object (right menu with axis) and update the size/boldness of the graph series
        based on wether they are selected or not"""
        emphasized_yaxes_id:Set[int] = set()
        selected_index = self._signal_tree.selectedIndexes()
        for item in self._serverid2sgnal_item.values():
            if item.series_attached():
                series = self._get_item_series(item)
                if item.index() in selected_index:
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

    def auto_scale_xaxis(self) -> None:
        """Sets the scale of the X-Axis based on the save min/max"""
        max_x = self._xaxis.maxval()
        min_x = self._xaxis.minval()
        if max_x is not None and min_x is not None:
            if max_x > min_x + self._graph_max_width:
                min_x = max_x - self._graph_max_width
            if max_x == min_x :
                self._xaxis.setRange(min_x, max_x+1)
            else:
                self._xaxis.setRange(min_x, max_x)
    
    #endregion Control

    # region Internal

    def _latch_all_axis_range(self) -> None:
        self._xaxis.latch_range()
        for yaxis in self._yaxes:
            yaxis.latch_range()
    
    def _reload_all_latched_ranges(self) -> None:
        self._xaxis.reload_latched_range()
        for yaxis in self._yaxes:
            yaxis.reload_latched_range()

    def _configure_and_start_csv_logger(self) -> None:
        """Start the CSV logger. Will accept incoming value update afterward. Expect that the CSV logger object is created beforehand"""
        self.logger.debug("Trying to start the CSV logger")
        assert self._csv_logger is not None
        columns:List[CSVLogger.ColumnDescriptor] = []

        # Reverse lookup of the server id / item map.
        # We do that just so the columns in the CSV file is in the same order as the right menu
        # Right-click -> Save to CSV also follow the same ordering. We want the 2 CSV files to be identical
        def get_server_id_from_signal_item(arg:ChartSeriesWatchableStandardItem) -> str:
            for server_id, item in self._serverid2sgnal_item.items():
                if item is arg:
                    return server_id
            raise KeyError(f"Could not find the server ID for item: {arg.text()}")
        
        # Creates the list of columns following the same order has the export_to_csv feature
        signals = self._signal_tree.get_signals()
        for axis in signals:
            for signal_item in axis.signal_items:
                columns.append(CSVLogger.ColumnDescriptor(
                    server_id=get_server_id_from_signal_item(signal_item),
                    name=signal_item.text(),
                    fullpath=signal_item.fqn
                ))

        columns.sort(key=lambda x:x.name)
        self._csv_logger.define_columns(columns)
        self._csv_logger.set_file_headers(make_csv_headers(device=self._graph_device_info, sfd=self._graph_sfd))
        self._csv_logger.start()


    def _registry_changed_slot(self) -> None:
        """Called when the server manager has finished making a change to the registry"""
        self._signal_tree.update_all_availabilities()
        if self._state.acquiring and self._signal_tree.has_unavailable_signals():
            # If a we loose a signal while acquiring, stop everything.
            self.stop_acquisition()

    def _flush_decimated_to_dirty_series(self) -> None:
        """Flush the decimated data buffer of all series marked as dirty. They're dirty when new data is available in 
        the decimator decimated buffer (not the input buffer)"""
        for series in self._all_series():
            if series.is_dirty():
                series.flush_decimated()
                self._last_decimated_flush_paint_in_progress = True

    def _get_item_series(self, item:ChartSeriesWatchableStandardItem) -> RealTimeScrutinyLineSeries:
        """Return the series tied to a Tree Item (right menu)"""
        return cast(RealTimeScrutinyLineSeries, item.series())
    
    def _get_series_yaxis(self, series:RealTimeScrutinyLineSeries) -> ScrutinyValueAxisWithMinMax:
        """Return the Y-Axis tied to a series"""
        return cast(ScrutinyValueAxisWithMinMax, self._chartview.chart().axisY(series))
    
    def _all_series(self) -> Generator[RealTimeScrutinyLineSeries, None, None]:
        """Return the list of all series in the graph"""
        for item in self._serverid2sgnal_item.values():
            yield self._get_item_series(item)

    def _maybe_enable_opengl_drawing(self, val:bool) -> None:
        """Enable OpenGL drawing for real time graph, only if the app is running with OpenGL enabled"""
        if self._state.use_opengl:
            for series in self._all_series():
                series.setUseOpenGL(val)
            # Forces redraw.
            self._chartview.setDisabled(True)
            self._chartview.setDisabled(False)

    def _change_x_resolution(self, resolution:float) -> None:
        """Change the decimator resolution of all series, directly affecting the decimation factor."""
        self._x_resolution = resolution
        for series in self._all_series():
            series.set_x_resolution(resolution)
        if self._state.require_flush_on_resolution_change():
            self._flush_decimated_to_dirty_series()
        self.update_stats()

    def enable_repaint_rate_measurement(self) -> None:
        self._stats.repaint_rate.enable()
    
    def disable_repaint_rate_measurement(self) -> None:
        self._stats.repaint_rate.disable()

    def update_stats(self) -> None:
        """Update the stats displayed at the top left region of the graph
        :param use_decimated: When ``True``, the decimated buffer is used. When ``False``
            the full dataset is used, giving an effective decimation ratio of 1x and no points hidden.
        """
        self._stats.repaint_rate.update()
        self._stats.opengl = self._state.use_opengl
        self._stats.decimation_factor = 0
        self._stats.visible_points = 0
        self._stats.total_points = 0
        all_series = list(self._all_series())
        if self._state.should_use_decimated_data():
            # The decimator is active, we want to show stats about the decimated dataset to the user
            nb_series = len(all_series)
            if nb_series > 0:
                per_series_weight = 1/nb_series
                for series in all_series:
                    self._stats.decimation_factor += series.decimation_factor() * per_series_weight
                    self._stats.visible_points+=series.count_decimated_points()
                    self._stats.total_points+=series.count_all_points()
        else:
            # The decimator is not active (graph paused or stopped). We're showing the full dataset
            self._stats.decimation_factor = 1               # No points hidden
            total_points = 0
            for series in all_series:
                total_points  += series.count_all_points()  # No points hidden
            self._stats.visible_points = total_points       # No points hidden
            self._stats.total_points = total_points         # No points hidden

        if self._state.should_display_overlay():
            self._stats.update_overlay()

    def _clear_stats_and_hide(self)->None:
        """Make the stats overlay go away and reset all the numbers to their default value"""
        self._stats.clear()
        self._stats.hide_overlay()
    
    def show_stats(self) -> None:
        """Display the stats overlay"""
        self._stats.show_overlay()

    def _apply_internal_state(self) -> None:
        """Update all the widgets based on our internal state variables"""
        if self._state.acquiring:
            self._btn_start_stop.setText("Stop")
        else:
            self._btn_start_stop.setText("Start")

        if self._state.paused:
            self._btn_pause.setText("Unpause")
        else:
            self._btn_pause.setText("Pause")
        
        self._btn_start_stop.setEnabled(self._state.enable_startstop_button())
        self._btn_pause.setEnabled(self._state.enable_pause_button())
        self._btn_clear.setEnabled(self._state.enable_clear_button())
        self._chartview.allow_zoom(self._state.allow_zoom())
        self._csv_log_menu.setEnabled(self._state.enable_csv_logging_menu())
        self.update_stats()


        if self._state.must_lock_signal_tree():
            self._signal_tree.lock()
        else:
            self._signal_tree.unlock()

        if self._state.must_display_toolbar():
            self._chart_toolbar.show()
        else:
            self._chart_toolbar.hide()


    def _watcher_id(self) -> str:
        return self.instance_name
    
    def _report_error(self, msg:str) -> None:
        self._feedback_label.set_error(msg)

    def _report_info(self, msg:str) -> None:
        self._feedback_label.set_info(msg)
    
    def _clear_feedback(self) -> None:
        self._feedback_label.clear()

    def _val_update_callback(self, watcher_id:Union[str, int], value_updates:List[ValueUpdate]) -> None:
        """Invoked when we have new data available"""
        if not self._state.has_content: # We don't check for acquiring just in case an extra value was in transit when we stop.
            self.logger.error("Received value updates when no graph was ready")
            return 
        
        if self._first_val_dt is None:
            self._first_val_dt = value_updates[0].update_timestamp   # precise to the microsecond. Coming from the server

        tstart = self._first_val_dt
        def get_x(val:ValueUpdate) -> float:    # A getter to get the relative timestamp
            return  (val.update_timestamp-tstart).total_seconds()
        
        if self._csv_logger is not None:
            try:
                self._csv_logger.write(value_updates)
            except Exception as e:

                tools.log_exception(self.logger, e, "CSV logger failed to write")
                self._report_error(f"Error while logging CSV. \n {e}")
                self._csv_logger.stop()
                self._csv_logger = None

        try:
            for value_update in value_updates:
                xval = get_x(value_update)
                yval = float(value_update.value)
                
                series = self._get_item_series(self._serverid2sgnal_item[value_update.watchable.server_id]) 
                yaxis = self._get_series_yaxis(series)
                series.add_point(QPointF(xval, yval))
                self._xaxis.update_minmax(xval)
                yaxis.update_minmax(yval)   # Can only grow
                if self._state.autoscale_enabled():
                    yaxis.autoset_range(margin_ratio=self.Y_AXIS_MARGIN)
            
            if self._state.autoscale_enabled():
                self.auto_scale_xaxis()

            if not self._state.paused and not self._last_decimated_flush_paint_in_progress:
                self._flush_decimated_to_dirty_series()

        except KeyError as e:
            tools.log_exception(self.logger, e, "Received a value update from a watchable that maps to no valid series in the chart")
            self.stop_acquisition()
        except Exception as e:
            tools.log_exception(self.logger, e, f"Error when receiving data for the chart")
            self.stop_acquisition()

            
    def _unwatch_callback(self, watcher_id:Union[str, int], server_path:str, watchable_config:sdk.WatchableConfiguration) -> None:
        # Should we do something? User feedback if the watcahble is not available anymore maybe?
        pass
    
    def _start_periodic_graph_maintenance(self) -> None:
        self._y_minmax_recompute_index=0
        self._graph_maintenance_timer.start()
    
    def _stop_periodic_graph_maintenance(self) -> None:
        self._graph_maintenance_timer.stop()

    def _round_robin_recompute_single_series_min_max(self, full:bool) -> None:
        """Compute a series min/max values. 
        if full=``False``, does only 1 series per call to reduce the load on the CPU. Does all if full=``True``"""
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
        allseries = list(self._all_series())
        for yaxis in self._yaxes:
            yaxis.clear_minmax()
            for series in allseries:
                if id(yaxis) in [id(axis) for axis in series.attachedAxes()]:
                    minv, maxv = series.y_min(), series.y_max()
                    if minv is not None:
                        yaxis.update_minmax(minv)
                    if maxv is not None:
                        yaxis.update_minmax(maxv)


    def _compute_new_decimator_resolution(self) -> None:
        """Compute a decimator resolution to have ~1pt per pixel. Maybe a little more to spare the CPU."""
        w = self._chartview.chart().size().width()
        xspan = self._xaxis.max() - self._xaxis.min()
        sec_per_pixel = xspan/w
        resolution = 2*sec_per_pixel        # When full, the decimator produces 2 points per time slice. (min/max
        resolution = 1.5*resolution         # Heuristic to reduce the CPU load. Result is visually acceptable
        resolution = round(resolution, 2)   # Avoid constantly recomputing the decimated data
        self._change_x_resolution(resolution)

    def _recompute_xaxis_minmax_and_delete_old_data(self) -> None:
        """Delete old data, then recompute the X-Axis min/max values without touching the effective chart range"""
        # X axis maintenance (span shrink)
        new_max_f = -math.inf
        
        for series in self._all_series():
            last_x = series.get_last_x()
            if last_x is None:
                continue    # Means serie sis empty.
            new_max_f = max(new_max_f, last_x)
        
        if not math.isfinite(new_max_f):
            return
        
        new_min_x = math.inf
        lower_x_bound_for_deletion = new_max_f - self._graph_max_width  # wanted lower bound
        for series in self._all_series():
            series.delete_up_to_x_without_flushing(lower_x_bound_for_deletion)   # Does not affect the chart. Just the internal buffer
            first_x = series.get_first_x()

            if first_x is not None:
                new_min_x = min(new_min_x, first_x) # Reduce the axis lower bound to the series lower bound

        if math.isfinite(new_min_x):
            self._xaxis.set_minval(new_min_x)
            self._xaxis.set_maxval(new_max_f)

    # endregion Internal

    # region SLOTS
    def _chartview_key_pressed_slot(self, event:QKeyEvent) -> None:
        """Chartview Event forwarded through a signal"""
        if event.key() == Qt.Key.Key_Escape:
            self._signal_tree.clearSelection()

    def _chartview_zoombox_selected_slot(self, zoombox:QRectF) -> None:
        """When the chartview emit a zoombox_selected signal. Coming from either a wheel event or a selection of zoom with a rubberband"""
        if not self._state.allow_zoom():
            return 
        self._callout.hide()

        # When we are paused, we want the zoom to stay within the range of that was latched when pause was called.
        # When not pause, saturate to min/max values
        saturate_to_latched_range = True if self._state.paused else False   
        self._xaxis.apply_zoombox_x(zoombox, saturate_to_latched_range=saturate_to_latched_range)
        selected_axis_items = self._signal_tree.get_selected_axes(include_if_signal_is_selected=True)
        selected_axis_ids = [id(item.axis()) for item in selected_axis_items]
        for yaxis in self._yaxes:
            if id(yaxis) in selected_axis_ids or len(selected_axis_ids) == 0:
                yaxis.apply_zoombox_y(
                    zoombox, 
                    margin_ratio=self.Y_AXIS_MARGIN, 
                    saturate_to_latched_range=saturate_to_latched_range
                    )
        
    def _reset_zoom_slot(self) -> None:
        """Right-click -> Reset zoom"""
        self._callout.hide()
        if self._state.paused:
            # Latched when paused. guaranteed to be unzoomed because zoom is not allowed when not
            self._reload_all_latched_ranges()
        else:
            self._xaxis.autoset_range()
            for yaxis in self._yaxes:
                yaxis.autoset_range(margin_ratio=self.Y_AXIS_MARGIN)


    def _paint_finished_slot(self) -> None:
        """Used to throttle the update rate if the CPU can't follow. Prevent any chart update while repaint is in progress"""
        self._stats.repaint_rate.add_data(1)

        def set_paint_not_in_progress() -> None:
            self._last_decimated_flush_paint_in_progress = False
            if not self._state.paused:
                self._flush_decimated_to_dirty_series()

        InvokeQueued(set_paint_not_in_progress)

    def _btn_clear_slot(self) -> None:
        """Slot when "clear" is clicked"""
        self.clear_graph()
        self._clear_feedback()
        self._apply_internal_state()

    def _btn_pause_slot(self) -> None:
        """Slot when "pause" is clicked"""
        if self._state.paused:           
            self.unpause()
        else:
            self.pause()

    def _btn_start_stop_slot(self) -> None:
        """Slot when "start/stop" is clicked"""
        if self._state.acquiring:           
            self.stop_acquisition()
        else:
            self.start_acquisition()
    
    def _selection_changed_slot(self) -> None:
        """Whent he user selected/deselected a signal in the right menu"""
        self.update_emphasize_state()
        
    def _series_clicked_slot(self, signal_item:ChartSeriesWatchableStandardItem, point:QPointF) -> None:
        """When the user clicked a line on the graph. We make it bold and select the matching item in the right menu"""
        sel = self._signal_tree.selectionModel()
        sel.select(signal_item.index(), QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)

    def _graph_maintenance_timer_slot(self) -> None:
        """Periodic callback meant to prune the graph and recompute the rang eof the axis.
        Done periodically to reduce the strain on the CPU"""
        if not self._state.acquiring:
            return

        self._compute_new_decimator_resolution()
        self._recompute_xaxis_minmax_and_delete_old_data()
        
        all_series = list(self._all_series())
        nb_series = len(all_series)
        nb_loop = nb_series//6+1    # If there is lot of series, we update more at the time. Axes will reduce their range in max 6 second because of this
        for i in range(nb_loop):
            self._round_robin_recompute_single_series_min_max(full=False) # Update a single series at a time to reduce the load on the CPU
            self._update_yaxes_minmax_based_on_series_minmax()  # Recompute min/max. Only way to shrink the scale reliably.
        self.update_stats()    # Recompute the stats and display

        if self._csv_logger is not None:
            filepath = self._csv_logger.get_actual_filename()
            if filepath is not None:
                self._report_info(f"Writing: {filepath.name}")

    def _series_hovered_slot(self, signal_item:ChartSeriesWatchableStandardItem, point:QPointF, state:bool) -> None:
        """Called by QtChart when the mouse is over a point of a series. state=``True`` when the mouse enter the point. ``False`` when it leaves"""
        # FIXME : Snap zone is too small. QT source code says it is computed with markersize, but changing it has no effect.
        must_show = state
        if not self._state.allow_display_callout():
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
        """When the user changed the max width spinbox"""
        if val == 0:
            self._spinbox_graph_max_width.setProperty("state", WidgetState.error)
            return
        self._spinbox_graph_max_width.setProperty("state", WidgetState.default)
        
        self._graph_max_width = val
        if self._state.autoscale_enabled():
            self.auto_scale_xaxis()
        
        # QT Selects the textbox when the value is changed. We add a clear action at the end of the event loop
        def deselect_spinbox() -> None:
            child = cast(Optional[QLineEdit], self._spinbox_graph_max_width.findChild(QLineEdit))
            if child is not None:
                child.deselect()
                child.clearFocus()
        InvokeQueued(deselect_spinbox)

    def _chart_context_menu_slot(self, chartview_event:QContextMenuEvent) -> None:
        """Slot called when the user right click the chartview. Create a context menu and display it.
        This event is forwarded by the chartview through a signal."""
        context_menu = QMenu(self)

        save_img_action = context_menu.addAction(assets.load_tiny_icon(assets.Icons.Image), "Save as image")
        save_img_action.triggered.connect(self._save_image_slot)
        save_img_action.setEnabled(self._state.allow_save_image())

        save_csv_action = context_menu.addAction(assets.load_tiny_icon(assets.Icons.CSV), "Save as CSV")
        save_csv_action.triggered.connect(self._save_csv_slot)
        save_csv_action.setEnabled(self._state.allow_save_csv())

        reset_zoom_action = context_menu.addAction(assets.load_tiny_icon(assets.Icons.Zoom100), "Reset zoom")
        reset_zoom_action.triggered.connect(self._reset_zoom_slot)
        reset_zoom_action.setEnabled(self._state.enable_reset_zoom_button())
        
        if self._stats.is_overlay_allowed():
            show_hide_stats = context_menu.addAction(assets.load_tiny_icon(assets.Icons.EyeBar), "Hide stats")
            show_hide_stats.triggered.connect(self._stats.disallow_overlay)
        else:
            show_hide_stats = context_menu.addAction(assets.load_tiny_icon(assets.Icons.Eye), "Show stats")
            show_hide_stats.triggered.connect(self._stats.allow_overlay)
        
        show_hide_stats.setEnabled(self._state.enable_showhide_stats_button())            
        
        context_menu.popup(self._chartview.mapToGlobal(chartview_event.pos()))

    def _save_image_slot(self) -> None:
        """When the user right-click the graph then click "Save as image" """
        if not self._state.allow_save_image():
            return 
        
        filepath:Optional[Path] = None
        try:
            pix = self._chartview.grab()
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

        filepath = prompt.get_save_filepath_from_last_save_dir(self, ".csv")
        if filepath is None:
            return
        
        def finished_callback(exception:Optional[Exception]) -> None:
            # This runs in a different thread
            # Todo : Add visual "saving..." feedback ?
            if exception is not None:
                tools.log_exception(self.logger, exception, f"Error while saving graph into {filepath}" )
                InvokeInQtThread(lambda: prompt.exception_msgbox(self, exception, "Failed to save", f"Failed to save the graph to {filepath}"))

        export_chart_csv_threaded(
            datetime_zero_sec = self._first_val_dt,
            filename = filepath, 
            signals = self._signal_tree.get_signals(), 
            finished_callback = finished_callback,
            device = self._graph_device_info,
            sfd = self._graph_sfd
            )


    #endregion
