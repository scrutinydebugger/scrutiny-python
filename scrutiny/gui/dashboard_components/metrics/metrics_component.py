#    metrics_component.py
#        A component used to display the internal operating metrics
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from typing import Dict,Any, Optional

from PySide6.QtWidgets import QVBoxLayout, QPushButton, QSizePolicy
from PySide6.QtCore import  QTimer, Qt
from scrutiny.gui.widgets.app_stats_display import ApplicationStatsDisplay
from scrutiny.gui import assets
from scrutiny.sdk.client import ScrutinyClient
from scrutiny import sdk


class MetricsComponent(ScrutinyGUIBaseComponent):
    _ICON = assets.get("stopwatch-96x128.png")
    _NAME = "Internal Metrics"

    app_stats:ApplicationStatsDisplay

    def setup(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.app_stats = ApplicationStatsDisplay(self)
        self.app_stats.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.app_stats)
        
        self.reset_btn = QPushButton(self)
        self.reset_btn.setText("Reset local values")
        self.reset_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.reset_btn.clicked.connect(self.btn_reset_click)
        layout.addWidget(self.reset_btn)
        
        self.server_manager.signals.server_connected.connect(self.server_connected_slot)
        self.server_manager.signals.server_disconnected.connect(self.server_disconnected_slot)
        self.local_data_timer = QTimer()
        self.local_data_timer.setInterval(200)
        self.local_data_timer.timeout.connect(self.local_stats_timer_timeout)
        self.local_data_timer.start()

        self.server_data_timer = QTimer()
        self.server_data_timer.setSingleShot(True)
        self.server_data_timer.setInterval(200)
        self.server_data_timer.timeout.connect(self.server_stats_timer_timeout)

        self.app_stats.clear_server_labels()
        if self.server_manager.get_server_state() == sdk.ServerState.Connected:
            self.server_data_timer.start()

    
    def server_connected_slot(self) -> None:
        self.server_data_timer.start()

    def server_disconnected_slot(self) -> None:
        self.app_stats.clear_server_labels()
        self.server_data_timer.stop()


    def local_stats_timer_timeout(self) -> None:
        self.app_stats.update_local_data(self.server_manager.get_stats())


    def server_stats_timer_timeout(self) -> None:
        def threaded_get_stats(client:ScrutinyClient) -> sdk.ServerStatistics:
            return client.get_server_stats()
        
        def ui_callback(stats:Optional[sdk.ServerStatistics], exception:Optional[Exception]) -> None:
            if stats is not None:
                self.app_stats.update_server_data(stats)
            
            if exception is not None:
                if self.server_manager.get_server_state() == sdk.ServerState.Connected:
                    self.logger.error(str(exception))
            
            if self.server_manager.get_server_state() == sdk.ServerState.Connected:
                self.server_data_timer.start()

        self.server_manager.schedule_client_request(threaded_get_stats, ui_callback)

    def btn_reset_click(self) -> None:
        self.server_manager.reset_stats()

    def teardown(self) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        return {}

    def load_state(self, state:Dict[Any, Any]) -> None:
        pass
