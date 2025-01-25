#    globals.py
#        GUI wide globals definitions
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import appdirs  # type: ignore
from pathlib import Path

GUI_STORAGE = Path(appdirs.user_data_dir(appname='gui', appauthor='scrutiny'))

def get_gui_storage() -> Path:
    return GUI_STORAGE
