#    datalog_control.py
#        Scrutiny protocol command to trigger and read data logs.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from .base_command import BaseCommand
from enum import Enum


class DatalogControl(BaseCommand):
    _cmd_id = 5

    class Subfunction(Enum):
        GetSetup = 1
        """Request the device for its datalogging setup. (word "configuration" is purposely avoided here to avoid confusion). Includes encoding, buffer size, etc"""

        ConfigureDatalog = 2
        """ Configure the datalogger for an acquisition. Circular buffer will start to be filled after this command"""

        ArmTrigger = 3
        """Make the datalogger wait for the trigger condition to finish its acquisition"""

        DisarmTrigger = 4
        """Stop the datalogger from waiting for the trigger condition"""

        GetStatus = 5
        """Request the device for the state of the datalogger"""

        GetAcquisitionMetadata = 6
        """Once an acquisition is ready, request the device for the acquisition metadata"""

        ReadAcquisition = 7
        """Once an acquisition is ready, request the device to return the acquisition data"""

        ResetDatalogger = 8
        """Put back the datalogger in standby state where it'll wait for a new configuration through ConfigureDatalog"""
