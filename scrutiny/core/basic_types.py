#    basic_types.py
#        Contains the basic types used project-wides
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = [
    'Endianness',
    'DataTypeType',
    'DataTypeSize',
    'EmbeddedDataType',
    'RuntimePublishedValue',
    'MemoryRegion'
]

from enum import Enum
from typing import Union
from dataclasses import dataclass
from scrutiny.core import validation


@dataclass(frozen=True)
class MemoryRegion:
    """(Immutable struct) 
    Represent a memory region spanning from ``start`` to ``start+size-1``"""

    start: int
    """Start address of the region"""
    size: int
    """Size in bytes of the region"""

    def __post_init__(self) -> None:
        validation.assert_int_range(self.start, 'start', minval=0)
        validation.assert_int_range(self.size, 'size', minval=0)

    def touches(self, other: "MemoryRegion") -> bool:
        if self.size <= 0 or other.size <= 0:
            return False

        if self.start >= other.start + other.size:
            return False

        if other.start >= self.start + self.size:
            return False

        return True

    @property
    def end(self) -> int:
        return max(self.start, self.start + self.size - 1)


class Endianness(Enum):
    """(Enum) Represent an data storage endianness"""

    Little = 0
    """Litle endian. 0x12345678 is stored as 78 56 34 12 """

    Big = 1
    """Big endian. 0x12345678 is stored as 12 34 56 78 """


class DataTypeType(Enum):
    _sint = (0 << 4)
    _uint = (1 << 4)
    _float = (2 << 4)
    _boolean = (3 << 4)
    _cfloat = (4 << 4)
    _struct = (5 << 4)
    _NA = 0xF


class DataTypeSize(Enum):
    _8 = 0
    _16 = 1
    _32 = 2
    _64 = 3
    _128 = 4
    _256 = 5
    _NA = 0xF


class EmbeddedDataType(Enum):
    """
    (Enum)
    Represent a datatype that can be read from a device.
    The embedded library has the same definition of datatype as this one. They needs to match.
    Not all datatype are supported.  (cfloat or >64 bits)
    """
    sint8 = DataTypeType._sint.value | DataTypeSize._8.value
    sint16 = DataTypeType._sint.value | DataTypeSize._16.value
    sint32 = DataTypeType._sint.value | DataTypeSize._32.value
    sint64 = DataTypeType._sint.value | DataTypeSize._64.value
    sint128 = DataTypeType._sint.value | DataTypeSize._128.value
    sint256 = DataTypeType._sint.value | DataTypeSize._256.value

    uint8 = DataTypeType._uint.value | DataTypeSize._8.value
    uint16 = DataTypeType._uint.value | DataTypeSize._16.value
    uint32 = DataTypeType._uint.value | DataTypeSize._32.value
    uint64 = DataTypeType._uint.value | DataTypeSize._64.value
    uint128 = DataTypeType._uint.value | DataTypeSize._128.value
    uint256 = DataTypeType._uint.value | DataTypeSize._256.value

    float8 = DataTypeType._float.value | DataTypeSize._8.value
    float16 = DataTypeType._float.value | DataTypeSize._16.value
    float32 = DataTypeType._float.value | DataTypeSize._32.value
    float64 = DataTypeType._float.value | DataTypeSize._64.value
    float128 = DataTypeType._float.value | DataTypeSize._128.value
    float256 = DataTypeType._float.value | DataTypeSize._256.value

    cfloat8 = DataTypeType._cfloat.value | DataTypeSize._8.value
    cfloat16 = DataTypeType._cfloat.value | DataTypeSize._16.value
    cfloat32 = DataTypeType._cfloat.value | DataTypeSize._32.value
    cfloat64 = DataTypeType._cfloat.value | DataTypeSize._64.value
    cfloat128 = DataTypeType._cfloat.value | DataTypeSize._128.value
    cfloat256 = DataTypeType._cfloat.value | DataTypeSize._256.value

    boolean = DataTypeType._boolean.value | DataTypeSize._8.value

    struct = DataTypeType._struct.value | DataTypeSize._NA.value
    NA = DataTypeType._NA.value | DataTypeSize._NA.value

    def get_size_bit(self) -> int:
        """Return the size fo the datatype in bits. Returns 0 if NA"""
        v = self.get_size_byte()
        return v * 8

    def get_size_byte(self) -> int:
        """Return the size fo the datatype in bytes. Returns 0 if NA"""
        vbytes = (self.value & 0xF)
        if DataTypeSize(vbytes) == DataTypeSize._NA:
            return 0
        return 1 << vbytes

    def is_integer(self) -> bool:
        """Tells if the datatype is an integer type (sint or uint)"""
        type_type = self.value & 0xF0
        if type_type in (DataTypeType._sint.value, DataTypeType._uint.value):
            return True
        return False

    def is_float(self) -> bool:
        """Tells if a datatype is a floating point value (float)"""
        type_type = self.value & 0xF0
        # Cfloat???
        if type_type in (DataTypeType._float.value, DataTypeType._cfloat.value):
            return True
        return False

    def is_signed(self) -> bool:
        """Tells if the datatype support a sign (sint, float, cfloat)"""
        type_type = self.value & 0xF0
        if type_type in (DataTypeType._sint.value, DataTypeType._float.value, DataTypeType._cfloat.value):
            return True
        return False


@dataclass(frozen=True)
class RuntimePublishedValue:
    """ 
    (Immutable struct) A Runtime Published Value (RPV) is on of the basic element that can be read from a target device.
    RPVs are defined in the embedded code and known by the server by polling the device.
    They don't have a name, they are identified by a 16bits identifier.
    The user can add an Alias on a RPV to assign them a name
    """

    id: int
    """RPV ID (16bits)"""
    datatype: EmbeddedDataType
    """The data type of the value"""

    def __post_init__(self) -> None:
        validation.assert_int_range(self.id, 'id', 0, 0xFFFF)
        validation.assert_type(self.datatype, 'datatype', EmbeddedDataType)

    def __repr__(self) -> str:
        return "<%s: 0x%x (%s) at 0x%016x>" % (self.__class__.__name__, self.id, self.datatype.name, id(self))
