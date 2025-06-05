#    embedded_enum.py
#        Contains the definition for an enum on the embedded side
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = ['EmbeddedEnum', 'EmbeddedEnumDef']

from scrutiny.tools.typing import *


class EmbeddedEnumDef(TypedDict):
    """
    Represent the dictionary version of the EmbeddedEnum (for .json import/export).
    Used only for type hints
    """
    name: str
    values: Dict[str, int]


class EmbeddedEnum:
    """
    Represents an enumeration in the embedded code.
    Match a string to an int value
    """
    name: str
    vals: Dict[str, int]

    def __init__(self, name: str, vals: Optional[Dict[str, int]] = None):
        self.name = name
        self.vals = {}
        if vals is not None:
            for k, v in vals.items():
                self.add_value(k, v)

    def get_first_value_name_match(self, wanted_val: int) -> Optional[str]:
        """Return the name associated with a value. In case of duplicates, the first found is returned.

        :param wanted_val: The numerical value to search for
        """
        for name, val in self.vals.items():
            if val == wanted_val:
                return name
        return None

    def add_value(self, name: str, value: int) -> None:
        """Adds a string/value pair in the enum

        :param name: Enumerator name
        :param value: Enumerator value

        :raises IndexError: If the enumerator name is already defined in the enum with a different value

        """
        if name in self.vals and self.vals[name] != value:
            raise IndexError('Duplicate entry for enum %s. %s can either be %s or %s' % (self.name, name, self.vals[name], value))

        self.vals[name] = value

    def get_name(self) -> str:
        """Return the name of the enum"""
        return self.name

    def get_value(self, name: str) -> int:
        """Returns the value associated with a name

        :param name: Enumerator name

        :raises ValueError: If the given enumerator name is not part of the enumeration
        """
        if name not in self.vals:
            raise ValueError('%s is not a valid name for enum %s' % (name, self.name))
        return self.vals[name]

    def has_value(self, name: str) -> bool:
        """Tells if the enum has value with the given name

        :param name: Enumerator name
        """
        return name in self.vals

    def get_def(self) -> EmbeddedEnumDef:
        """Exports to dict for json serialization mainly"""

        obj: EmbeddedEnumDef = {
            'name': self.name,
            'values': self.vals
        }
        return obj

    def has_signed_value(self) -> bool:
        """Returns true if any value is negative"""
        for v in self.vals.values():
            if v < 0:
                return True
        return False

    def copy(self) -> "EmbeddedEnum":
        """Creates a copy of the enum"""
        return EmbeddedEnum(name=self.name, vals=self.vals)

    @classmethod
    def from_def(cls, enum_def: EmbeddedEnumDef) -> "EmbeddedEnum":
        """Recreates from a .json dict

        :param enum_def: The json structure created with :meth:`get_def<get_def>`

        """
        obj = EmbeddedEnum(enum_def['name'])
        obj.vals = enum_def['values']
        return obj
