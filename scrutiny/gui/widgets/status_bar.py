from qtpy.QtWidgets import QStatusBar, QWidget, QLabel, QHBoxLayout, QSizePolicy, QPushButton, QToolBar, QMenu
from qtpy.QtGui import QPixmap, QAction
from qtpy.QtCore import Qt, QPoint
from scrutiny.gui.core.server_manager import ServerManager
from scrutiny.gui.dialogs.server_config_dialog import ServerConfigDialog
from scrutiny.gui.dialogs.device_config_dialog import DeviceConfigDialog
from scrutiny.gui import assets
from scrutiny.sdk import ServerState, DeviceCommState, SFDInfo, DataloggingInfo, DataloggerState, DeviceLinkType, BaseLinkConfig
from scrutiny import sdk
from scrutiny.sdk.client import ScrutinyClient
import functools
import enum
from typing import Optional, Dict, cast, Union, Any, Tuple

class ServerLabelValue(enum.Enum):
    Disconnected = enum.auto()
    Disconnecting = enum.auto()
    Waiting = enum.auto()
    Connected = enum.auto()


TextLabelType = Union[QLabel, QPushButton, QAction]

class StatusBarLabel(QWidget):
    """Custom status bar label object that allow many useful configuration"""
    INDICATOR_SIZE = 12
    """Size of the red/yellow/green indicator"""
    
    class Color(enum.Enum):
        RED = enum.auto()
        YELLOW = enum.auto()
        GREEN = enum.auto()

    class TextLabelKind(enum.Enum):
        LABEL = enum.auto()
        BUTTON = enum.auto()
        TOOLBAR = enum.auto()

    _text_label:TextLabelType
    """The QWidget that store the text"""
    _indicator_label:Optional[QLabel]
    """The label used for the indicator icon. Only present if use_indicator=True"""
    _color:Optional[Color]
    """The color of the indicator light. Needs use_indicator=True"""
    _color_image_map:Dict[Color, QPixmap]
    """A dict that maps a Color enum to a Pixmap to the indicator icon"""
    _label_kind:TextLabelKind
    """The kind of label used to store the text. Can be button/label/toolbar"""
    _use_indicator:bool
    """True if we want a little indicator light next to the text label"""
    _toolbar : Optional[QToolBar]
    """The contianing toolbar object for label using a toolbar for the text label"""

    @property
    def text_label(self) -> TextLabelType:
        """The kind of text label used in this item"""
        return self._text_label
    
    @property
    def indicator_label(self) -> QLabel:
        """The label used for the indicator light. ``use_indicator`` must be True"""
        assert self._indicator_label is not None
        return self._indicator_label

    def __init__(self, 
                 text:str, 
                 label_kind:TextLabelKind,
                 use_indicator:bool,
                 color:"Optional[StatusBarLabel.Color]" = None
                 ) -> None:
        super().__init__()
        self._label_kind = label_kind
        self._use_indicator = use_indicator

        self._color_image_map = {
            self.Color.RED : assets.load_pixmap('red_square-64x64.png').scaled(self.INDICATOR_SIZE, self.INDICATOR_SIZE),
            self.Color.YELLOW : assets.load_pixmap('yellow_square-64x64.png').scaled(self.INDICATOR_SIZE, self.INDICATOR_SIZE),
            self.Color.GREEN : assets.load_pixmap('green_square-64x64.png').scaled(self.INDICATOR_SIZE, self.INDICATOR_SIZE)
        }
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(5,0,10,0)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._indicator_label = None
        if use_indicator:
            self._indicator_label = QLabel()
            self._indicator_label.setFixedWidth(self.INDICATOR_SIZE)
            self._layout.addWidget(self.indicator_label)

        self._toolbar = None
        if label_kind == self.TextLabelKind.LABEL:
            self._text_label =  QLabel()
            self._layout.addWidget(self._text_label)
        elif label_kind == self.TextLabelKind.BUTTON:
            self._text_label = QPushButton()
            self._text_label.setContentsMargins(0,0,0,0)
            self._layout.addWidget(self._text_label)
        elif label_kind == self.TextLabelKind.TOOLBAR:
            self._toolbar = QToolBar()
            self._text_label = self._toolbar.addAction(text)
            self._layout.addWidget(self._toolbar)
        else:
            raise ValueError("Unsupported text label type")
        
        self.set_color(color)
        self.set_text(text)

    def set_color(self, color:Optional[Color]) -> None:
        """Change the color of the indicator light. raise an exception is ``use_indicator`` is not True"""
        if not self._use_indicator:
            return
        assert self._indicator_label is not None
        assert color is not None

        if color not in self._color_image_map:
            raise ValueError("Unsupported color")
        self._color = color
        self._indicator_label.setPixmap(self._color_image_map[color])

    def get_color(self) -> Color:
        """Return the color of the indicator light. raise an exception is ``use_indicator`` is not True"""
        if not self._use_indicator:
            raise RuntimeError("No color on status bar item without indicator")
        assert self._color is not None
        return self._color

    def set_text(self, text:str) -> None:
        """Set the text on the text label"""
        self._text_label.setText(text)   # Uses public property to have uniform api
    
    def get_text(self) -> str:
        """Get the text of the text label"""
        return self._text_label.text()
    
    def add_menu(self, menu:QMenu) -> None:
        """Add a menu to the label. label kind must be TOOLBAR"""
        if self._label_kind != self.TextLabelKind.TOOLBAR:
            raise ValueError("Cannot add a menu on other types than toolbars")
        assert isinstance(self._text_label, QAction)
        def show_menu() -> None:
            assert self._toolbar is not None
            menu.show()
            menu.popup(self.mapToGlobal(self._toolbar.pos() - QPoint(0, menu.height())))
        self._text_label.triggered.connect(show_menu)

    def set_click_action(self, fn:object) -> None:
        """Connect a function to a click signal on the underlying text label. Possible with TOOLBAR and BUTTON kind"""
        if self._label_kind not in [self.TextLabelKind.TOOLBAR, self.TextLabelKind.BUTTON] :
            raise ValueError("Cannot set a click action on label other than toolbar and button")
        
        if isinstance(self._text_label, QAction):
            self._text_label.triggered.connect(fn)
        elif isinstance(self._text_label, QPushButton):
            self._text_label.clicked.connect(fn)
        else:
            raise ValueError("Unsupported label type")  # Shouldn't happen

class StatusBar(QStatusBar):
    _server_manager:ServerManager
    """Broker between the QT app and the server"""
    _server_status_label:StatusBarLabel
    """Label where the server status is written (Connected, Waiting, Disconnected)"""
    _device_status_label:StatusBarLabel
    """Label where the device status is written (Connected, Connecting, Disconnected)"""
    _device_comm_link_label:StatusBarLabel
    """Label where the actual server/device communication link configuration is written."""
    _sfd_status_label:StatusBarLabel
    """Label that shows the actually loaded SFD"""
    _datalogger_status_label:StatusBarLabel
    """Label that shows the state of the datalogger"""
    
    _server_status_label_menu:QMenu
    """Menu showed when the user click the server status label"""
    _server_configure_action: QAction
    """Menu action : Server Status -> Configure. Allow to change the server configuration"""
    _server_connect_action: QAction
    """Menu action : Server Status -> Connect. Starts the server manager"""
    _server_disconnect_action: QAction
    """Menu action : Server Status -> Connect. Stops the server manager"""
    _server_config_dialog:ServerConfigDialog
    """Dialog shown when Configure menu is hit. Allow to change the server hostname and port"""
    
    _device_status_label_menu:QMenu
    """Menu showed when the user click the device status label"""
    _device_details_action:QAction
    """Menu action : Device Status -> Details. Pops a window with all the device info in it"""
    _device_config_dialog:DeviceConfigDialog
    """Dialog that allow configuring the device link. Shown when the device_link_label is clicked"""

    _red_square:QPixmap
    """Icon shown next to the label in the status bar"""
    _yellow_square:QPixmap
    """Icon shown next to the label in the status bar"""
    _green_square:QPixmap
    """Icon shown next to the label in the status bar"""
    _one_shot_auto_connect:bool
    """Flag used to ensure is single reconnection if the user change the server confiugration"""
    
    def __init__(self, parent:QWidget, server_manager:ServerManager) -> None:
        super().__init__(parent)
        self._server_manager=server_manager
        self._server_config_dialog = ServerConfigDialog(self, apply_callback=self._server_config_applied)
        self._device_config_dialog = DeviceConfigDialog(self, apply_callback=self._device_config_applied)
        self._one_shot_auto_connect = False

        self._server_status_label = StatusBarLabel("", use_indicator=True, label_kind=StatusBarLabel.TextLabelKind.TOOLBAR, color=StatusBarLabel.Color.RED)
        self._device_comm_link_label = StatusBarLabel("", use_indicator=True, label_kind=StatusBarLabel.TextLabelKind.TOOLBAR, color=StatusBarLabel.Color.RED)
        self._device_status_label = StatusBarLabel("", use_indicator=True, label_kind=StatusBarLabel.TextLabelKind.TOOLBAR, color=StatusBarLabel.Color.RED)
        self._sfd_status_label = StatusBarLabel("", use_indicator=False, label_kind=StatusBarLabel.TextLabelKind.LABEL)
        self._datalogger_status_label = StatusBarLabel("", use_indicator=False, label_kind=StatusBarLabel.TextLabelKind.LABEL)

        self._server_status_label_menu = QMenu()
        self._server_configure_action = self._server_status_label_menu.addAction("Configure")
        self._server_connect_action = self._server_status_label_menu.addAction("Connect")
        self._server_disconnect_action = self._server_status_label_menu.addAction("Disconnect")
        self._server_status_label.add_menu(self._server_status_label_menu)
        self._server_configure_action.triggered.connect(self._server_configure_func)
        self._server_connect_action.triggered.connect(self._server_connect_func)
        self._server_disconnect_action.triggered.connect(self._server_disconnect_func)

        self._device_status_label_menu = QMenu()
        self._device_details_action = self._device_status_label_menu.addAction("Details")
        self._device_status_label.add_menu(self._device_status_label_menu)
        self._device_details_action.triggered.connect(self._device_about_func)

        self._device_comm_link_label.set_click_action(self._device_link_click_func)

        self.setContentsMargins(5,0,5,0)    
        self.addWidget(self._server_status_label)
        self.addWidget(self._device_comm_link_label)
        self.addWidget(self._device_status_label)
        self.addWidget(self._sfd_status_label)
        self.addPermanentWidget(self._datalogger_status_label)  # Right aligned
        
        # Allow the window to shrink horizontally. Prevented by the status bar otherwise.
        self._server_status_label.setMinimumWidth(1)    
        self._device_status_label.setMinimumWidth(1)    
        self._device_comm_link_label.setMinimumWidth(1)    
        self._sfd_status_label.setMinimumWidth(1)   
        self._datalogger_status_label.setMinimumWidth(1)
        
        # We catch everything!
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
        # When the user click the server status -> Configure
        self._server_config_dialog.show()

    def _server_connect_func(self) -> None:
        # When the user click the server status -> Connect
        self._server_manager.start(self._server_config_dialog.get_config())
    
    def _server_disconnect_func(self) -> None:
        # When the user click the server status -> Disconnect
        self._server_manager.stop()

    def _server_config_applied(self, dialog:ServerConfigDialog) -> None:
        # Called When the server parameters are set and the user click OK in the dialog
        if self._server_manager.is_running():
            self._one_shot_auto_connect = True
            self._server_manager.stop()

        elif not self._server_manager.is_stopping():
            self._server_connect_func()
    
    def _one_shot_reconnect(self) -> None:
        # Used for reconnecting once after the user change the server config
        if self._one_shot_auto_connect:
            self._one_shot_auto_connect=False
            self._server_connect_func()
    
    def _device_link_click_func(self) -> None:
        # Called when the suer click on the device link label in the status bar. 
        # Opens a configuration dialog
        info = self._server_manager.get_server_info()
        if info is None:
            self._device_config_dialog.swap_config_pane(DeviceLinkType.NONE)
        else:
            self._device_config_dialog.set_config(info.device_link.type, cast(sdk.BaseLinkConfig, info.device_link.config))
            self._device_config_dialog.swap_config_pane(info.device_link.type)

        self._device_config_dialog.show()


    def _device_about_func(self) -> None:
        # TODO
        pass

    def _device_config_applied(self, dialog:DeviceConfigDialog) -> None:
        # When the user click OK in the DeviceLinkConfigDialog. He wants the change the link between the server and the device
        link_type, config = dialog.get_type_and_config()
        if config is None:
            # Invalid config. Do nothing
            return 
        
        def change_device_link(link_type:DeviceLinkType, config:BaseLinkConfig, client:ScrutinyClient) -> Tuple[DeviceLinkType, BaseLinkConfig]:
            client.configure_device_link(link_type, config)
            return (link_type, config)
        
        # Runs the request in a separate thread to avoid blocking the UI thread
        self._server_manager.schedule_client_request(
            user_func = functools.partial(change_device_link, link_type, config), 
            ui_thread_callback= self._change_device_link_completed
        )
    
    def _change_device_link_completed(self, return_val:Optional[Tuple[DeviceLinkType, BaseLinkConfig]], error:Optional[Exception]) -> None:
        # Callback invoked once the server manager has a response from the server after we asked to change the device link
        if error is None:
            assert return_val is not None
            link_type, config = return_val
            self._device_config_dialog.change_success_callback()
            self._device_config_dialog.set_config(link_type, config)
        else:
            self._device_config_dialog.change_fail_callback(f"Failed:\n {error}")
        self.update_content()

    def set_server_label_value(self, value:ServerLabelValue) -> None:
        """Change the server status label"""
        prefix = 'Server:'
        if value == ServerLabelValue.Disconnected :
            self._server_status_label.set_color(StatusBarLabel.Color.RED)
            self._server_status_label.set_text(f"{prefix} Disconnected")
        elif value == ServerLabelValue.Disconnecting :
            self._server_status_label.set_color(StatusBarLabel.Color.YELLOW)
            self._server_status_label.set_text(f"{prefix} Stopping...")
        elif value == ServerLabelValue.Waiting:
            self._server_status_label.set_color(StatusBarLabel.Color.YELLOW)
            self._server_status_label.set_text(f"{prefix} Waiting...")
        elif value == ServerLabelValue.Connected:
            self._server_status_label.set_color(StatusBarLabel.Color.GREEN)
            self._server_status_label.set_text(f"{prefix} Connected")
        else:
            raise NotImplementedError(f"Unsupported label value {value}")
    
    def set_device_label(self, value:DeviceCommState) -> None:
        """Change the device label status"""
        prefix = 'Device:'
        if value == DeviceCommState.NA:
            self._device_status_label.set_color(StatusBarLabel.Color.RED)
            self._device_status_label.set_text(f"{prefix} N/A")
        elif value == DeviceCommState.ConnectedReady:
            self._device_status_label.set_color(StatusBarLabel.Color.GREEN)
            self._device_status_label.set_text(f"{prefix} Connected")
        elif value == DeviceCommState.Connecting:
            self._device_status_label.set_color(StatusBarLabel.Color.YELLOW)
            self._device_status_label.set_text(f"{prefix} Connecting")
        elif value == DeviceCommState.Disconnected:
            self._device_status_label.set_color(StatusBarLabel.Color.RED)
            self._device_status_label.set_text(f"{prefix} Disconnected")
        else:
            raise NotImplementedError(f"Unsupported device comm state value {value}")

    def set_device_comm_link_label(self, link_type:DeviceLinkType, operational:bool, config:Optional[BaseLinkConfig]) -> None:
        """Set the device link label with the actually loaded link on the server side"""
        prefix= "Link:"
        if link_type == DeviceLinkType.NONE:
            self._device_comm_link_label.set_text(f"{prefix} None")
        elif link_type == DeviceLinkType.TCP:
            config = cast(sdk.TCPLinkConfig, config)
            self._device_comm_link_label.set_text(f"{prefix} TCP {config.host}:{config.port}")
        elif link_type == DeviceLinkType.UDP:
            config = cast(sdk.UDPLinkConfig, config)
            self._device_comm_link_label.set_text(f"{prefix} UDP {config.host}:{config.port}")
        elif link_type == DeviceLinkType.Serial:
            config = cast(sdk.SerialLinkConfig, config)
            line = f"{config.port}@{config.baudrate} [D:{config.databits.name} S:{config.stopbits.name} P:{config.parity.name}]"
            self._device_comm_link_label.set_text(f"{prefix} Serial {line}")
        elif link_type == DeviceLinkType.RTT:
            config = cast(sdk.RTTLinkConfig, config)
            self._device_comm_link_label.set_text(f"{prefix} RTT {config.jlink_interface.name} ({config.target_device})")
        else:
            raise NotImplementedError("Unsupported device link type")
        
        self._device_comm_link_label.set_color(StatusBarLabel.Color.GREEN if operational else StatusBarLabel.Color.RED)


    def set_sfd_label(self, device_connected:bool, value:Optional[SFDInfo]) -> None:
        """Change the loaded SFD label"""
        prefix = 'SFD:'
        if value is None:
            self._sfd_status_label.setEnabled(device_connected)
            self._sfd_status_label.set_text(f'{prefix} None ')
            self._sfd_status_label.setToolTip("No Scrutiny Firmware Description file loaded")
        else:
            self._sfd_status_label.setEnabled(True)
            project_name = "Unnamed project"
            if value.metadata is not None:
                if value.metadata.project_name is not None:
                    project_name = value.metadata.project_name
                    if value.metadata.version is not None:
                        project_name += ' V' + value.metadata.version
            
            self._sfd_status_label.set_text(f'{prefix} {project_name}')
            self._sfd_status_label.setToolTip(f"Firmware ID: {value.firmware_id}")

    def set_datalogging_label(self, value:DataloggingInfo) -> None:
        """Change the datalogger state label"""
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

        self._datalogger_status_label.set_text(f"{prefix} {state_str[value.state]}{completion_str}")

    def emulate_connect_click(self)->None:
        """Programmatically cause a click on the server Connect menu."""
        if self._server_connect_action.isEnabled():
            self._server_connect_action.trigger()

    def update_content(self) -> None:
        """Update the status bar content"""
        if not self._server_manager.is_running():   # Server manager is either stopped or stopping
            self._device_details_action.setEnabled(False)
            self._device_comm_link_label.setEnabled(False)
            self._device_status_label.setEnabled(False)

            if self._server_manager.is_stopping():
                self._server_disconnect_action.setEnabled(False)
                self._server_connect_action.setEnabled(False)
                self.set_server_label_value(ServerLabelValue.Disconnecting)
            else:
                self._server_disconnect_action.setEnabled(False)
                self._server_connect_action.setEnabled(True)
                self.set_server_label_value(ServerLabelValue.Disconnected)
            self.set_device_label(DeviceCommState.NA)
            self.set_device_comm_link_label(DeviceLinkType.NONE, False, sdk.NoneLinkConfig())
            self.set_sfd_label(device_connected=False, value=None)
            self.set_datalogging_label(DataloggingInfo(state=DataloggerState.NA, completion_ratio=None))
        else:   # Server manager is running healthy
            self._server_disconnect_action.setEnabled(True)
            self._server_connect_action.setEnabled(False)
            
            server_state = self._server_manager.get_server_state()
            server_info = None

            if server_state == ServerState.Connected:   # We are connected to the server
                self.set_server_label_value(ServerLabelValue.Connected)
                server_info = self._server_manager.get_server_info()
                self._device_comm_link_label.setEnabled(True)
            else:   # Still waiting for a server to show up
                self.set_server_label_value(ServerLabelValue.Waiting)
                self._device_comm_link_label.setEnabled(False)
            
            # We have no server status available. Only available when the server is connected
            if server_info is None:
                self._device_status_label.setEnabled(False)
                self._device_details_action.setEnabled(False)
                self.set_device_label(DeviceCommState.NA)
                self.set_device_comm_link_label(DeviceLinkType.NONE, False, sdk.NoneLinkConfig())
                self.set_sfd_label(device_connected=False, value=None)
                self.set_datalogging_label(DataloggingInfo(state=DataloggerState.NA, completion_ratio=None))
            else:
                self.set_device_comm_link_label(server_info.device_link.type, server_info.device_link.operational, server_info.device_link.config)
                self.set_device_label(server_info.device_comm_state)
                self.set_sfd_label(device_connected=server_info.device_comm_state == DeviceCommState.ConnectedReady, value=server_info.sfd)
                self.set_datalogging_label(server_info.datalogging)
                
                self._device_status_label.setEnabled(server_info.device_link.operational and server_info.device_comm_state != DeviceCommState.NA)
                self._device_details_action.setEnabled(server_info.device_comm_state == DeviceCommState.ConnectedReady)
                        
