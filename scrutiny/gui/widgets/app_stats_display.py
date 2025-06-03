#    app_stats_display.py
#        A widget to display the application stats
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = ['ApplicationStatsDisplay']

from PySide6.QtWidgets import QWidget, QFormLayout, QLabel, QGroupBox, QVBoxLayout
from PySide6.QtCore import Qt
from scrutiny import sdk
from scrutiny.gui.core.server_manager import ServerManager
from scrutiny.tools import format_eng_unit, format_sec_to_dhms
from scrutiny.tools.typing import *


def _configure_property_label(label: QLabel, has_tooltip: bool) -> None:
    if has_tooltip:
        label.setCursor(Qt.CursorShape.WhatsThisCursor)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)


def _configure_value_label(label: QLabel) -> None:
    label.setCursor(Qt.CursorShape.IBeamCursor)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)


class DisplayTable(QWidget):
    """A table of properties/value. One per section displayed in DeviceInfoDialog"""
    form_layout: QFormLayout

    def __init__(self) -> None:
        super().__init__()
        self.form_layout = QFormLayout(self)
        self.form_layout.setFormAlignment(Qt.AlignmentFlag.AlignVCenter)

    def add_row(self, label_txt: str, item: Union[str, QWidget], tooltip: Optional[str] = None) -> QLabel:
        label = QLabel(label_txt)
        has_tooltip = True if tooltip is not None else False
        _configure_property_label(label, has_tooltip=has_tooltip)
        if tooltip is not None:
            label.setToolTip(tooltip)
        if isinstance(item, str):
            item = QLabel(item)

        if isinstance(item, QLabel):
            _configure_value_label(item)

        is_odd = self.form_layout.rowCount() % 2 == 0    # Check for 0 because we evaluate for next node
        odd_even = "odd" if is_odd else "even"
        label.setProperty("table_odd_even", odd_even)
        item.setProperty("table_odd_even", odd_even)

        self.form_layout.addRow(label, item)
        assert isinstance(item, QLabel)
        return item


class ApplicationStatsDisplay(QWidget):
    client_rx_data_label: QLabel
    client_tx_data_label: QLabel
    status_update_count_label: QLabel

    listener_update_count_label: QLabel
    listener_drop_count_label: QLabel
    listener_update_per_sec_label: QLabel
    listener_internal_qsize_label: QLabel
    listener_gui_qsize_label: QLabel
    listener_event_rate_label: QLabel

    registry_var_count_label: QLabel
    registry_alias_count_label: QLabel
    registry_rpv_count_label: QLabel
    registry_watcher_count_label: QLabel
    registry_watched_entries_label: QLabel

    server_uptime_label: QLabel
    server_invalid_request_count_label: QLabel
    server_unexpected_error_count_label: QLabel
    server_client_count_label: QLabel
    server_api_tx_datarate_label: QLabel
    server_api_rx_datarate_label: QLabel
    server_msg_received_label: QLabel
    server_msg_sent_label: QLabel
    server_device_session_count_label: QLabel
    server_device_datarate_byte_per_sec_label: QLabel
    server_device_datarate_up_down_ratio_label: QLabel

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        client_table = self.add_section_table("Client")
        self.client_rx_data_label = client_table.add_row("Rx data", "", "Inbound data rate")
        self.client_tx_data_label = client_table.add_row("Tx data", "", "Outbound data rate")
        self.status_update_count_label = client_table.add_row("Status update count", "", "Number of status update received from the server")

        listener_table = self.add_section_table("Listener")
        self.listener_update_count_label = listener_table.add_row(
            "Total update received", "", "Total number of value update received from the server")
        self.listener_drop_count_label = listener_table.add_row(
            "Total update dropped", "", "Number of value update dropped because of queue overflow. Expect 0")
        self.listener_update_per_sec_label = listener_table.add_row("Update/sec", "", "Number of value update per seconds received from the server")
        self.listener_internal_qsize_label = listener_table.add_row(
            "Internal queue size", "", "The size of the queue passing the value updates from the network thread to the listener thread")
        self.listener_gui_qsize_label = listener_table.add_row(
            "GUI thread queue size", "", "The size of the queue passing the value updates from the listener thread to the UI thread")
        self.listener_event_rate_label = listener_table.add_row(
            "QT broadcast event rate", "", "Rate at which the value updates are signaled to be fetched in the UI")

        registry_table = self.add_section_table("Watchable registry")
        self.registry_var_count_label = registry_table.add_row("Variable count", "", "Number of Variables available")
        self.registry_alias_count_label = registry_table.add_row("Alias count", "", "Number of Alias available")
        self.registry_rpv_count_label = registry_table.add_row("RPV count", "", "Number of Runtime Published Values available")
        self.registry_watcher_count_label = registry_table.add_row("Registered watchers", "", "Number of GUI items subscribed to value update")
        self.registry_watched_entries_label = registry_table.add_row(
            "Watched entries", "", "Number of watchable element that has at least 1 GUI item subscribed as watcher")

        server_table = self.add_section_table("Server")
        self.server_uptime_label = server_table.add_row("Up Time", "N/A", "Time in seconds elapsed since the server has been started")
        self.server_invalid_request_count_label = server_table.add_row(
            "Invalid requests", "N/A", "Number of invalid request the server received. Expect 0")
        self.server_unexpected_error_count_label = server_table.add_row(
            "Unexpected errors", "N/A", "Number of unexpected error the server encountered while processing a request. Expect 0")
        self.server_client_count_label = server_table.add_row("Connected clients", "N/A", "Number of clients actually connected to the server")
        self.server_api_tx_datarate_label = server_table.add_row(
            "API Tx datarate", "N/A", "Datarate (byte/sec) going out of the API, all clients summed together")
        self.server_api_rx_datarate_label = server_table.add_row(
            "API Rx datarate", "N/A", "Datarate (byte/sec) going in the API, all clients summed together")
        self.server_msg_received_label = server_table.add_row("Messages received", "N/A", "Number of message received, all clients summed together")
        self.server_msg_sent_label = server_table.add_row("Message sent", "N/A", "Number of message sent, all clients summed together")
        self.server_device_session_count_label = server_table.add_row(
            "Device session count", "N/A", "Counter indicating how many new working connections has been established with a device ")
        self.server_device_datarate_byte_per_sec_label = server_table.add_row(
            "Device datarate", "N/A", "Number of request/response per seconds exchanged between the server and the device")
        self.server_device_datarate_up_down_ratio_label = server_table.add_row(
            "Device bandwidth ratios", "N/A", "Ratio of the device bandwidth used for Requests vs Responses ")

    def clear_server_labels(self) -> None:
        self.server_uptime_label.setText("N/A")
        self.server_invalid_request_count_label.setText("N/A")
        self.server_unexpected_error_count_label.setText("N/A")
        self.server_client_count_label.setText("N/A")
        self.server_api_tx_datarate_label.setText("N/A")
        self.server_api_rx_datarate_label.setText("N/A")
        self.server_msg_received_label.setText("N/A")
        self.server_msg_sent_label.setText("N/A")
        self.server_device_session_count_label.setText("N/A")
        self.server_device_datarate_byte_per_sec_label.setText("N/A")
        self.server_device_datarate_up_down_ratio_label.setText("N/A")

    def update_local_data(self, stats: ServerManager.Statistics) -> None:
        self.client_rx_data_label.setText("%s (%0.1f Msg/s)" % (format_eng_unit(stats.client.rx_data_rate,
                                          1, unit="B/s", binary=True), stats.client.rx_message_rate))
        self.client_tx_data_label.setText("%s (%0.1f Msg/s)" % (format_eng_unit(stats.client.tx_data_rate,
                                          1, unit="B/s", binary=True), stats.client.tx_message_rate))
        self.status_update_count_label.setText(f"{stats.status_update_received}")

        self.listener_update_count_label.setText(f"{stats.listener.update_received_count}")
        self.listener_drop_count_label.setText(f"{stats.listener.update_drop_count}")
        self.listener_update_per_sec_label.setText(f"{stats.listener.update_per_sec:0.1f} update/sec")
        self.listener_internal_qsize_label.setText(f"{stats.listener.internal_qsize}")
        self.listener_gui_qsize_label.setText(f"{stats.listener_to_gui_qsize}")
        self.listener_event_rate_label.setText(f"{stats.listener_event_rate:0.1f} signal/sec")

        self.registry_var_count_label.setText(f"{stats.watchable_registry.var_count}")
        self.registry_alias_count_label.setText(f"{stats.watchable_registry.alias_count}")
        self.registry_rpv_count_label.setText(f"{stats.watchable_registry.rpv_count}")
        self.registry_watcher_count_label.setText(f"{stats.watchable_registry.registered_watcher_count}")
        self.registry_watched_entries_label.setText(f"{stats.watchable_registry.watched_entries_count}")

    def update_server_data(self, stats: sdk.ServerStatistics) -> None:
        self.server_uptime_label.setText(format_sec_to_dhms(int(stats.uptime)))
        self.server_invalid_request_count_label.setText(f"{stats.invalid_request_count}")
        self.server_unexpected_error_count_label.setText(f"{stats.unexpected_error_count}")
        self.server_client_count_label.setText(f"{stats.client_count}")
        self.server_api_tx_datarate_label.setText(format_eng_unit(stats.to_all_clients_datarate_byte_per_sec, 1, unit="B/s", binary=True))
        self.server_api_rx_datarate_label.setText(format_eng_unit(stats.from_any_client_datarate_byte_per_sec, 1, unit="B/s", binary=True))
        self.server_device_session_count_label.setText(f"{stats.device_session_count}")
        self.server_msg_received_label.setText(f"{stats.msg_received}")
        self.server_msg_sent_label.setText(f"{stats.msg_sent}")
        total_datarate = stats.to_device_datarate_byte_per_sec + stats.from_device_datarate_byte_per_sec
        self.server_device_datarate_byte_per_sec_label.setText(
            "%s (%0.1f req/s)" % (format_eng_unit(total_datarate * 8, 1, "bit/s", binary=False), stats.device_request_per_sec))

        if total_datarate == 0:
            tx_ratio = 0.0
            rx_ratio = 0.0
        else:
            tx_ratio = round(min(100, max(0, stats.to_device_datarate_byte_per_sec / total_datarate * 100)), 1)
            rx_ratio = round(min(100, max(0, stats.from_device_datarate_byte_per_sec / total_datarate * 100)), 1)

        self.server_device_datarate_up_down_ratio_label.setText(f"Requests : {tx_ratio:0.1f}%    Responses:{rx_ratio:0.1f}%")

    def add_section(self, title: str) -> QVBoxLayout:
        gb = QGroupBox()
        gb.setTitle(title)
        self.main_layout.addWidget(gb)
        internal_layout = QVBoxLayout(gb)
        internal_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        return internal_layout

    def add_section_table(self, title: str) -> DisplayTable:
        table = DisplayTable()
        table_layout = self.add_section(title)
        table_layout.addWidget(table)
        return table

    def add_section_text(self, title: str, text: str) -> QLabel:
        text_layout = self.add_section(title)
        label = QLabel(text)
        _configure_value_label(label)
        text_layout.addWidget(label)
        return label
