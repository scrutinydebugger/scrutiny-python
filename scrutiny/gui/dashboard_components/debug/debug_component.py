#    debug_component.py
#        A component used to develop the GUI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from typing import Dict,Any

from PySide6.QtWidgets import QFormLayout, QLabel,  QTextEdit
from PySide6.QtCore import QMimeData

from scrutiny.gui import assets
from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from scrutiny import tools


class DroppableTextEdit(QTextEdit):
    @tools.copy_type(QTextEdit.__init__)
    def __init__(self, *args:Any, **kwargs:Any) -> None:
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

    def canInsertFromMimeData(self, source: QMimeData) -> bool:
        return source.hasFormat('application/json')
    
    def insertFromMimeData(self, source: QMimeData) -> None:
        self.setText(source.data('application/json').toStdString())

class DebugComponent(ScrutinyGUIBaseComponent):
    _ICON = assets.get("debug-96x128.png")
    _NAME = "Debug"

    _label_nb_status_update:QLabel
    _nb_status_update:int
    _dnd_text_edit:DroppableTextEdit

    def setup(self) -> None:
        layout = QFormLayout(self)
        self._nb_status_update = 0
        self._dnd_text_edit = DroppableTextEdit()
        self._dnd_text_edit.setMaximumSize(400,300)

        layout.addRow(QLabel("Component name:"), QLabel(self._NAME))
        layout.addRow(QLabel("Instance name:"), QLabel(self.instance_name))
        layout.addRow(QLabel("Drag & Drop zone:"), self._dnd_text_edit)

    def teardown(self) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        return {}

    def load_state(self, state:Dict[Any, Any]) -> None:
        pass
