#    globals.py
#        Server wide globals definitions
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = [
    'set_server_storage',
    'get_server_storage'
]

import appdirs
from pathlib import Path

from scrutiny.tools.typing import *

SERVER_STORAGE = Path(appdirs.user_data_dir(appname='server', appauthor='scrutiny'))


def set_server_storage(val: Union[Path]) -> None:
    global SERVER_STORAGE
    SERVER_STORAGE = val


def get_server_storage() -> Path:
    return SERVER_STORAGE
