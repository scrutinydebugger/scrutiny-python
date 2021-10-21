from .base_command import BaseCommand
from enum import Enum

# For testing purpose.
class DummyCommand(BaseCommand):
    _cmd_id = 0

    class Subfunction(Enum):
        SubFn1 = 1
        SubFn2 = 2
        SubFn3 = 3