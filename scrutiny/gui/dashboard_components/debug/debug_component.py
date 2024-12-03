#    debug_component.py
#        A component used to develop the GUI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from typing import Dict,Any

from PySide6.QtWidgets import QFormLayout, QLabel, QLineEdit, QCheckBox, QRadioButton, QTextEdit
from PySide6.QtCore import QMimeData, Qt
from scrutiny.gui.dashboard_components.common.watchable_line_edit import WatchableLineEdit

from scrutiny.gui import assets

class DroppableTextEdit(QTextEdit):
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
    _test_textbox:QLineEdit
    _test_checkbox:QCheckBox
    _test_radio:QRadioButton
    _watchable_line_edit:WatchableLineEdit
    _dnd_text_edit:DroppableTextEdit



    def setup(self) -> None:
        layout = QFormLayout(self)
        self._nb_status_update = 0
        self._label_nb_status_update = QLabel(str(self._nb_status_update))
        self._test_textbox = QLineEdit()
        self._test_textbox.setMaximumWidth(100)
        self._test_checkbox = QCheckBox()
        self._test_radio = QRadioButton()
        self._watchable_line_edit = WatchableLineEdit()
        self._watchable_line_edit.setMaximumWidth(100)
        self._dnd_text_edit = DroppableTextEdit()
        self._dnd_text_edit.setMaximumSize(600,300)

        layout.addRow(QLabel("Component name:"), QLabel(self._NAME))
        layout.addRow(QLabel("Instance name:"), QLabel(self.instance_name))
        layout.addRow(QLabel("Status update count:"), self._label_nb_status_update)
        layout.addRow(QLabel("Test textbox:"), self._test_textbox)
        layout.addRow(QLabel("Test checkbox:"), self._test_checkbox)
        layout.addRow(QLabel("Test radio button:"), self._test_radio)
        layout.addRow(QLabel("Droppable line edit:"), self._watchable_line_edit)
        layout.addRow(QLabel("Drag & Drop zone:"), self._dnd_text_edit)

        self.server_manager.signals.status_received.connect(self.update_status)

    def update_status(self) -> None:
        self._nb_status_update += 1
        self._label_nb_status_update.setText(str(self._nb_status_update))

    def teardown(self) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        return {
            "textbox" : self._test_textbox.text(),
            "checkbox" : self._test_checkbox.checkState().value,
            "radio" : self._test_radio.isChecked()
        }

    def load_state(self, state:Dict[Any, Any]) -> None:
        if 'textbox' in state:
            self._test_textbox.setText(state['textbox'])
        
        if 'checkbox' in state:
            self._test_checkbox.setCheckState(Qt.CheckState(state['checkbox']))

        if 'radio' in state:
            self._test_radio.setChecked(state['radio'])
        
