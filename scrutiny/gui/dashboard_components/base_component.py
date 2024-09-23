__all__ = ['ScrutinyGUIBaseComponent']

from abc import ABC, abstractmethod

from qtpy.QtWidgets import QWidget
from qtpy.QtGui import QIcon
from typing import Dict, cast, TYPE_CHECKING

if TYPE_CHECKING:   # Prevent circular dependency
    from scrutiny.gui.main_window import MainWindow

class ScrutinyGUIBaseComponent(QWidget):
    instance_name:str
    main_window:"MainWindow"

    def __init__(self, main_window:"MainWindow", instance_name:str) -> None:
        self.instance_name = instance_name
        self.main_window = main_window
        super().__init__()

    @classmethod
    def get_icon(cls) -> QIcon:
        if not hasattr(cls, '_ICON'):
            raise RuntimeError(f"Class {cls.__name__} require the _ICON to be set")
        return  QIcon(str(getattr(cls, '_ICON')))

    @classmethod
    def get_name(cls) -> str: 
        if not hasattr(cls, '_NAME'):
            raise RuntimeError(f"Class {cls.__name__} require the _NAME to be set")
        return cast(str, getattr(cls, '_NAME'))

    @abstractmethod
    def setup(self):
        pass

    @abstractmethod
    def teardown(self):
        pass

    @abstractmethod
    def get_state(self) -> Dict:
        pass

    @abstractmethod
    def load_state(self) -> Dict:
        pass
