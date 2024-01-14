#    get_info.py
#        Scrutiny protocol command to read some specific configuration in the device
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from .base_command import BaseCommand
from enum import Enum


class GetInfo(BaseCommand):
    _cmd_id = 1

    class Subfunction(Enum):
        GetProtocolVersion = 1
        """Request the device for its protocol version. """

        GetSoftwareId = 2
        """Request the device for its firmware ID"""

        GetSupportedFeatures = 3
        """Request the device for the list of supported features. Some features can be disabled to reduces the embedded library footprint"""

        GetSpecialMemoryRegionCount = 4
        """Request the device with the number of readonly and forbidden memory region"""

        GetSpecialMemoryRegionLocation = 5
        """Request the device with the location a readonly or a forbidden memory region"""

        GetRuntimePublishedValuesCount = 6
        """Request the device with the number of Runtime Published Values (RPV)"""

        GetRuntimePublishedValuesDefinition = 7
        """Request the device with the definition of a Runtime Published Values (RPV). 
        Definition include ID and type (size implied by data type)"""

        GetLoopCount = 8
        """Request the device with the number of loops (execution unit with its own time domain) being run on the device"""

        GetLoopDefinition = 9
        """Get the parameters of a loop (execution unit with its own time domain) """

    class MemoryRangeType(Enum):
        """Type of special memory region"""
        ReadOnly = 0
        Forbidden = 1
