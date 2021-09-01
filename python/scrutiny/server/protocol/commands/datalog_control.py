from .base_command import BaseCommand
from enum import Enum

class DatalogControl(BaseCommand):
    _cmd_id = 6

    class Subfunction(Enum):
        GetAvailableTarget = 1
        GetBufferSize = 2
        GetSamplingRates = 3
        ConfigureDatalog = 4
        ListRecordings = 5
        ReadRecordings = 6
        ArmLog = 7
        DisarmLog = 8
        GetLogStatus = 9