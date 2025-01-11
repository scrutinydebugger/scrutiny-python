#    app_settings.py
#        Global settings for the GUI.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import typing

if typing.TYPE_CHECKING:
    from scrutiny.gui.gui import ScrutinyQtGUI

def app_settings() -> "ScrutinyQtGUI.Settings":
    from scrutiny.gui.gui import ScrutinyQtGUI
    return ScrutinyQtGUI.instance().settings
