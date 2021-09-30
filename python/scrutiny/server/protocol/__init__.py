from .request import Request
from .response import Response
from .protocol import Protocol
from .datalog import *

from enum import Enum

class Feature(Enum):
    ReadMem = 1
    WriteMem = 2
    Datalog = 3


