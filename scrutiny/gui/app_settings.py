#    app_settings.py
#        Global settings for the GUI.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['app_settings']

import typing
from dataclasses import dataclass

if typing.TYPE_CHECKING:
    from scrutiny.gui.gui import ScrutinyQtGUI


@dataclass
class UnitTests:
    enable: bool
    settings: typing.Optional["ScrutinyQtGUI.Settings"]


unit_tests = UnitTests(enable=False, settings=None)


def configure_unit_test_app_settings(settings: "ScrutinyQtGUI.Settings") -> None:
    unit_tests.settings = settings
    unit_tests.enable = True


def app_settings() -> "ScrutinyQtGUI.Settings":
    if unit_tests.enable:
        assert unit_tests.settings is not None
        return unit_tests.settings
    else:
        from scrutiny.gui.gui import ScrutinyQtGUI
        return ScrutinyQtGUI.instance().settings
