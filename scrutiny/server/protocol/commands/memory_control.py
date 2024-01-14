#    memory_control.py
#        Scrutiny protocol command to read and wrie memory
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from .base_command import BaseCommand
from enum import Enum


class MemoryControl(BaseCommand):
    _cmd_id = 3

    class Subfunction(Enum):
        Read = 1
        """Reads the device memory based on an address and a length. Can read multiple block in a single request"""

        Write = 2
        """Writes the device memory based on an address and payload. Can write multiple blocks in a single request"""

        WriteMasked = 3
        """Writes the device memory with an address, a payload and a binary mask as long as the payload. Only the bits 
        where the mask is set to 1 will be written. Can write multiple blocks in a single request"""

        ReadRPV = 4
        """Reads a Runtime Published Value by providing its 16bits ID only. 
        The value type is expected to be known by both sides. The requestor can inquire the device with the list of its RPV 
        using the GetInfo commands"""

        WriteRPV = 5
        """Writes a Runtime Published Value by providing its 16bits ID and the binary payload.
        The value type is expected to be known by both sides. The requestor can inquire the device with the list of its RPV 
        using the GetInfo commands"""
