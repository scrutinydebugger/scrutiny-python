#    app_stats_display.py
#        A widget to display the application stats
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['ApplicationStatsDisplay']

from PySide6.QtWidgets import QWidget, QFormLayout, QLabel, QGroupBox, QVBoxLayout
from PySide6.QtCore import Qt
from typing import Union, Optional
from scrutiny.gui.core.server_manager import ServerManager
from scrutiny.tools import format_eng_unit

def configure_property_label(label:QLabel, has_tooltip:bool) -> None:
    if has_tooltip:
        label.setCursor(Qt.CursorShape.WhatsThisCursor)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

def configure_value_label(label:QLabel) -> None:
    label.setCursor(Qt.CursorShape.IBeamCursor)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse) 

class DisplayTable(QWidget):
    """A table of properties/value. One per section displayed in DeviceInfoDialog"""
    form_layout : QFormLayout
    def __init__(self) -> None:
        super().__init__()
        self.form_layout = QFormLayout(self)
        self.form_layout.setFormAlignment(Qt.AlignmentFlag.AlignVCenter)
        
    
    def add_row(self, label_txt:str, item:Union[str, QWidget], tooltip:Optional[str]=None) -> QLabel:
        label = QLabel(label_txt)
        has_tooltip=True if tooltip is not None else False
        configure_property_label(label, has_tooltip=has_tooltip)
        if tooltip is not None:
            label.setToolTip(tooltip)
        if isinstance(item, str):
            item=QLabel(item)
        
        if isinstance(item, QLabel):
            configure_value_label(item)

        is_odd = self.form_layout.rowCount() % 2 == 0    # Check for 0 because we evaluate for next node
        odd_even = "odd" if is_odd else "even"
        label.setProperty("table_odd_even", odd_even)
        item.setProperty("table_odd_even", odd_even)

        self.form_layout.addRow(label, item)
        assert isinstance(item, QLabel)
        return item

class ApplicationStatsDisplay(QWidget):
    client_rx_data_label:QLabel
    client_tx_data_label:QLabel
    status_update_count_label:QLabel
    listener_update_count_label:QLabel
    listener_drop_count_label:QLabel
    listener_update_per_sec_label:QLabel
    listener_internal_qsize_label:QLabel
    listener_gui_qsize_label:QLabel
    listener_event_rate_label:QLabel
    registry_var_count_label:QLabel
    registry_alias_count_label:QLabel
    registry_rpv_count_label:QLabel
    registry_watcher_count_label:QLabel
    registry_watched_entries_label:QLabel

    def __init__(self, parent:QWidget) -> None:
        super().__init__(parent)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        client_table = self.add_section_table("Client")
        self.client_rx_data_label = client_table.add_row("Rx data", "")
        self.client_tx_data_label = client_table.add_row("Tx data", "")
        self.status_update_count_label = client_table.add_row("Status update count", "")

        listener_table = self.add_section_table("Listener")
        self.listener_update_count_label = listener_table.add_row("Total update received", "")
        self.listener_drop_count_label = listener_table.add_row("Total update dropped", "")
        self.listener_update_per_sec_label = listener_table.add_row("Update/sec", "")
        self.listener_internal_qsize_label = listener_table.add_row("Internal queue size", "")
        self.listener_gui_qsize_label = listener_table.add_row("GUI thread queue size", "")
        self.listener_event_rate_label = listener_table.add_row("QT broadcast event rate", "")

        registry_table = self.add_section_table("Watchable registry")
        self.registry_var_count_label = registry_table.add_row("Variable count", "")
        self.registry_alias_count_label = registry_table.add_row("Alias count", "")
        self.registry_rpv_count_label = registry_table.add_row("RPV count", "")
        self.registry_watcher_count_label = registry_table.add_row("Registered watchers", "")
        self.registry_watched_entries_label = registry_table.add_row("Watched entries", "")


    def update_data(self, stats:ServerManager.Statistics) -> None:
        self.client_rx_data_label.setText("%sB/s (%0.1f Msg/s)" % (format_eng_unit(stats.client.rx_data_rate, 1, binary=True), stats.client.rx_message_rate))
        self.client_tx_data_label.setText("%sB/s (%0.1f Msg/s)" % (format_eng_unit(stats.client.tx_data_rate, 1, binary=True), stats.client.tx_message_rate))
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

    def add_section(self, title:str) -> QVBoxLayout:
        gb = QGroupBox()
        gb.setTitle(title)
        self.main_layout.addWidget(gb)
        internal_layout = QVBoxLayout(gb)
        internal_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        return internal_layout

    def add_section_table(self, title:str) -> DisplayTable:
        table = DisplayTable()
        table_layout = self.add_section(title)
        table_layout.addWidget(table)
        return table
    
    def add_section_text(self, title:str, text:str) -> QLabel:
        text_layout = self.add_section(title)
        label = QLabel(text)
        configure_value_label(label)
        text_layout.addWidget(label)
        return label
