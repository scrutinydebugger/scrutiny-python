#    comm_control.py
#        Scrutiny protocol command to manipulate the communication
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from .base_command import BaseCommand
from enum import Enum


class CommControl(BaseCommand):
    """All commands related to communication handling"""
    _cmd_id = 2
    DISCOVER_MAGIC = bytes([0x7e, 0x18, 0xfc, 0x68])
    CONNECT_MAGIC = bytes([0x82, 0x90, 0x22, 0x66])

    class Subfunction(Enum):
        Discover = 1
        """Request for a device to identify itself with his firmware ID and name"""

        Heartbeat = 2
        """Keep a connection to a device alive. Meaning the device will refuse any other 
        incoming Connect request as long heartbeat are being sent """

        GetParams = 3
        """Request for the device communication parameters"""

        Connect = 4
        """Request the device for a Connection"""

        Disconnect = 5
        """Inform the device that we want to disconnect"""
