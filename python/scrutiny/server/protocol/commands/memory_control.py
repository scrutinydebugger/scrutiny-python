from .base_command import BaseCommand
from enum import Enum

class MemoryControl(BaseCommand):
    _cmd_id = 3

    class Subfunction(Enum):
        Read = 1
        Write = 2
