#    base_command.py
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import argparse
from abc import ABC, abstractmethod
from typing import List, Optional


class BaseCommand(ABC):
    _cmd_name_: str
    _brief_: str
    _group_: str

    @classmethod
    def get_name(cls) -> str:
        return cls._cmd_name_

    @classmethod
    def get_brief(cls) -> str:
        return cls._brief_

    @classmethod
    def get_group(cls) -> str:
        if hasattr(cls, '_group_'):
            return cls._group_
        else:
            return ''

    @classmethod
    def get_prog(cls) -> str:
        return 'scrutiny ' + cls.get_name()

    @abstractmethod
    def run(self) -> Optional[int]:
        pass

    @abstractmethod
    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        pass
