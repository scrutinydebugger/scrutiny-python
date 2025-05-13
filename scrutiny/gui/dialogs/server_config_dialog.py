#    server_config_dialog.py
#        A dialog to edit the connection parameter of the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['ServerConfigDialog']

import enum

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QWidget, QVBoxLayout,QPushButton, QHBoxLayout, QGroupBox, QFormLayout, QRadioButton
from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator, QPixmap

from scrutiny.gui.widgets.validable_line_edit import ValidableLineEdit
from scrutiny.gui.widgets.feedback_label import FeedbackLabel
from scrutiny.gui.widgets.log_viewer import LogViewer

from scrutiny.gui.tools.validators import IpPortValidator, NotEmptyValidator
from scrutiny.gui.core.server_manager import ServerConfig
from scrutiny.gui.core.local_server_runner import LocalServerRunner
from scrutiny.gui.core.persistent_data import gui_persistent_data, AppPersistentData
from scrutiny.gui import assets

from scrutiny.tools.typing import *

DEFAULT_HOSTNAME = 'localhost'
DEFAULT_PORT = 8765

class LocalServerStateLabel(QWidget):
    """A label that shows the state of the server with a colored icon (green/yellow/red)"""

    _indicator_label:QLabel
    """The label that hold the icon part"""
    _text_label:QLabel
    """The label that hold the text part"""

    ICON_RED:QPixmap    
    ICON_YELLOW:QPixmap
    ICON_GREEN:QPixmap

    def __init__(self, parent:QWidget) -> None:
        super().__init__(parent)
        self.ICON_RED = assets.load_tiny_icon_as_pixmap(assets.Icons.SquareRed)
        self.ICON_YELLOW = assets.load_tiny_icon_as_pixmap(assets.Icons.SquareYellow)
        self.ICON_GREEN = assets.load_tiny_icon_as_pixmap(assets.Icons.SquareGreen)
        
        self._indicator_label = QLabel()
        self._text_label = QLabel()
        layout = QHBoxLayout(self)
        layout.addWidget(self._indicator_label)
        layout.addWidget(self._text_label)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.setContentsMargins(0,0,0,0)
        
    
    def set_state(self, state:LocalServerRunner.State, pid:Optional[int]) -> None:
        """Update the display based on the state of the runner"""
        if state == LocalServerRunner.State.STOPPED:
            text = "Stopped"
            icon = self.ICON_RED
        elif state == LocalServerRunner.State.STARTING:
            text = "Starting"
            icon = self.ICON_YELLOW
        elif state == LocalServerRunner.State.STARTED:
            text = f"Running"
            if pid is not None:
                text += f"\n(PID: {pid})"
            icon = self.ICON_GREEN
        elif state == LocalServerRunner.State.STOPPING:
            text = "Stopping"
            icon = self.ICON_YELLOW
        else:
            raise NotImplementedError("Unknown local server state")
        
        self._indicator_label.setPixmap(icon)
        self._text_label.setText(text)

class LocalServerConfigurator(QWidget):
    """A widget meant for the user to start/stop a local isntance of the Scrutiny server.
    Controls an appwide LocalServerRunner"""

    class PersistentData:
        LOCAL_PORT = 'local_port'


    _port:int
    """Port configured. Used for reloading the textbox on cancel"""
    _runner:LocalServerRunner
    """The local server runner that controls the subprocess"""
    _txt_port:ValidableLineEdit
    """The port textbox"""
    _btn_start:QPushButton
    """Start button"""
    _btn_stop:QPushButton
    """Stop button"""
    _state_label:LocalServerStateLabel
    """The label that says Running/Stopped/Stopping/Starting with a colored icon"""
    _feedback_label:FeedbackLabel
    """A label that shows error (when the server exits by itself)"""
    _log_viewer:LogViewer
    """The log viewer box"""
    _persistent_data:AppPersistentData


    def __init__(self, parent:QWidget, runner:LocalServerRunner) -> None:
        super().__init__(parent)
        self.setWindowTitle("Local Server")
        self._runner = runner
        self._log_line_count = 0
        self._persistent_data = gui_persistent_data.get_namespace(self.__class__.__name__)

        main_vlayout = QVBoxLayout(self)
        top_menu =  QWidget()
        top_menu_hlayout = QHBoxLayout(top_menu)
        top_menu_hlayout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self._state_label = LocalServerStateLabel(self)
        self._txt_port = ValidableLineEdit(
            hard_validator=QIntValidator(0, 0xFFFF),
            soft_validator=IpPortValidator()
        )
        
        port_label_txtbox = QWidget()
        port_label_txtbox_layout = QHBoxLayout(port_label_txtbox)
        port_label_txtbox_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        port_label_txtbox_layout.setContentsMargins(0,0,0,0)
        port_label = QLabel("Port: ")
        port_label.setMaximumWidth(port_label.sizeHint().width())
        port_label_txtbox_layout.addWidget(port_label)
        port_label_txtbox_layout.addWidget(self._txt_port)
        
        self._txt_port.setText(str(self._persistent_data.get_int(self.PersistentData.LOCAL_PORT, DEFAULT_PORT)))
        self._txt_port.setMaximumWidth(self._txt_port.sizeHint().width())

        self._feedback_label = FeedbackLabel()
        self._feedback_label.setVisible(False)
        
        self._btn_start = QPushButton("Start")
        self._btn_stop = QPushButton("Stop")
        self._log_viewer = LogViewer(self, 100)

        top_menu_hlayout.addWidget(port_label_txtbox)
        top_menu_hlayout.addWidget(self._state_label)
        top_menu_hlayout.addWidget(self._btn_start)
        top_menu_hlayout.addWidget(self._btn_stop)

        main_vlayout.addWidget(top_menu)
        main_vlayout.addWidget(self._feedback_label)
        main_vlayout.addWidget(self._log_viewer)

        self._runner.signals.state_changed.connect(self.update_state)
        self._runner.signals.abnormal_termination.connect(self._abnormal_termination_slot)
        self._runner.signals.stdout.connect(self._log_viewer.add_line)
        self._runner.signals.stderr.connect(self._log_viewer.add_line)
        self._btn_start.pressed.connect(self._try_start)
        self._btn_stop.pressed.connect(self._try_stop)

        self.update_state(LocalServerRunner.State.STOPPED)

    def update_state(self, state:LocalServerRunner.State) -> None:
        """Called when the runner state changes"""
        self._state_label.set_state(state, pid = self._runner.get_process_id())
        self._txt_port.setEnabled(state == LocalServerRunner.State.STOPPED)
        self._btn_start.setEnabled(state == LocalServerRunner.State.STOPPED)
        self._btn_stop.setEnabled(state in ( LocalServerRunner.State.STARTING, LocalServerRunner.State.STARTED ))

    def _try_start(self) -> None:
        """Starts the runner if the port number is correct"""
        self.clear_error()
        port = self.get_ui_port()
        if port is None:
            return
        self._log_viewer.add_line('---------')
        self._runner.start(port)
    
    def _try_stop(self) -> None:
        """Stops the runner"""
        self._runner.stop()
    
    def _abnormal_termination_slot(self) -> None:
        """The running thread emits a signal if the subprocess exits without a request for it."""
        self.display_error("Server exited abnormally")
    
    def display_error(self, err:str) -> None:
        """Display an error message on the feedback label"""
        self._feedback_label.set_error(err)
        self._feedback_label.setVisible(True)
    
    def clear_error(self) -> None:
        """Clear the feedback label from its error emssage"""
        self._feedback_label.clear()
        self._feedback_label.setVisible(False)

    def is_running(self) -> bool:
        """Return true if the subprocess is allive and well"""
        return self._runner.get_state() == LocalServerRunner.State.STARTED
    
    def get_running_port(self) -> Optional[int]:
        """Return the port on which the subprocess is listening on. ``None`` if no subprocess is runinng"""
        return self._runner.get_port()

    def get_ui_port(self) -> Optional[int]:
        """Return the port number written in the UI textbox. ``None`` if the value is not a valid port number"""
        if self._txt_port.is_valid():
            return int(self._txt_port.text())
        return None

    def is_valid(self) -> bool:
        """Return True if the UI is in a valid state for connecting to the server. Require a valid port number and a running subprocess"""
        v1 = (self._txt_port.is_valid())
        v2 = (self._runner.get_state() == LocalServerRunner.State.STARTED)
        return v1 and v2

    def validate(self) -> bool:
        """Check if the widget is in a valid state for connection. Highlight in the UI what needs to be fixed in order to be valid."""
        self._txt_port.validate_expect_valid()
        
        if self._runner.get_state() != LocalServerRunner.State.STARTED:
            self.display_error("Server not started")
        else:
            self.clear_error()

        return self.is_valid()
    
    def set_normal_state(self) -> None:
        """Undo the visual feedback caused by ``validate``"""
        self._txt_port.set_default_state()

    def commit_ui_data(self) -> None:
        """Store the UI values into the persistent storage"""
        if self.is_valid():
            port = self.get_ui_port()
            assert port is not None
            self._persistent_data.set(self.PersistentData.LOCAL_PORT, port)

class RemoteServerConfigurator(QWidget):
    """A widget to edit the connection parameters to a remote server"""

    class PersistentData:
        HOSTNAME = 'server_hostname'
        PORT = 'server_port'

    _hostname:str
    """The active hostname"""
    _port:int
    """The active port number """

    _hostname_textbox:ValidableLineEdit
    """The textbox for editing the hostname"""
    _port_textbox:ValidableLineEdit
    """The hostname for editing the port number"""
    _persistent_data:AppPersistentData
    """A handle to a specific storage namespace"""

    def __init__(self, parent:QWidget) -> None:
        super().__init__(parent)
        self._persistent_data = gui_persistent_data.get_namespace(self.__class__.__name__)
        self._hostname_textbox = ValidableLineEdit(soft_validator=NotEmptyValidator())
        self._port_textbox = ValidableLineEdit(hard_validator=QIntValidator(0,0xFFFF), soft_validator=IpPortValidator())

        self._hostname_textbox.textChanged.connect(self._hostname_textbox.validate_expect_not_wrong_default_slot)
        self._port_textbox.textChanged.connect(self._port_textbox.validate_expect_not_wrong_default_slot)

        self._hostname_textbox.setMaximumWidth(self._hostname_textbox.sizeHint().width())
        self._port_textbox.setMaximumWidth(self._port_textbox.sizeHint().width())

        hlayout = QFormLayout(self)
        hlayout.setAlignment(Qt.AlignmentFlag.AlignRight)
        hlayout.addRow("Hostname: ", self._hostname_textbox)
        hlayout.addRow("Port:  ", self._port_textbox)
        self.set_hostname(self._persistent_data.get_str(self.PersistentData.HOSTNAME, DEFAULT_HOSTNAME))
        self.set_port(self._persistent_data.get_int(self.PersistentData.PORT, DEFAULT_PORT))

    def get_port(self) -> int:
        """Returns the effective port number, not the one in the textbox."""
        return self._port

    def get_hostname(self) -> str:
        """Returns the effective hostname, not the one in the textbox"""
        return self._hostname
    
    def set_port(self, port:int) -> None:
        """Change the effective port number and update the port textbox too"""
        self._port = port
        self._port_textbox.setText(str(port))

    def set_hostname(self, hostname:str) -> None:
        """Change the effective hostname number and update the hostname textbox too"""
        self._hostname = hostname
        self._hostname_textbox.setText(hostname)

    def reset(self) -> None:
        """Update the UI with the effective host/port. To be called when the user clicks Cancel"""
        self.set_hostname(self.get_hostname())
        self.set_port(self.get_port())

    def validate(self) -> bool:
        """Check if the UI is in a state that permit a connection to the server. Highlight the widgets that are preventing the valid state"""
        v1 = self._hostname_textbox.validate_expect_valid()
        v2 = self._port_textbox.validate_expect_valid()
        return v1 and v2
    
    def set_normal_state(self) -> None:
        """Undo the visual feedback caused by ``validate``"""
        self._hostname_textbox.set_default_state()
        self._port_textbox.set_default_state()

    def commit_ui_data(self) -> None:
        """Save the data from the UI into the persistent storage to reload the same content on next startup"""
        if self._port_textbox.is_valid() and self._hostname_textbox.is_valid():
            self._hostname = self._hostname_textbox.text()
            self._port = int(self._port_textbox.text()) # Validator is supposed to guarantee the validity of this
            self._persistent_data.set(self.PersistentData.HOSTNAME, self._hostname)
            self._persistent_data.set(self.PersistentData.PORT, self._port)

class ServerConfigDialog(QDialog):
    """A dialog to edit the connection parameter of the server"""

    class ServerType(enum.Enum):
        LOCAL = enum.auto()
        REMOTE = enum.auto()

    _radio_remote_server:QRadioButton
    """Radio button for "Remote" """
    _radio_local_server:QRadioButton
    """Radio button for "Local" """
    _remote_server_configurator:RemoteServerConfigurator
    """The widget shown when the user select "Remote" """
    _local_server_configurator:LocalServerConfigurator
    """The widget shown when the user select "Local" """
    _apply_callback:Callable[["ServerConfigDialog"], None]
    """A function to be called when the user click OK and the configuration is valid"""
    _buttons:QDialogButtonBox
    """The buttons"""
    _server_type:ServerType
    """The type of server configuration presently selected (Local or remote)"""

    def __init__(self, 
                 parent:QWidget, 
                 apply_callback:Callable[["ServerConfigDialog"], None],
                 local_server_runner:LocalServerRunner) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.WindowTitleHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setWindowTitle("Server configuration")
        self.setMinimumSize(200,100)    # Default minimum size is too big for hte remote server case.
        self._apply_callback = apply_callback
        radio_btn_group = QGroupBox("Server type")
        radio_btn_group_hlayout = QHBoxLayout(radio_btn_group)
        radio_btn_group_hlayout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._radio_remote_server = QRadioButton("Remote Server", radio_btn_group)
        self._radio_local_server = QRadioButton("Local Server", radio_btn_group)
        radio_btn_group_hlayout.addWidget(self._radio_local_server)
        radio_btn_group_hlayout.addWidget(self._radio_remote_server)

        self._remote_server_configurator = RemoteServerConfigurator(self)
        self._local_server_configurator = LocalServerConfigurator(self, local_server_runner)

        main_vlayout = QVBoxLayout(self)
        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel) # cast is for mypy issue
        main_vlayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_vlayout.addWidget(radio_btn_group)
        main_vlayout.addWidget(self._local_server_configurator)
        main_vlayout.addWidget(self._remote_server_configurator)
        main_vlayout.addWidget(self._buttons)
        
        self._buttons.accepted.connect(self._btn_ok_click)
        self._buttons.rejected.connect(self._btn_cancel_click)

        self._radio_local_server.toggled.connect(self._radio_local_server_toggled_slot)
        self._radio_remote_server.toggled.connect(self._radio_remote_server_toggled_slot)

        self._server_type = self.ServerType.LOCAL
        self._radio_local_server.setChecked(True)

    def reset(self) -> None:
        """Callend on Cancel button"""
        self._remote_server_configurator.reset()

    def _btn_ok_click(self) -> None:
        """Called on OK button"""
        self._apply_and_connect()

    def _apply_and_connect(self) -> None:
        self._remote_server_configurator.set_normal_state()
        self._local_server_configurator.set_normal_state()

        if self._use_local_server():
            valid_config = self._local_server_configurator.validate()
            if valid_config:
                self._local_server_configurator.commit_ui_data()
        else:
            valid_config = self._remote_server_configurator.validate()
            if valid_config:
                self._remote_server_configurator.commit_ui_data()

        if valid_config:
            self._apply_callback(self)
            self.close()

    def _btn_cancel_click(self) -> None:
        """Called on Cancel button"""
        self.reset()
        self.close()

    def _use_local_server(self) -> bool:
        return self._radio_local_server.isChecked()
    
    def get_config(self) -> Optional[ServerConfig]:
        if self._server_type == self.ServerType.LOCAL:
            if not self._local_server_configurator.is_running():
                return None
            port = self._local_server_configurator.get_running_port()
            if port is None:
                return None
            
            return ServerConfig(
                hostname='localhost',
                port = port
            )
        elif self._server_type == self.ServerType.REMOTE:
            return ServerConfig(
                hostname=self._remote_server_configurator.get_hostname(),
                port=self._remote_server_configurator.get_port()
            )
        else:
            raise NotImplementedError("Unsupported server connection type")

    def _radio_local_server_toggled_slot(self, checked:bool) -> None:
        """When Local radio button is clicked"""
        if checked:
            self._set_server_type(self.ServerType.LOCAL)

    def _radio_remote_server_toggled_slot(self, checked:bool) -> None:
        """When Remote radio button is clicked"""
        if checked:
            self._set_server_type(self.ServerType.REMOTE)
    
    def _set_server_type(self, server_type:ServerType) -> None:
        """Change the type of server connection"""
        if server_type == self.ServerType.LOCAL:
            self._remote_server_configurator.setVisible(False)
            self._local_server_configurator.setVisible(True)
        elif server_type == self.ServerType.REMOTE:
            self._remote_server_configurator.setVisible(True)
            self._local_server_configurator.setVisible(False)
        else:
            raise NotImplementedError("Unsupported server type")
        self._server_type = server_type
        self.resize(self.sizeHint())
