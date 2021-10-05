from .base_command import BaseCommand
from enum import Enum

class CommControl(BaseCommand):
    _cmd_id = 2
    MAGIC = bytes([0x7e, 0x18, 0xfc, 0x68])

    class Subfunction(Enum):
        Discover = 1
        Heartbeat = 2
        GetParams = 3
        Connect = 4