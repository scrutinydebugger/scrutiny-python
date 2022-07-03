#    datalog_control.py
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

from .base_command import BaseCommand
from enum import Enum


class DatalogControl(BaseCommand):
    _cmd_id = 5

    class Subfunction(Enum):
        GetAvailableTarget = 1
        GetBufferSize = 2
        GetSamplingRates = 3
        ConfigureDatalog = 4
        ListRecordings = 5
        ReadRecordings = 6
        ArmLog = 7
        DisarmLog = 8
        GetLogStatus = 9
