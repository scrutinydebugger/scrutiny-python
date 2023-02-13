#    datalog_control.py
#        Scrutiny protocol command to trigger and read data logs.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

from .base_command import BaseCommand
from enum import Enum


class DatalogControl(BaseCommand):
    _cmd_id = 5

    class Subfunction(Enum):
        GetSetup = 1
        ConfigureDatalog = 2
        ArmTrigger = 3
        DisarmTrigger = 4
        GetStatus = 5
        GetAcquisitionMetadata = 6
        ReadAcquisition = 7
