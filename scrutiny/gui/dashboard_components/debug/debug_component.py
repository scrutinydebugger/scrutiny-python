
from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from typing import Dict

from qtpy.QtWidgets import QVBoxLayout, QLabel

from scrutiny.gui import assets

class DebugComponent(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("debug-96x128.png")
    _NAME = "Debug"

    def setup(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel())

    def teardown(self):
        pass

    def get_state(self) -> Dict:
        pass

    def load_state(self) -> Dict:
        pass
