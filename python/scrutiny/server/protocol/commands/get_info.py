from .base_command import BaseCommand
from enum import Enum

class GetInfo(BaseCommand):
    _cmd_id = 1

    class Subfunction(Enum):
        GetProtocolVersion = 1
        GetSoftwareId = 2
        GetSupportedFeatures = 3
        GetSpecialMemoryRegionCount = 4
        GetSpecialMemoryRegionLocation = 5 

    class MemoryRangeType(Enum):
        ReadOnly = 0
        Forbidden = 1




