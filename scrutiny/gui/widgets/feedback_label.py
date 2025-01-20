#    feedback_label.py
#        A label that can display messages to the suer with success/warning/info/error facilities
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import enum

from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout, QSizePolicy
from PySide6.QtCore import Qt

from scrutiny.gui import assets
from scrutiny import tools

from typing import Any

class FeedbackLabel(QWidget):

    class MessageType(enum.Enum):
        INFO = enum.auto()
        WARNING = enum.auto()
        ERROR = enum.auto()
        NORMAL = enum.auto()
        
    _icon_label:QLabel
    _text_label:QLabel
    _actual_msg_type:MessageType

    @tools.copy_type(QWidget.__init__)
    def __init__(self, *args:Any, **kwargs:Any) -> None:
        super().__init__(*args, **kwargs)
        self._icon_label = QLabel()
        self._text_label = QLabel()
        self._text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout = QHBoxLayout(self)
        layout.addWidget(self._icon_label)
        layout.addWidget(self._text_label)
        self._icon_label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        self._text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._actual_msg_type = self.MessageType.NORMAL

    def clear(self) -> None:
        self._icon_label.clear()
        self._text_label.clear()
        self._actual_msg_type = self.MessageType.NORMAL

    def icon_label(self) -> QLabel:
        return self._icon_label
    
    def text_label(self) -> QLabel:
        return self._text_label

    def set_error(self, text:str) -> None:
        self._text_label.setText(text)
        self._icon_label.setPixmap(assets.load_tiny_icon_as_pixmap(assets.Icons.Error))
        self._actual_msg_type = self.MessageType.ERROR

    def set_warning(self, text:str) -> None:
        self._text_label.setText(text)
        self._icon_label.setPixmap(assets.load_tiny_icon_as_pixmap(assets.Icons.Warning))
        self._actual_msg_type = self.MessageType.WARNING

    def set_info(self, text:str) -> None:
        self._text_label.setText(text)
        self._icon_label.setPixmap(assets.load_tiny_icon_as_pixmap(assets.Icons.Info))
        self._actual_msg_type = self.MessageType.INFO

    def set_normal(self, text:str) -> None:
        self._text_label.setText(text)
        self._icon_label.clear()
        self._actual_msg_type = self.MessageType.NORMAL

    def get_message_type(self) -> MessageType:
        return self._actual_msg_type
    
    def is_info(self) -> bool:
        return self.get_message_type() == self.MessageType.INFO
    
    def is_warning(self) -> bool:
        return self.get_message_type() == self.MessageType.WARNING
    
    def is_error(self) -> bool:
        return self.get_message_type() == self.MessageType.ERROR
    
    def is_normal(self) -> bool:
        return self.get_message_type() == self.MessageType.NORMAL
