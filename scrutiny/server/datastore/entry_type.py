#    entry_type.py
#        Type of datastore entry.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from typing import List
from enum import Enum


class EntryType(str, Enum):
    Var = 'var'
    RuntimePublishedValue = 'rpv'
    Alias = 'alias'

    @classmethod
    def all(cls) -> List['EntryType']:
        """Return a list of all possible Entry Type"""
        # Todo, find a better way to do this. This enum also inherit str. __iter__ returns the chars
        return [EntryType.Var, EntryType.Alias, EntryType.RuntimePublishedValue]

    def toJson(self) -> str:
        return self.value
