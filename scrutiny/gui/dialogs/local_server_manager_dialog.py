
__all__ = ['LocalServerManagerDialog']

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QDialog, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QPlainTextEdit, QGroupBox
from PySide6.QtGui import QIntValidator, QPixmap

from scrutiny.gui.core.local_server_runner import LocalServerRunner
from scrutiny.gui.widgets.validable_line_edit import ValidableLineEdit
from scrutiny.gui.widgets.feedback_label import FeedbackLabel

from scrutiny.gui.tools.validators import IpPortValidator
from scrutiny.gui import assets

from scrutiny import tools
from scrutiny.tools.typing import *

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

class LogViewer(QPlainTextEdit):
    """A read-only multiline text edit area that displays log lines """
    MAX_LINE = 25
    _log_lines:List[str]

    @tools.copy_type(QPlainTextEdit.__init__)
    def __init__(self, *args:Any, **kwargs:Any) -> None:
        super().__init__(*args, **kwargs)
        self.setReadOnly(True)
        self._log_lines = []
    
    def add_lines(self, lines:List[str]) -> None:
        self._log_lines.extend(lines)
        if len(self._log_lines) > self.MAX_LINE:
            self._log_lines = self._log_lines[-self.MAX_LINE:]
        scrollbar = self.verticalScrollBar()
        previous_value = scrollbar.value()
        autoscroll = True if scrollbar.value() == scrollbar.maximum() else False

        self.setPlainText('\n'.join(self._log_lines))
        if autoscroll:
            scrollbar.setValue(scrollbar.maximum())
        else:
            scrollbar.setValue(previous_value)

    def add_line(self, line:str) -> None:
        self.add_lines([line])
    
    def sizeHint(self):
        return QSize(600,300)

class LocalServerManagerDialog(QDialog):
    """A dialog meant for the user to start/stop a local isntance of the Scrutiny server.
    Controls an appwide LocalServerRunner"""

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
    _crash_feedback_label:FeedbackLabel
    """A label that shows error (when the server exits by itself)"""
    _log_viewer:LogViewer
    """The log viewer box"""

    def __init__(self, parent:QWidget, runner:LocalServerRunner) -> None:
        super().__init__(parent)
        self.setWindowTitle("Local Server")
        self._runner = runner
        self._log_line_count = 0

        main_vlayout = QVBoxLayout(self)
        top_menu =  QGroupBox("Controls")
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
        self._txt_port.setText("8765")
        self._txt_port.setMaximumWidth(self._txt_port.sizeHint().width())

        self._crash_feedback_label = FeedbackLabel()
        self._crash_feedback_label.setVisible(False)
        
        self._btn_start = QPushButton("Start")
        self._btn_stop = QPushButton("Stop")
        self._log_viewer = LogViewer()

        top_menu_hlayout.addWidget(port_label_txtbox)
        top_menu_hlayout.addWidget(self._state_label)
        top_menu_hlayout.addWidget(self._btn_start)
        top_menu_hlayout.addWidget(self._btn_stop)

        main_vlayout.addWidget(top_menu)
        main_vlayout.addWidget(self._crash_feedback_label)
        main_vlayout.addWidget(self._log_viewer)

        self._runner.signals.state_changed.connect(self.update_state)
        self._runner.signals.abnormal_termination.connect(self._abnormal_termination)
        self._runner.signals.stdout.connect(self._log_viewer.add_line)
        self._runner.signals.stderr.connect(self._log_viewer.add_line)
        self._btn_start.pressed.connect(self._try_start)
        self._btn_stop.pressed.connect(self._try_stop)

        self.update_state(LocalServerRunner.State.STOPPED)

    def update_state(self, state:LocalServerRunner.State) -> None:
        self._state_label.set_state(state, pid = self._runner.get_process_id())
        self._txt_port.setEnabled(state == LocalServerRunner.State.STOPPED)
        self._btn_start.setEnabled(state == LocalServerRunner.State.STOPPED)
        self._btn_stop.setEnabled(state in ( LocalServerRunner.State.STARTING, LocalServerRunner.State.STARTED ))

    def _try_start(self) -> None:
        self._crash_feedback_label.clear()
        self._crash_feedback_label.setVisible(False)
        valid = self._txt_port.validate_expect_valid()
        if not valid:
            return 
        port = int(self._txt_port.text())
        self._log_viewer.add_line('---------')
        self._runner.start(port)
    
    def _try_stop(self) -> None:
        self._runner.stop()
    
    def _abnormal_termination(self) -> None:
        self._crash_feedback_label.set_error("Server exited abnormally")
        self._crash_feedback_label.setVisible(True)


        

    
