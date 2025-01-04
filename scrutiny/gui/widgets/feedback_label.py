from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout, QSizePolicy
from PySide6.QtCore import Qt

from scrutiny.gui import assets
from scrutiny import tools

from typing import Any

class FeedbackLabel(QWidget):
    _icon_label:QLabel
    _text_label:QLabel

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

    def clear(self) -> None:
        self._icon_label.clear()
        self._text_label.clear()

    def icon_label(self) -> QLabel:
        return self._icon_label
    
    def text_label(self) -> QLabel:
        return self._text_label

    def set_error(self, text:str) -> None:
        self._text_label.setText(text)
        self._icon_label.setPixmap(assets.load_pixmap(assets.Icons.Error))

    def set_warning(self, text:str) -> None:
        self._text_label.setText(text)
        self._icon_label.setPixmap(assets.load_pixmap(assets.Icons.Warning))

    def set_info(self, text:str) -> None:
        self._text_label.setText(text)
        self._icon_label.setPixmap(assets.load_pixmap(assets.Icons.Info))

    def set_normal(self, text:str) -> None:
        self._text_label.setText(text)
        self._icon_label.clear()
