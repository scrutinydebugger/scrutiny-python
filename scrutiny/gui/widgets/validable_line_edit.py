#    validable_line_edit.py
#        An extension of QLine edit that can accept 2 validator. One enforced by Qt, the other
#        used for visual feedback
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = ['ValidableLineEdit']

from PySide6.QtWidgets import QLineEdit, QWidget
from PySide6.QtGui import QValidator

from scrutiny.gui.themes import scrutiny_get_theme

from scrutiny.tools.typing import *


class ValidableLineEdit(QLineEdit):
    _hard_validator: Optional[QValidator]
    _soft_validator: Optional[QValidator]

    def __init__(self,
                 hard_validator: Optional[QValidator] = None,
                 soft_validator: Optional[QValidator] = None,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._hard_validator = hard_validator
        self._soft_validator = soft_validator

        if hard_validator is not None:
            self.setValidator(hard_validator)

    def _get_validator_states(self) -> Tuple[QValidator.State, QValidator.State]:
        if self._hard_validator is not None:
            validity_hard, _, _ = cast(Tuple[QValidator.State, str, int], self._hard_validator.validate(self.text(), 0))
        else:
            validity_hard = QValidator.State.Acceptable

        if self._soft_validator is not None:
            validity_soft, _, _ = cast(Tuple[QValidator.State, str, int], self._soft_validator.validate(self.text(), 0))
        else:
            validity_soft = QValidator.State.Acceptable

        return (validity_hard, validity_soft)

    def set_default_state(self) -> None:
        scrutiny_get_theme().set_default_state(self)

    def set_error_state(self) -> None:
        scrutiny_get_theme().set_error_state(self)

    def validate_expect_not_wrong(self) -> bool:
        """Validate both validators and expect them to both return Acceptable or Intermediate

        :invalid_state param
        :valid_state param

        """
        validity_hard, validity_soft = self._get_validator_states()

        if validity_hard == QValidator.State.Invalid or validity_soft == QValidator.State.Invalid:
            self.set_error_state()
            return False
        else:
            self.set_default_state()
            return True

    def validate_expect_not_wrong_default_slot(self) -> None:
        self.validate_expect_not_wrong()

    def validate_expect_valid(self) -> bool:
        """Validate both validators and expect them to both return Acceptable"""
        validity_hard, validity_soft = self._get_validator_states()

        if validity_hard == QValidator.State.Acceptable and validity_soft == QValidator.State.Acceptable:
            self.set_default_state()
            return True
        else:
            self.set_error_state()
            return False

    def is_valid(self) -> bool:
        validity_hard, validity_soft = self._get_validator_states()
        return validity_hard == QValidator.State.Acceptable and validity_soft == QValidator.State.Acceptable
