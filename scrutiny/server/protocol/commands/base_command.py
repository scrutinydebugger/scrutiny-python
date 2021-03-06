#    base_command.py
#        Abstract class for all Scrutiny protocol commands
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

from abc import ABC
import inspect
import sys

from typing import Type


class BaseCommand(ABC):

    _cmd_id = -1

    @classmethod  # Returns an instance of the service identified by the service ID (Request)
    def from_command_id(cls, given_id: int) -> Type["BaseCommand"]:
        given_id &= 0x7F
        for name, obj in inspect.getmembers(sys.modules[__name__]):
            if hasattr(obj, "__bases__") and cls in obj.__bases__:
                if obj.request_id() == given_id:
                    return obj
        raise ValueError('Unknown command ID %s' % given_id)

    @classmethod
    def response_id(cls) -> int:
        return cls._cmd_id | 0x80

    @classmethod
    def request_id(cls) -> int:
        return cls._cmd_id & 0x7F


from .datalog_control import DatalogControl
from .get_info import GetInfo
from .memory_control import MemoryControl
from .comm_control import CommControl
from .user_command import UserCommand
from .dummy_command import DummyCommand
