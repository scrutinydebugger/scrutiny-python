#    comm_control.py
#        Scrutiny protocol command to manipulate the communication
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

from .base_command import BaseCommand
from enum import Enum


class CommControl(BaseCommand):
    _cmd_id = 2
    DISCOVER_MAGIC = bytes([0x7e, 0x18, 0xfc, 0x68])
    CONNECT_MAGIC = bytes([0x82, 0x90, 0x22, 0x66])

    class Subfunction(Enum):
        Discover = 1
        Heartbeat = 2
        GetParams = 3
        Connect = 4
        Disconnect = 5
