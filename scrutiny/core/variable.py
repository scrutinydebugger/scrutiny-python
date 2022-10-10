#    variable.py
#        Variable class represent a variable, will be included in VarMap
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import struct
import logging
from scrutiny.core.basic_types import Endianness, EmbeddedDataType
from scrutiny.core.codecs import Codecs, Encodable
from typing import Dict, Union, List, Literal, Optional, TypedDict, Any, Tuple


MASK_MAP: Dict[int, int] = {}
for i in range(63):
    v = 0
    for j in range(i):
        v |= (1 << j)
        MASK_MAP[i] = v


class VariableLocation:
    """Represent an address in memory. """

    def __init__(self, address: int):
        if not isinstance(address, int):
            raise ValueError('Address must be a valid integer')

        self.address = address

    def get_address(self) -> int:
        """Return the address in a numerical format"""
        return self.address

    def add_offset(self, offset: int):
        """Modify the address by the given offset"""
        self.address += offset

    @classmethod
    def check_endianness(cls, endianness: Endianness):
        """Tells if given endianness is valid"""
        if endianness not in [Endianness.Little, Endianness.Big]:
            raise ValueError('Invalid endianness "%s" ' % endianness)

    @classmethod
    def from_bytes(cls, data: Union[bytes, List[int], bytearray], endianness: Endianness):
        """Reads the address encoded in binary with the given endianness"""
        if isinstance(data, list) or isinstance(data, bytearray):
            data = bytes(data)
        if not isinstance(data, bytes):
            raise ValueError('Data must be bytes, not %s' % (data.__class__.__name__))

        if len(data) < 1:
            raise ValueError('Empty data')

        cls.check_endianness(endianness)
        byteorder_map: Dict[Endianness, Literal['little', 'big']] = {
            Endianness.Little: 'little',
            Endianness.Big: 'big'
        }
        address = int.from_bytes(data, byteorder=byteorder_map[endianness], signed=False)
        return cls(address)

    def copy(self) -> 'VariableLocation':
        """Return a copy of this VariableLocation object"""
        return VariableLocation(self.get_address())

    def __str__(self):
        return str(self.get_address())

    def __repr__(self):
        return '<%s - 0x%08X>' % (self.__class__.__name__, self.get_address())


class VariableEnumDef(TypedDict):
    """
    Represent the dictionary version of the VariableEnum (for .json import/export).
    Used only for type hints
    """
    name: str
    values: Dict[str, int]


class VariableEnum:
    """
    Represents an enumeration in the embedded code.
    Match a string to an int value
    """
    name: str
    vals: Dict[str, int]

    def __init__(self, name: str):
        self.name = name
        self.vals = {}

    def add_value(self, name: str, value: int) -> None:
        """Add a string/value pair in the enum"""
        if name in self.vals and self.vals[name] != value:
            raise Exception('Duplicate entry for enum %s. %s can either be %s or %s' % (self.name, name, self.vals[name], value))

        self.vals[name] = value

    def get_name(self) -> str:
        """Return the name of the enum"""
        return self.name

    def get_value(self, name: str) -> int:
        """Return the value associated with a name"""
        if name not in self.vals:
            raise Exception('%s is not a valid name for enum %s' % (name, self.name))
        return self.vals[name]

    def get_def(self) -> VariableEnumDef:
        """Export to dict for json serialization mainly"""
        obj: VariableEnumDef = {
            'name': self.name,
            'values': self.vals
        }
        return obj

    @classmethod
    def from_def(cls, enum_def: VariableEnumDef):
        """Recreate from a .json dict"""
        obj = cls(enum_def['name'])
        obj.vals = enum_def['values']
        return obj


class Struct:
    class Member:
        name: str
        is_substruct: bool
        original_type_name: Optional[str]
        bitoffset: Optional[int]
        byte_offset: Optional[int]
        bitsize: Optional[int]
        substruct: Optional['Struct']

        def __init__(self, name: str, is_substruct: bool = False, original_type_name: Optional[str] = None, byte_offset: Optional[int] = None, bitoffset: Optional[int] = None, bitsize: Optional[int] = None, substruct: Optional['Struct'] = None):

            if not is_substruct:
                if original_type_name is None:
                    raise ValueError('A typename must be given for non-struct member')

            if bitoffset is not None:
                if not isinstance(bitoffset, int):
                    raise ValueError('bitoffset must be an integer value')
                if bitoffset < 0:
                    raise ValueError('bitoffset must be a positive integer')

            if bitsize is not None:
                if not isinstance(bitsize, int):
                    raise ValueError('bitsize must be an integer value')
                if bitsize < 0:
                    raise ValueError('bitsize must be a positive integer')

            if byte_offset is not None:
                if not isinstance(byte_offset, int):
                    raise ValueError('byte_offset must be an integer value')
                if byte_offset < 0:
                    raise ValueError('byte_offset must be a positive integer')

            if substruct is not None:
                if not isinstance(substruct, Struct):
                    raise ValueError('substruct must be Struct instance')

            self.name = name
            self.is_substruct = is_substruct
            self.original_type_name = original_type_name
            self.bitoffset = bitoffset
            self.byte_offset = byte_offset
            self.bitsize = bitsize
            self.substruct = substruct

    name: str
    members: Dict[str, Union['Struct', 'Struct.Member']]

    def __init__(self, name: str):
        self.name = name
        self.members = {}

    def add_member(self, member):
        """Add a member to the struct"""
        if member.name in self.members:
            raise Exception('Duplicate member %s' % member.name)

        if not isinstance(member, Struct) and not isinstance(member, Struct.Member):
            raise ValueError('Node must be a member or a substruct')

        self.members[member.name] = member


class Variable:
    """
    One of the most basic type of data (with RPV and Alias).
    Represent a variable in memory. It has a name, location and type.
    It supports bitfields and variable endianness.
    """

    name: str
    vartype: EmbeddedDataType
    path_segments: List[str]
    location: VariableLocation
    endianness: Endianness
    bitsize: Optional[int]
    bitfield: Optional[bool]
    bitoffset: Optional[int]
    enum: Optional[VariableEnum]

    def __init__(self, name: str, vartype: EmbeddedDataType, path_segments: List[str], location: Union[int, VariableLocation], endianness: Endianness, bitsize: Optional[int] = None, bitoffset: Optional[int] = None, enum: Optional[VariableEnum] = None):

        self.name = name
        self.vartype = vartype
        self.path_segments = path_segments
        if isinstance(location, VariableLocation):
            self.location = location.copy()
        else:
            self.location = VariableLocation(location)
        self.endianness = endianness

        if bitoffset is not None and bitsize is None:
            var_size = self.vartype.get_size_bit()
            if var_size is None:
                raise Exception('Cannot specify bitsize for variable of type %s' % str(EmbeddedDataType))
            bitsize = var_size - bitoffset
        elif bitoffset is None and bitsize is not None:
            bitoffset = 0
        self.bitfield = False if bitoffset is None or bitsize is None else True
        self.bitsize = bitsize
        self.bitoffset = bitoffset
        self.enum = enum

    def decode(self, data: Union[bytes, bytearray]) -> Encodable:
        """Decode the binary content in memory to a python value"""

        if self.bitfield:
            # todo improve this with bit array maybe.
            assert self.bitsize is not None
            if len(data) > 8:
                raise NotImplementedError('Does not support bitfield bigger than %dbits' % (8 * 8))
            initial_len = len(data)

            if self.endianness == Endianness.Little:
                padded_data = bytearray(data + b'\x00' * (8 - initial_len))
                uint_data = struct.unpack('<q', padded_data)[0]
                uint_data >>= self.bitoffset
                uint_data &= MASK_MAP[self.bitsize]
                data = struct.pack('<q', uint_data)
                data = data[0:initial_len]
            else:
                padded_data = bytearray(b'\x00' * (8 - initial_len) + data)
                uint_data = struct.unpack('>q', padded_data)[0]
                uint_data >>= self.bitoffset
                uint_data &= MASK_MAP[self.bitsize]
                data = struct.pack('>q', uint_data)
                data = data[-initial_len:]

        decoded = Codecs.get(self.vartype, endianness=self.endianness).decode(data)

        return decoded

    def encode(self, value: Encodable) -> Tuple[bytes, Optional[bytes]]:
        """
        Converts a python balue to a binary content that can be written in memory.
        The write mask is used for bitfields
        """
        write_mask = None
        data = Codecs.get(self.vartype, endianness=self.endianness).encode(value)

        # todo bitfield set write_mask
        return data, write_mask

    def get_fullname(self) -> str:
        """Returns the full path identifying this variable"""
        if len(self.path_segments) == 0:
            path_str = '/'
        else:
            path_str = '/' + '/'.join(self.path_segments)
        return '%s/%s' % (path_str, self.name)

    def get_type(self) -> EmbeddedDataType:
        """Returns the data type of the variable"""
        return self.vartype

    def get_path_segments(self) -> List[str]:
        """Returns a list of segments representing the path to the variable. Exclude the variable name"""
        return self.path_segments

    def get_address(self) -> int:
        """Get the variable address"""
        return self.location.get_address()

    def has_enum(self) -> bool:
        """True if an enum is attached to that variable"""
        return self.enum is not None

    def get_enum(self) -> Optional[VariableEnum]:
        """Return the enum attached to the variable. None if it does not exists"""
        return self.enum

    def get_size(self) -> Optional[int]:
        """Returns the size of the variable in bytes"""
        size_bit = self.vartype.get_size_bit()
        if size_bit is None:
            return None
        else:
            return int(size_bit / 8)

    def __repr__(self):
        return '<%s - %s (%s) @ %s>' % (self.__class__.__name__, self.get_fullname(), self.vartype, self.location)
