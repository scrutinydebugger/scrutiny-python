from qtpy.QtWidgets import QStatusBar, QWidget, QLabel, QHBoxLayout, QSizePolicy, QPushButton, QToolBar, QMenu
from qtpy.QtGui import QPixmap, QAction
from qtpy.QtCore import Qt, QPoint
from scrutiny.gui.core.server_manager import ServerManager
from scrutiny.gui import assets
from scrutiny.sdk import ServerState, DeviceCommState, SFDInfo, DataloggingInfo, DataloggerState
import enum
from typing import Optional, Dict, Generic, TypeVar, cast, Union

class ServerLabelValue(enum.Enum):
    Disconnected = enum.auto()
    Disconnecting = enum.auto()
    Waiting = enum.auto()
    Connected = enum.auto()


TextLabelType = Union[QLabel, QPushButton, QAction]

class IndicatorLabel(QWidget):
    INDICATOR_SIZE = 12
    
    class Color(enum.Enum):
        RED = enum.auto()
        YELLOW = enum.auto()
        GREEN = enum.auto()

    class TextLabel(enum.Enum):
        LABEL = enum.auto()
        BUTTON = enum.auto()
        TOOLBAR = enum.auto()

    _text_label:TextLabelType
    _indicator_label:QLabel
    _color:Color
    _color_image_map:Dict[Color, QPixmap]
    _label_type:TextLabel
    _toolbar : Optional[QToolBar]

    @property
    def text_label(self) -> TextLabelType:
        return self._text_label
    
    @property
    def indicator_label(self) -> QLabel:
        return self._indicator_label

    def __init__(self, text:str, color:"IndicatorLabel.Color", label_type:TextLabel) -> None:
        super().__init__()
        self._label_type = label_type

        self._color_image_map = {
            self.Color.RED : assets.load_pixmap('red_square-64x64.png').scaled(self.INDICATOR_SIZE, self.INDICATOR_SIZE),
            self.Color.YELLOW : assets.load_pixmap('yellow_square-64x64.png').scaled(self.INDICATOR_SIZE, self.INDICATOR_SIZE),
            self.Color.GREEN : assets.load_pixmap('green_square-64x64.png').scaled(self.INDICATOR_SIZE, self.INDICATOR_SIZE)
        }
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(5,0,10,0)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._indicator_label = QLabel()
        self._indicator_label.setFixedWidth(self.INDICATOR_SIZE)
        
        self._layout.addWidget(self.indicator_label)

        self._toolbar = None
        if label_type == self.TextLabel.LABEL:
            self._text_label =  QLabel()
            self._layout.addWidget(self._text_label)
        elif label_type == self.TextLabel.BUTTON:
            self._text_label = QPushButton()
            self._text_label.setContentsMargins(0,0,0,0)
            self._layout.addWidget(self._text_label)
        elif label_type == self.TextLabel.TOOLBAR:
            self._toolbar = QToolBar()
            self._text_label = self._toolbar.addAction(text)
            self._layout.addWidget(self._toolbar)
        else:
            raise ValueError("Unsupported text label type")
        
        self.set_color(color)
        self.set_text(text)

    def set_color(self, color:Color) -> None:
        if color not in self._color_image_map:
            raise ValueError("Unsupported color")
        self._color = color
        self._indicator_label.setPixmap(self._color_image_map[color])

    def get_color(self) -> Color:
        return self._color

    def set_text(self, text:str) -> None:
        self._text_label.setText(text)   # Uses public property to have uniform api
    
    def get_text(self) -> str:
        return self._text_label.text()
    
    def add_menu(self, menu:QMenu) -> None:
        if self._label_type != self.TextLabel.TOOLBAR:
            raise ValueError("Cannot add a menu on other types than toolbars")
        assert isinstance(self._text_label, QAction)
        def show_menu() -> None:
            assert self._toolbar is not None
            menu.show()
            menu.popup(self.mapToGlobal(self._toolbar.pos() - QPoint(0, menu.height())))
        self._text_label.triggered.connect(show_menu)


class StatusBar(QStatusBar):

    _server_manager:ServerManager
    _server_status_label:IndicatorLabel
    _device_status_label:IndicatorLabel
    _sfd_status_label:QLabel
    _datalogger_status_label:QLabel

    _red_square:QPixmap
    _yellow_square:QPixmap
    _green_square:QPixmap
    
    def __init__(self, parent:QWidget, server_manager:ServerManager) -> None:
        super().__init__(parent)
        self._server_manager=server_manager

        self._server_status_label = IndicatorLabel("", color=IndicatorLabel.Color.RED, label_type=IndicatorLabel.TextLabel.TOOLBAR)
        self._device_status_label = IndicatorLabel("", color=IndicatorLabel.Color.RED, label_type=IndicatorLabel.TextLabel.TOOLBAR)
        self._sfd_status_label = QLabel("")
        self._datalogger_status_label = QLabel("")

        menu = QMenu()
        menu.addAction("test1")
        menu.addAction("test2")

        self._server_status_label.add_menu(menu)


        self.setContentsMargins(5,0,5,0)    
        self.addWidget(self._server_status_label)
        self.addWidget(self._device_status_label)
        self.addWidget(self._sfd_status_label)
        self.addPermanentWidget(self._datalogger_status_label)  # Right aligned
        
        # Allow the window to shrink horizontally. Prevented by the status bar otherwise.
        self._server_status_label.setMinimumWidth(1)    
        self._device_status_label.setMinimumWidth(1)    
        self._sfd_status_label.setMinimumWidth(1)   
        self._datalogger_status_label.setMinimumWidth(1)
        
        self._server_manager.signals.starting.connect(self.update_content)
        self._server_manager.signals.started.connect(self.update_content)
        self._server_manager.signals.stopping.connect(self.update_content)
        self._server_manager.signals.stopped.connect(self.update_content)
        self._server_manager.signals.server_connected.connect(self.update_content)
        self._server_manager.signals.server_disconnected.connect(self.update_content)
        self._server_manager.signals.device_ready.connect(self.update_content)
        self._server_manager.signals.device_disconnected.connect(self.update_content)
        self._server_manager.signals.datalogging_state_changed.connect(self.update_content)
        self._server_manager.signals.sfd_loaded.connect(self.update_content)
        self._server_manager.signals.sfd_unloaded.connect(self.update_content)

        self.update_content()

    def set_server_label_value(self, value:ServerLabelValue) -> None:
        prefix = 'Server:'
        if value == ServerLabelValue.Disconnected :
            self._server_status_label.set_color(IndicatorLabel.Color.RED)
            self._server_status_label.set_text(f"{prefix} Disconnected")
        elif value == ServerLabelValue.Disconnecting :
            self._server_status_label.set_color(IndicatorLabel.Color.YELLOW)
            self._server_status_label.set_text(f"{prefix} Stopping...")
        elif value == ServerLabelValue.Waiting:
            self._server_status_label.set_color(IndicatorLabel.Color.YELLOW)
            self._server_status_label.set_text(f"{prefix} Waiting...")
        elif value == ServerLabelValue.Connected:
            self._server_status_label.set_color(IndicatorLabel.Color.GREEN)
            self._server_status_label.set_text(f"{prefix} Connected")
        else:
            raise NotImplementedError(f"Unsupported label value {value}")
    
    def set_device_label(self, value:DeviceCommState) -> None:
        prefix = 'Device:'
        if value == DeviceCommState.NA:
            self._device_status_label.set_color(IndicatorLabel.Color.RED)
            self._device_status_label.set_text(f"{prefix} N/A")
        elif value == DeviceCommState.ConnectedReady:
            self._device_status_label.set_color(IndicatorLabel.Color.GREEN)
            self._device_status_label.set_text(f"{prefix} Connected")
        elif value == DeviceCommState.Connecting:
            self._device_status_label.set_color(IndicatorLabel.Color.YELLOW)
            self._device_status_label.set_text(f"{prefix} Connecting")
        elif value == DeviceCommState.Disconnected:
            self._device_status_label.set_color(IndicatorLabel.Color.RED)
            self._device_status_label.set_text(f"{prefix} Disconnected")
        else:
            raise NotImplementedError(f"Unsupported device comm state value {value}")
        
    def set_sfd_label(self, value:Optional[SFDInfo]) -> None:
        prefix = 'SFD:'
        if value is None:
            self._sfd_status_label.setText(f'{prefix} --- ')
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
            DataloggerState.Acquiring: "Acquiring",
            DataloggerState.DataReady: "Data Ready",
            DataloggerState.Error: "Error",
        }

        if value.state not in state_str:
            raise NotImplementedError(f"Unsupported datalogger state {value.state}")

        self._datalogger_status_label.setText(f"{prefix} {state_str[value.state]}{completion_str}")


    def update_content(self) -> None:
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
                        
