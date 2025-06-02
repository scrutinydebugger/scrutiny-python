#    globals.py
#        GUI wide globals definitions
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['get_gui_storage']

import appdirs
from pathlib import Path

GUI_STORAGE = Path(appdirs.user_data_dir(appname='gui', appauthor='scrutiny'))


def get_gui_storage() -> Path:
    return GUI_STORAGE
