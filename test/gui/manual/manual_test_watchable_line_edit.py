#    manual_test_watchable_line_edit.py
#        A test suite for the WatchableLineEdit widget. A textbox that can receive watchables
#        through drag&drop
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

if __name__ != '__main__' : 
    raise RuntimeError("This script is expected to run from the command line")

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from manual_test_base import make_manual_test_app
app = make_manual_test_app()

from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QCheckBox, QLabel, QHBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator
from scrutiny.gui.widgets.watchable_line_edit import WatchableLineEdit
from scrutiny.gui.components.globals.varlist.varlist_component import VarListComponent
from scrutiny.gui.core.watchable_registry import WatchableRegistry

from scrutiny.sdk import WatchableType, WatchableConfiguration, EmbeddedDataType
from test.gui.fake_server_manager import FakeServerManager

window = QMainWindow()
central_widget = QWidget()
line_edit = WatchableLineEdit(window)
line_edit_double_validator = WatchableLineEdit(window)
line_edit_double_validator.setValidator(QDoubleValidator(-100,100,4,window))
window.setCentralWidget(central_widget)
layout = QVBoxLayout(central_widget)

registry = WatchableRegistry()
server_manager = FakeServerManager(registry)
varlist = VarListComponent(main_window=window, instance_name="varlist1", server_manager=server_manager, watchable_registry=registry)
varlist.setup()

registry.write_content({
    WatchableType.Alias : {
        '/my_var' : WatchableConfiguration('my_var', WatchableType.Variable, EmbeddedDataType.float32, enum=None)
    },
    WatchableType.RuntimePublishedValue : {
        '/my_rpva' : WatchableConfiguration('my_rpv', WatchableType.RuntimePublishedValue, EmbeddedDataType.float32, enum=None)
    },
    WatchableType.Variable : {
        '/my_alias' : WatchableConfiguration('my_alias', WatchableType.Alias, EmbeddedDataType.float32, enum=None),
        '/alias with very long name' : WatchableConfiguration('my_alias', WatchableType.Alias, EmbeddedDataType.float32, enum=None)
    },
})
varlist.reload_model([WatchableType.Alias, WatchableType.RuntimePublishedValue, WatchableType.Variable])

chk_text_mode = QCheckBox("Text mode enabled (both)")
def state_changed(state:Qt.CheckState):
    if state == Qt.CheckState.Checked:
        line_edit.set_text_mode_enabled(True)
        line_edit_double_validator.set_text_mode_enabled(True)
    else:
        line_edit.set_text_mode_enabled(False)
        line_edit_double_validator.set_text_mode_enabled(False)
        
chk_text_mode.checkStateChanged.connect(state_changed)
chk_text_mode.setCheckState(Qt.CheckState.Checked)

widget_lineedit = QWidget()
layout1 = QHBoxLayout(widget_lineedit)
layout1.addWidget(QLabel("No Validator"))
layout1.addWidget(line_edit)

widget_lineedit_double_validator = QWidget()
layout2 = QHBoxLayout(widget_lineedit_double_validator)
layout2.addWidget(QLabel("Validator"))
layout2.addWidget(line_edit_double_validator)

layout.addWidget(widget_lineedit)
layout.addWidget(widget_lineedit_double_validator)
layout.addWidget(chk_text_mode)
layout.addWidget(varlist)

window.show()

sys.exit(app.exec())
