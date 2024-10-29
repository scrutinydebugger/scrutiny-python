#    validable_line_edit.py
#        An extension of QLine edit that can accept 2 validator. One enforced by Qt, the other
#        used for visual feedback
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from PySide6.QtWidgets import QLineEdit, QWidget
from PySide6.QtGui import QValidator
from typing import Optional,cast , Tuple
from scrutiny.gui.core import WidgetState

class ValidableLineEdit(QLineEdit):
    _hard_validator:Optional[QValidator]
    _soft_validator:Optional[QValidator]
    def __init__(self, 
                 hard_validator:Optional[QValidator] = None, 
                 soft_validator:Optional[QValidator] = None, 
                 parent:Optional[QWidget]=None) -> None:
        super().__init__(parent)

        self._hard_validator = hard_validator
        self._soft_validator = soft_validator

        if hard_validator is not None:
            self.setValidator(hard_validator)
    

    def default_style(self) -> None:
        self.setProperty("state", WidgetState.default)
        style = self.style()
        style.unpolish(self)
        style.polish(self)

    def _get_validator_states(self) -> Tuple[QValidator.State, QValidator.State]:
        if self._hard_validator is not None:
            validity_hard, _, _ =  cast(Tuple[QValidator.State, str, int], self._hard_validator.validate(self.text(), 0))
        else:
            validity_hard = QValidator.State.Acceptable

        if self._soft_validator is not None:            
            validity_soft, _, _ =  cast(Tuple[QValidator.State, str, int], self._soft_validator.validate(self.text(), 0))
        else:
            validity_soft = QValidator.State.Acceptable

        return (validity_hard, validity_soft)

    def set_style_state(self, new_state:str) -> None:
        old_state = self.property("state")  # Might be an empty string
        
        if new_state != old_state:
            self.setProperty("state", new_state)
            style = self.style()
            style.unpolish(self)
            style.polish(self)


    def validate_expect_not_wrong(self, invalid_state:str = WidgetState.error, valid_state:str = WidgetState.default) -> bool:
        """Validate both validators and expect them to both return Acceptable or Intermediate
        
        :invalid_state param
        :valid_state param
        
        """
        validity_hard, validity_soft = self._get_validator_states()
        
        if validity_hard == QValidator.State.Invalid or validity_soft == QValidator.State.Invalid:
            self.set_style_state(invalid_state)
            return False
        else:
            self.set_style_state(valid_state)
            return True

    def validate_expect_not_wrong_default_slot(self) -> None:
        self.validate_expect_not_wrong()

    def validate_expect_valid(self, invalid_state:str = WidgetState.error, valid_state:str = WidgetState.default) -> bool:
        """Validate both validators and expect them to both return Acceptable"""
        validity_hard, validity_soft = self._get_validator_states()
        
        if validity_hard == QValidator.State.Acceptable and validity_soft == QValidator.State.Acceptable:
            self.set_style_state(valid_state)
            return True
        else:
            self.set_style_state(invalid_state)
            return False
