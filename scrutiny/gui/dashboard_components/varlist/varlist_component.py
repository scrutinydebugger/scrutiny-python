
from scrutiny.gui.dashboard_components.base_component import ScrutinyGUIBaseComponent
from typing import Dict, Any

from qtpy.QtWidgets import QVBoxLayout, QLabel

from scrutiny.gui import assets

class VarListComponent(ScrutinyGUIBaseComponent):
    instance_name : str

    _ICON = assets.get("treelist-96x128.png")
    _NAME = "Variable List"

    def setup(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("YAYAYA : " + self.get_name()))

    def teardown(self) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        raise NotImplementedError()

    def load_state(self) -> Dict[Any, Any]:
        raise NotImplementedError()