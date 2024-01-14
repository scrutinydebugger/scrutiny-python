#    base_command.py
#        Abstract class for all commands. Used to automatically find all available commands
#        through reflection
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from abc import ABC, abstractmethod
from typing import List, Optional


class BaseCommand(ABC):
    _cmd_name_: str
    _brief_: str
    _group_: str

    @classmethod
    def get_name(cls) -> str:
        """Returns the name of the command"""
        return cls._cmd_name_

    @classmethod
    def get_brief(cls) -> str:
        """Returns a textual description of what the command does"""
        return cls._brief_

    @classmethod
    def get_group(cls) -> str:
        """Returns the group in which this command belongs"""
        if hasattr(cls, '_group_'):
            return cls._group_
        else:
            return ''

    @classmethod
    def get_prog(cls) -> str:
        """Return the name of the program to be called on the CLI"""
        return 'scrutiny ' + cls.get_name()

    @abstractmethod
    def run(self) -> Optional[int]:
        """Executes a command"""
        pass

    @abstractmethod
    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        pass
