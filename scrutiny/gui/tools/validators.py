__all__ = ['IpPortValidator', 'NotEmptyValidator']

from qtpy.QtGui import  QValidator
from qtpy.QtWidgets import  QWidget

from typing import Optional

class IpPortValidator(QValidator):
    def validate(self, val:str, pos:int):
        port_valid = True
        
        if len(val) == 0:
            return (QValidator.State.Intermediate, val, pos)
        
        try:
            port = int(val)
        except Exception:
            return (QValidator.State.Invalid, val, pos)
        
        if port_valid:
            if port<=0 or port>0xFFFF:
                return (QValidator.State.Invalid, val, pos)
        
        return (QValidator.State.Acceptable, val, pos)

class NotEmptyValidator(QValidator):
    _empty_state: QValidator.State

    def __init__(self, empty_state:QValidator.State=QValidator.State.Intermediate, parent:Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._empty_state = empty_state
    def validate(self, val:str, pos:int):
        if isinstance(val, str):
            if len(val) == 0:
                return (self._empty_state, val, pos)
        
        return (QValidator.State.Acceptable, val, pos)
