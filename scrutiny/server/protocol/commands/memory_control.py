#    memory_control.py
#        Scrutiny protocol command to read and wrie memory
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

from .base_command import BaseCommand
from enum import Enum


class MemoryControl(BaseCommand):
    _cmd_id = 3

    class Subfunction(Enum):
        Read = 1
        Write = 2
        WriteMasked = 3
