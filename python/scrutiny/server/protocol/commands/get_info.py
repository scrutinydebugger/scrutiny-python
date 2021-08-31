from .base_command import BaseCommand
from enum import Enum

class GetInfo(BaseCommand):
    _cmd_id = 1

    class Subfunction(Enum):
        GetProtocolVersion = 1
        GetSoftwareId = 2
        GetSupportedFeatures = 3


