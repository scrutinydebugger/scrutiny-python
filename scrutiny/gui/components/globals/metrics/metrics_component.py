#    metrics_component.py
#        A dashboard component that shows internal metrics for debugging purpose
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['MetricsComponent']

from PySide6.QtWidgets import QVBoxLayout, QPushButton, QSizePolicy
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon

from scrutiny import sdk
from scrutiny.sdk.client import ScrutinyClient

from scrutiny.gui.components.globals.base_global_component import ScrutinyGUIBaseGlobalComponent
from scrutiny.gui.widgets.app_stats_display import ApplicationStatsDisplay
from scrutiny.gui import assets
from scrutiny.gui.themes import scrutiny_get_theme

from scrutiny.tools.typing import *
from scrutiny import tools


class MetricsComponent(ScrutinyGUIBaseGlobalComponent):
    _NAME = "Internal Metrics"
    _TYPE_ID = "metrics"

    _app_stats: ApplicationStatsDisplay
    """ The widget showing the stats"""
    _local_reset_btn: QPushButton
    """ Button that reset local measurements"""
    _local_data_timer: QTimer
    """Timer used to update periodically the local stats"""
    _server_data_timer: QTimer
    """Timer used to send periodic requests to the server"""
    _visible: bool
    """State variable telling if we are presently visible or not"""
    _server_connected: bool
    """State variable telling if the server is presently connected"""

    @classmethod
    def get_icon(cls) -> QIcon:
        return scrutiny_get_theme().load_medium_icon(assets.Icons.StopWatch)

    def setup(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._app_stats = ApplicationStatsDisplay(self)
        self._app_stats.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        layout.addWidget(self._app_stats)

        self._local_reset_btn = QPushButton(self)
        self._local_reset_btn.setText("Reset local values")
        self._local_reset_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self._local_reset_btn.clicked.connect(self._btn_reset_local_click_slot)
        layout.addWidget(self._local_reset_btn)

        self.server_manager.signals.server_connected.connect(self._server_connected_slot)
        self.server_manager.signals.server_disconnected.connect(self._server_disconnected_slot)
        self._local_data_timer = QTimer()
        self._local_data_timer.setInterval(200)
        self._local_data_timer.timeout.connect(self._local_stats_timer_timeout)

        self._server_data_timer = QTimer()
        self._server_data_timer.setSingleShot(True)
        self._server_data_timer.setInterval(200)
        self._server_data_timer.timeout.connect(self._server_stats_timer_timeout)

        self._app_stats.clear_server_labels()
        self._server_connected = (self.server_manager.get_server_state() == sdk.ServerState.Connected)
        self._visible = False

    def visibilityChanged(self, visible: bool) -> None:
        self._visible = visible
        self._update()

    def teardown(self) -> None:
        self._local_data_timer.stop()
        self._server_data_timer.stop()

    def get_state(self) -> Dict[Any, Any]:
        return {}

    def load_state(self, state: Dict[Any, Any]) -> bool:
        return True

    def _update(self) -> None:
        """Manage the UI and the timers based on the state variables"""
        if not self._visible:
            self._local_data_timer.stop()
            self._server_data_timer.stop()
            self._app_stats.clear_server_labels()
        else:
            if not self._local_data_timer.isActive():
                self._local_data_timer.start()

            if self._server_connected:
                if not self._server_data_timer.isActive():
                    self._server_data_timer.start()
            else:
                self._app_stats.clear_server_labels()

# region Slots
    def _server_connected_slot(self) -> None:
        self._server_connected = True
        self._update()

    def _server_disconnected_slot(self) -> None:
        self._server_connected = False
        self._update()

    def _local_stats_timer_timeout(self) -> None:
        self._app_stats.update_local_data(self.server_manager.get_stats())

    def _server_stats_timer_timeout(self) -> None:
        def threaded_get_stats(client: ScrutinyClient) -> sdk.ServerStatistics:
            return client.get_server_stats()

        def ui_callback(stats: Optional[sdk.ServerStatistics], exception: Optional[Exception]) -> None:
            if stats is not None:
                self._app_stats.update_server_data(stats)

            if exception is not None:
                if self.server_manager.get_server_state() == sdk.ServerState.Connected:  # Suppresses errors when the server is gone.
                    tools.log_exception(self.logger, exception, "Failed to read the server metrics")

            self._update()  # Will relaunch the server timer if necessary

        self.server_manager.schedule_client_request(threaded_get_stats, ui_callback)

    def _btn_reset_local_click_slot(self) -> None:
        self.server_manager.reset_stats()

# endregion
