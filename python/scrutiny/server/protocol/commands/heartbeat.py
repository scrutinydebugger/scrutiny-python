from .base_command import BaseCommand
from enum import Enum

class Heartbeat(BaseCommand):
    _cmd_id = 4

    class Subfunction(Enum):
        CheckAlive = 1