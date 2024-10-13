from qtpy.QtWidgets import QStatusBar, QWidget, QLabel
from qtpy.QtGui import QPixmap
from scrutiny.gui.core.server_manager import ServerManager
from scrutiny.gui import assets
from scrutiny.sdk import ServerState, DeviceCommState, SFDInfo, DataloggingInfo, DataloggerState
import enum
import logging
from typing import Optional

class ServerLabelValue(enum.Enum):
    Disconnected = enum.auto()
    Disconnecting = enum.auto()
    Waiting = enum.auto()
    Connected = enum.auto()


class StatusBar(QStatusBar):
    INDICATOR_SIZE = 12

    _server_manager:ServerManager
    _server_status_indicator:QLabel
    _server_status_label:QLabel
    _device_status_indicator:QLabel
    _device_status_label:QLabel
    _sfd_status_label:QLabel
    _datalogger_status_label:QLabel

    _red_square:QPixmap
    _yellow_square:QPixmap
    _green_square:QPixmap
    
    def __init__(self, parent:QWidget, server_manager:ServerManager) -> None:
        super().__init__(parent)
        self._server_manager=server_manager

        self._red_square = assets.load_pixmap('red_square-64x64.png').scaled(self.INDICATOR_SIZE, self.INDICATOR_SIZE)
        self._yellow_square = assets.load_pixmap('yellow_square-64x64.png').scaled(self.INDICATOR_SIZE, self.INDICATOR_SIZE)
        self._green_square = assets.load_pixmap('green_square-64x64.png').scaled(self.INDICATOR_SIZE, self.INDICATOR_SIZE)
        
        self._server_status_label = QLabel("")
        self._server_status_indicator = QLabel()
        self._device_status_label = QLabel("")
        self._device_status_indicator = QLabel()
        self._sfd_status_label = QLabel("")
        self._datalogger_status_label = QLabel("")
        spacer_left = QLabel("")
        spacer_right = QLabel("")
        spacer_left.setFixedWidth(5)
        spacer_right.setFixedWidth(5)
        
        self.addWidget(spacer_left)
        self.addWidget(self._server_status_indicator)
        self.addWidget(self._server_status_label)
        self.addWidget(self._device_status_indicator)
        self.addWidget(self._device_status_label)
        self.addWidget(self._sfd_status_label)
        self.addPermanentWidget(self._datalogger_status_label)  # Right aligned
        self.addPermanentWidget(spacer_right)
        
        self._server_status_label.setMinimumWidth(128)
        self._device_status_label.setMinimumWidth(128)
        self._sfd_status_label.setMinimumWidth(64)
        
        self._server_manager.signals.starting.connect(self.update)
        self._server_manager.signals.started.connect(self.update)
        self._server_manager.signals.stopping.connect(self.update)
        self._server_manager.signals.stopped.connect(self.update)
        self._server_manager.signals.server_connected.connect(self.update)
        self._server_manager.signals.server_disconnected.connect(self.update)
        self._server_manager.signals.device_ready.connect(self.update)
        self._server_manager.signals.device_disconnected.connect(self.update)
        self._server_manager.signals.datalogging_state_changed.connect(self.update)
        self._server_manager.signals.sfd_loaded.connect(self.update)
        self._server_manager.signals.sfd_unloaded.connect(self.update)

        self.update()

    def set_server_label_value(self, value:ServerLabelValue) -> None:
        prefix = 'Server:'
        if value == ServerLabelValue.Disconnected :
            self._server_status_indicator.setPixmap(self._red_square)
            self._server_status_label.setText(f"{prefix} Disconnected")
        elif value == ServerLabelValue.Disconnecting :
            self._server_status_indicator.setPixmap(self._yellow_square)
            self._server_status_label.setText(f"{prefix} Disconnecting...")
        elif value == ServerLabelValue.Waiting:
            self._server_status_indicator.setPixmap(self._yellow_square)
            self._server_status_label.setText(f"{prefix} Waiting...")
        elif value == ServerLabelValue.Connected:
            self._server_status_indicator.setPixmap(self._green_square)
            self._server_status_label.setText(f"{prefix} Connected")
        else:
            raise NotImplementedError(f"Unsupported label value {value}")
    
    def set_device_label(self, value:DeviceCommState) -> None:
        prefix = 'Device:'
        if value == DeviceCommState.NA:
            self._device_status_indicator.setPixmap(self._red_square)
            self._device_status_label.setText(f"{prefix} N/A")
        elif value == DeviceCommState.ConnectedReady:
            self._device_status_indicator.setPixmap(self._green_square)
            self._device_status_label.setText(f"{prefix} Connected")
        elif value == DeviceCommState.Connecting:
            self._device_status_indicator.setPixmap(self._yellow_square)
            self._device_status_label.setText(f"{prefix} Connecting")
        elif value == DeviceCommState.Disconnected:
            self._device_status_indicator.setPixmap(self._red_square)
            self._device_status_label.setText(f"{prefix} Disconnected")
        else:
            raise NotImplementedError(f"Unsupported device comm state value {value}")
        
    def set_sfd_label(self, value:Optional[SFDInfo]) -> None:
        prefix = 'SFD:'
        if value is None:
            self._sfd_status_label.setText(f'{prefix} -')
            self._sfd_status_label.setToolTip("No Scrutiny Firmware Description file loaded")
        else:
            project_name = "Unnamed project"
            if value.metadata is not None:
                if value.metadata.project_name is not None:
                    project_name = value.metadata.project_name
                    if value.metadata.version is not None:
                        project_name += ' V' + value.metadata.version
            
            self._sfd_status_label.setText(f'{prefix} {project_name}')
            self._sfd_status_label.setToolTip(f"Firmware ID: {value.firmware_id}")

    def set_datalogging_label(self, value:DataloggingInfo) -> None:
        prefix = "Datalogger:"
        completion_str = ""
        if value.completion_ratio is not None:
            ratio = round(value.completion_ratio*100)
            completion_str = f" {ratio}%"
        state_str = {
            DataloggerState.NA: "N/A",
            DataloggerState.Standby: "Standby",
            DataloggerState.WaitForTrigger: "Wait For Trigger",
            DataloggerState.Acquiring: "Acquiring...",
            DataloggerState.DataReady: "Data available",
            DataloggerState.Error: "Error",
        }

        if value.state not in state_str:
            raise NotImplementedError(f"Unsupported datalogger state {value.state}")

        self._datalogger_status_label.setText(f"{prefix} {state_str[value.state]}{completion_str}")


    def update(self) -> None:
        if not self._server_manager.is_running():
            if self._server_manager.is_stopping():
                self.set_server_label_value(ServerLabelValue.Disconnecting)
            else:
                self.set_server_label_value(ServerLabelValue.Disconnected)
            self.set_device_label(DeviceCommState.NA)
            self.set_sfd_label(None)
            self.set_datalogging_label(DataloggingInfo(state=DataloggerState.NA, completion_ratio=None))
        else:
            server_state = self._server_manager.get_server_state()
            server_info = None

            if server_state == ServerState.Connected:
                self.set_server_label_value(ServerLabelValue.Connected)
                server_info = self._server_manager.get_server_info()
            else:
                self.set_server_label_value(ServerLabelValue.Waiting)
        
            if server_info is None:
                self.set_device_label(DeviceCommState.NA)
                self.set_sfd_label(None)
                self.set_datalogging_label(DataloggingInfo(state=DataloggerState.NA, completion_ratio=None))
            else:
                self.set_device_label(server_info.device_comm_state)
                self.set_sfd_label(server_info.sfd)
                self.set_datalogging_label(server_info.datalogging)
                        
