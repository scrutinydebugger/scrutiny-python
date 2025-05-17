#    local_server_manager_dialog.py
#        A dialog that interract with the app-wide LocalServerRunner.
#        Let the user start/stop a local instance of the runner
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['LocalServerManagerDialog']

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QGroupBox
from PySide6.QtGui import QIntValidator, QPixmap

from scrutiny.gui.core.local_server_runner import LocalServerRunner
from scrutiny.gui.widgets.validable_line_edit import ValidableLineEdit
from scrutiny.gui.widgets.feedback_label import FeedbackLabel
from scrutiny.gui.widgets.log_viewer import LogViewer


from scrutiny.tools.typing import *




        

    
