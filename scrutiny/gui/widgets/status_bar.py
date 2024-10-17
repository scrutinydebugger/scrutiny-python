from qtpy.QtWidgets import QStatusBar, QWidget, QLabel, QHBoxLayout, QSizePolicy, QPushButton, QToolBar, QMenu
from qtpy.QtGui import QPixmap, QAction
from qtpy.QtCore import Qt, QPoint
from scrutiny.gui.core.server_manager import ServerManager
from scrutiny.gui.dialogs.server_config_dialog import ServerConfigDialog
from scrutiny.gui.dialogs.device_config_dialog import DeviceConfigDialog
from scrutiny.gui import assets
from scrutiny.sdk import ServerState, DeviceCommState, SFDInfo, DataloggingInfo, DataloggerState, DeviceLinkType
import enum
from typing import Optional, Dict, cast, Union

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
    
    _server_status_label_menu:QMenu
    _server_configure_action: QAction
    _server_connect_action: QAction
    _server_disconnect_action: QAction
    _server_config_dialog:ServerConfigDialog
    
    _device_status_label_menu:QMenu
    _device_configure_action:QAction
    _device_about_action:QAction
    _device_config_dialog:DeviceConfigDialog

    _red_square:QPixmap
    _yellow_square:QPixmap
    _green_square:QPixmap
    _one_shot_auto_connect:bool
    
    def __init__(self, parent:QWidget, server_manager:ServerManager) -> None:
        super().__init__(parent)
        self._server_manager=server_manager
        self._server_config_dialog = ServerConfigDialog(self, apply_callback=self._server_config_applied)
        self._device_config_dialog = DeviceConfigDialog(self, apply_callback=self._device_config_applied)
        self._one_shot_auto_connect = False

        self._server_status_label = IndicatorLabel("", color=IndicatorLabel.Color.RED, label_type=IndicatorLabel.TextLabel.TOOLBAR)
        self._device_status_label = IndicatorLabel("", color=IndicatorLabel.Color.RED, label_type=IndicatorLabel.TextLabel.TOOLBAR)
        self._sfd_status_label = QLabel("")
        self._datalogger_status_label = QLabel("")

        self._server_status_label_menu = QMenu()
        self._server_configure_action = self._server_status_label_menu.addAction("Configure")
        self._server_connect_action = self._server_status_label_menu.addAction("Connect")
        self._server_disconnect_action = self._server_status_label_menu.addAction("Disconnect")

        self._server_status_label.add_menu(self._server_status_label_menu)
        self._server_configure_action.triggered.connect(self._server_configure_func)
        self._server_connect_action.triggered.connect(self._server_connect_func)
        self._server_disconnect_action.triggered.connect(self._server_disconnect_func)

        self._device_status_label_menu = QMenu()
        self._device_configure_action = self._device_status_label_menu.addAction("Configure")
        self._device_about_action = self._device_status_label_menu.addAction("About")

        self._device_status_label.add_menu(self._device_status_label_menu)
        self._device_configure_action.triggered.connect(self._device_configure_func)
        self._device_about_action.triggered.connect(self._device_about_func)

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
        self._server_manager.signals.stopped.connect(self._one_shot_reconnect)
        self._server_manager.signals.server_connected.connect(self.update_content)
        self._server_manager.signals.server_disconnected.connect(self.update_content)
        self._server_manager.signals.device_ready.connect(self.update_content)
        self._server_manager.signals.device_disconnected.connect(self.update_content)
        self._server_manager.signals.datalogging_state_changed.connect(self.update_content)
        self._server_manager.signals.sfd_loaded.connect(self.update_content)
        self._server_manager.signals.sfd_unloaded.connect(self.update_content)
        
        self._server_manager.signals.status_received.connect(self.update_content)

        self.update_content()

    def _server_configure_func(self) -> None:
        self._server_config_dialog.show()

    def _server_connect_func(self) -> None:
        self._server_manager.start(self._server_config_dialog.get_config())
    
    def _server_disconnect_func(self) -> None:
        self._server_manager.stop()

    def _server_config_applied(self, dialog:ServerConfigDialog) -> None:
        if self._server_manager.is_running():
            self._one_shot_auto_connect = True
            self._server_manager.stop()

        elif not self._server_manager.is_stopping():
            self._server_connect_func()
    
    def _one_shot_reconnect(self) -> None:
        if self._one_shot_auto_connect:
            self._one_shot_auto_connect=False
            self._server_connect_func()
    
    def _device_configure_func(self) -> None:
        info = self._server_manager.get_server_info()
        if info is None:
            self._device_config_dialog.swap_config_pane(DeviceLinkType.NA)
        else:
            self._device_config_dialog.set_config(info.device_link.type, info.device_link.config)
            self._device_config_dialog.swap_config_pane(info.device_link.type)

        self._device_config_dialog.show()

    def _device_about_func(self) -> None:
        pass

    def _device_config_applied(self, dialog:DeviceConfigDialog) -> None:
        link_type, config = dialog.get_type_and_config()
        # TODO : Check if it is ok to use across thread.
        # self._server_manager._client.configure_device_link(link_type, config)
        # TODO
        
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
            self._device_status_label.setEnabled(False)
        elif value == DeviceCommState.ConnectedReady:
            self._device_status_label.set_color(IndicatorLabel.Color.GREEN)
            self._device_status_label.set_text(f"{prefix} Connected")
            self._device_status_label.setEnabled(True)
        elif value == DeviceCommState.Connecting:
            self._device_status_label.set_color(IndicatorLabel.Color.YELLOW)
            self._device_status_label.set_text(f"{prefix} Connecting")
            self._device_status_label.setEnabled(True)
        elif value == DeviceCommState.Disconnected:
            self._device_status_label.set_color(IndicatorLabel.Color.RED)
            self._device_status_label.set_text(f"{prefix} Disconnected")
            self._device_status_label.setEnabled(True)
        else:
            raise NotImplementedError(f"Unsupported device comm state value {value}")

    def set_sfd_label(self, device_connected:bool, value:Optional[SFDInfo]) -> None:
        prefix = 'SFD:'
        if value is None:
            self._sfd_status_label.setEnabled(device_connected)
            self._sfd_status_label.setText(f'{prefix} None ')
            self._sfd_status_label.setToolTip("No Scrutiny Firmware Description file loaded")
        else:
            self._sfd_status_label.setEnabled(True)
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

    def emulate_connect_click(self)->None:
        if self._server_connect_action.isEnabled():
            self._server_connect_action.trigger()

    def update_content(self) -> None:
        if not self._server_manager.is_running():
            self._device_configure_action.setEnabled(False)
            self._device_about_action.setEnabled(False)

            if self._server_manager.is_stopping():
                self._server_disconnect_action.setEnabled(False)
                self._server_connect_action.setEnabled(False)
                self.set_server_label_value(ServerLabelValue.Disconnecting)
            else:
                self._server_disconnect_action.setEnabled(False)
                self._server_connect_action.setEnabled(True)
                self.set_server_label_value(ServerLabelValue.Disconnected)
            self.set_device_label(DeviceCommState.NA)
            self.set_sfd_label(device_connected=False, value=None)
            self.set_datalogging_label(DataloggingInfo(state=DataloggerState.NA, completion_ratio=None))
        else:
            self._server_disconnect_action.setEnabled(True)
            self._server_connect_action.setEnabled(False)
            
            server_state = self._server_manager.get_server_state()
            server_info = None

            if server_state == ServerState.Connected:
                self._device_configure_action.setEnabled(True)
                self.set_server_label_value(ServerLabelValue.Connected)
                server_info = self._server_manager.get_server_info()
            else:
                self._device_configure_action.setEnabled(False)
                self.set_server_label_value(ServerLabelValue.Waiting)
        
            if server_info is None:
                self._device_about_action.setEnabled(False)
                self.set_device_label(DeviceCommState.NA)
                self.set_sfd_label(device_connected=False, value=None)
                self.set_datalogging_label(DataloggingInfo(state=DataloggerState.NA, completion_ratio=None))
            else:
                self.set_device_label(server_info.device_comm_state)
                self.set_sfd_label(device_connected=server_info.device_comm_state == DeviceCommState.ConnectedReady, value=server_info.sfd)
                self.set_datalogging_label(server_info.datalogging)
                self._device_about_action.setEnabled(server_info.device_comm_state == DeviceCommState.ConnectedReady)
                        
