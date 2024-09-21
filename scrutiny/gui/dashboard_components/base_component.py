__all__ = ['ScrutinyGUIBaseComponent']

from abc import ABC, abstractmethod

from qtpy.QtWidgets import QWidget
from qtpy.QtGui import QPixmap
from typing import Dict, cast

class ScrutinyGUIBaseComponent(QWidget):
    pass

    @classmethod
    def get_icon(cls) -> QPixmap:
        if not hasattr(cls, '_ICON'):
            raise RuntimeError(f"Class {cls.__name__} require the _ICON to be set")
        return  QPixmap(str(getattr(cls, '_ICON')))

    @classmethod
    def get_name(cls) -> str: 
        if not hasattr(cls, '_NAME'):
            raise RuntimeError(f"Class {cls.__name__} require the _NAME to be set")
        return cast(str, getattr(cls, '_NAME'))

    @abstractmethod
    def setup(self, instance_name:str):
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
