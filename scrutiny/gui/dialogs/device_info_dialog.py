__all__ = ['DeviceInfoDialog']

from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QWidget, QVBoxLayout, QGroupBox
from PySide6.QtCore import Qt
from typing import Optional, List, Union

from scrutiny.sdk import DeviceInfo, SupportedFeatureMap, MemoryRegion
from scrutiny.sdk.datalogging import DataloggingCapabilities


def configure_label(label:QLabel) -> None:
    label.setCursor(Qt.CursorShape.IBeamCursor)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

class SupportedFeatureList(QWidget):
    def __init__(self, features:SupportedFeatureMap):
        super().__init__()
        layout = QFormLayout(self)
        layout.setContentsMargins(0,0,0,0)
        feature_list = [
            ("Memory write", features.memory_write),
            ("Datalogging", features.datalogging),
            ("64 bits", features.sixtyfour_bits),
            ("User command", features.user_command)
        ]
        for feature in feature_list:
            title, enable = feature
            if enable:
                value_label = QLabel("Yes")
            else:
                value_label = QLabel("No")
            
            value_label.setProperty("feature_enable", enable)
            feature_label = QLabel(f"- {title} :")
            for label in [feature_label, value_label]:
                configure_label(label)
            layout.addRow(feature_label, label)
        
        layout.setSpacing(1)

class MemoryRegionList(QWidget):
    def __init__(self, regions:List[MemoryRegion], address_size_bits:int=64):
        super().__init__()
        address_size = address_size_bits//8
        if address_size%2 == 1:
            address_size += 1

        def make_label(region:MemoryRegion) -> QLabel:
            format_string = f"0x%0{address_size}X"
            s1 =  format_string % region.start
            s2 =  format_string % region.end
            label =  QLabel(f"- {s1}-{s2}")
            configure_label(label)
            return label

        layout:Union[QVBoxLayout, QFormLayout]
        if len(regions) == 0:
            layout = QVBoxLayout(self)
            label = QLabel("None")
            configure_label(label)
            layout.addWidget( label )
        else:
            layout = QFormLayout()
            for region in regions:
                layout.addWidget( make_label(region) )
        layout.setContentsMargins(0,0,0,0)
        self.setLayout(layout)

class DeviceInfoDisplayTable(QWidget):
    form_layout : QFormLayout
    def __init__(self) -> None:
        super().__init__()
        self.form_layout = QFormLayout(self)
    
    def add_row(self, label_txt:str, item:Union[str, QWidget]) -> None:
        label = QLabel(label_txt)
        configure_label(label)
        if isinstance(item, str):
            item=QLabel(item)
        
        if isinstance(item, QLabel):
            configure_label(item)

        is_odd = self.form_layout.rowCount() % 2 == 0    # Check for 0 because we evaluate for next node
        odd_even = "odd" if is_odd else "even"
        label.setProperty("table_odd_even", odd_even)
        item.setProperty("table_odd_even", odd_even)

        self.form_layout.addRow(label, item)


class DeviceInfoDialog(QDialog):
    def __init__(self, parent:Optional[QWidget] = None) -> None:
        super().__init__(parent) 

        self.setWindowTitle("Device")
    
    def rebuild(self, info:DeviceInfo) -> None:
        layout = QVBoxLayout(self)

        def add_section(title:str) -> QVBoxLayout:
            gb = QGroupBox()
            gb.setTitle(title)
            layout.addWidget(gb)
            internal_layout = QVBoxLayout(gb)
            return internal_layout

        def add_section_table(title:str) -> DeviceInfoDisplayTable:
            table = DeviceInfoDisplayTable()
            table_layout = add_section(title)
            table_layout.addWidget(table)
            return table
        
        def add_section_text(title:str, text:str) -> QLabel:
            text_layout = add_section(title)
            label = QLabel(text)
            configure_label(label)
            text_layout.addWidget(label)
            return label

        device_table = add_section_table("Device")
        comm_table = add_section_table("Communication")
        

        device_table.add_row("Device ID", info.device_id)
        device_table.add_row("Display name", info.display_name)
        device_table.add_row("Supported features", SupportedFeatureList(info.supported_features) )
        device_table.add_row("Read-only memory regions", MemoryRegionList(info.readonly_memory_regions, info.address_size_bits) )
        device_table.add_row("Forbidden memory regions",  MemoryRegionList(info.forbidden_memory_regions, info.address_size_bits) )

        comm_table.add_row("Rx buffer size", f"{info.max_rx_data_size} bytes")
        comm_table.add_row("Tx buffer size", f"{info.max_tx_data_size} bytes")
        bitrate_str = f"{info.max_bitrate_bps} bps" if info.max_bitrate_bps is not None else "N/A"
        comm_table.add_row("Max bitrate", bitrate_str)
        comm_table.add_row("Heartbeat timeout", f"{info.heartbeat_timeout:0.1f} seconds")
        comm_table.add_row("Protocol version", f"V{info.protocol_major}.{info.protocol_minor}")

        datalogging_title="Datalogging"
        #if datalogging is None:
        #    add_section_text(datalogging_title, "N/A")
        #else:
        #    datalogging_table = add_section_table(datalogging_title)
        #    datalogging_table.add_row("Buffer size", f"{datalogging.buffer_size} bytes")
        #    datalogging_table.add_row("Encoding", f"{datalogging.encoding.name}")
        #    datalogging_table.add_row("Max signals", f"{datalogging.max_nb_signal}")
            

    
    