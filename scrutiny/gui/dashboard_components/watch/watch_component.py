#    watch_component.py
#        A component to look at the value of watchable items broadcast by the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from typing import Dict, Any

from PySide6.QtWidgets import QVBoxLayout, QLabel

from scrutiny.gui import assets

class WatchComponent(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("eye-96x128.png")
    _NAME = "Watch Window"

    def setup(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("YAYAYA : " + self.get_name()))

    def teardown(self) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        raise NotImplementedError()

    def load_state(self) -> Dict[Any, Any]:
        raise NotImplementedError()
