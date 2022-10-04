from typing import List
from enum import Enum

class EntryType(str, Enum):
    Var = 'var'
    RuntimePublishedValue = 'rpv'
    Alias = 'alias'

    @classmethod
    def all(cls) -> List['EntryType']:
        return  [EntryType.Var, EntryType.Alias, EntryType.RuntimePublishedValue]   # Todo, find a better way to do this. This enum also inherit str

    def toJson(self):
        return self.value
