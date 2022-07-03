#    variable.py
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

from enum import Enum
import struct
from abc import ABC, abstractmethod

from typing import Dict, Union, List, Literal, Optional, TypedDict, Any, Tuple

MASK_MAP: Dict[int, int] = {}
for i in range(63):
    v = 0
    for j in range(i):
        v |= (1 << j)
        MASK_MAP[i] = v


class Endianness(Enum):
    Little = 0
    Big = 1


class VariableLocation:
    def __init__(self, address: int):
        if not isinstance(address, int):
            raise ValueError('Address must be a valid integer')

        self.address = address

    def get_address(self) -> int:
        return self.address

    def add_offset(self, offset: int):
        self.address += offset

    @classmethod
    def check_endianness(cls, endianness: Endianness):
        if endianness not in [Endianness.Little, Endianness.Big]:
            raise ValueError('Invalid endianness "%s" ' % endianness)

    @classmethod
    def from_bytes(cls, data: Union[bytes, List[int], bytearray], endianness: Endianness):
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
        return VariableLocation(self.get_address())

    def __str__(self):
        return str(self.get_address())

    def __repr__(self):
        return '<%s - 0x%08X>' % (self.__class__.__name__, self.get_address())


class VariableType(Enum):
    sint8 = 0
    sint16 = 1
    sint32 = 2
    sint64 = 3
    sint128 = 4
    sint256 = 5
    uint8 = 10
    uint16 = 11
    uint32 = 12
    uint64 = 13
    uint128 = 14
    uint256 = 15
    float8 = 20
    float16 = 21
    float32 = 22
    float64 = 23
    float128 = 24
    float256 = 25
    cfloat8 = 30
    cfloat16 = 31
    cfloat32 = 32
    cfloat64 = 33
    cfloat128 = 34
    cfloat256 = 35
    boolean = 40
    struct = 41

    def get_size_bit(self) -> Optional[int]:
        sizemap: Dict[VariableType, Optional[int]] = {
            self.__class__.sint8: 8,
            self.__class__.uint8: 8,
            self.__class__.float8: 8,
            self.__class__.cfloat8: 8,

            self.__class__.sint16: 16,
            self.__class__.uint16: 16,
            self.__class__.float16: 16,
            self.__class__.cfloat16: 16,

            self.__class__.sint32: 32,
            self.__class__.uint32: 32,
            self.__class__.float32: 32,
            self.__class__.cfloat32: 32,

            self.__class__.sint64: 64,
            self.__class__.uint64: 64,
            self.__class__.float64: 64,
            self.__class__.cfloat64: 64,

            self.__class__.sint128: 128,
            self.__class__.uint128: 128,
            self.__class__.float128: 128,
            self.__class__.cfloat128: 128,

            self.__class__.sint256: 256,
            self.__class__.uint256: 256,
            self.__class__.float256: 256,
            self.__class__.cfloat256: 256,

            self.__class__.boolean: 8,
            self.__class__.struct: None
        }

        return sizemap[self]

    def get_size_byte(self) -> Optional[int]:
        bitsize = self.get_size_bit()
        if bitsize is None:
            return None
        else:
            return int(bitsize / 8)


class VariableEnumDef(TypedDict):
    name: str
    values: Dict[int, str]


class VariableEnum:

    name: str
    vals: Dict[int, str]

    def __init__(self, name: str):
        self.name = name
        self.vals = {}

    def add_value(self, value: int, name: str) -> None:
        if value in self.vals and self.vals[value] != name:
            raise Exception('Duplicate entry for enum %s. %s can either be %s or %s' % (self.name, value, self.vals[value], name))
        self.vals[value] = name

    def get_name(self, value: int) -> str:
        if value not in self.vals:
            raise Exception('%d is not a valid value for enum %s' % (value, self.name))
        return self.vals[value]

    def get_def(self) -> VariableEnumDef:
        obj: VariableEnumDef = {
            'name': self.name,
            'values': self.vals
        }
        return obj

    @classmethod
    def from_def(cls, enum_def: VariableEnumDef):
        obj = cls(enum_def['name'])
        obj.vals = {}
        for k in enum_def['values']:
            if isinstance(k, str):
                newkey = int(k)
            else:
                newkey = k
            obj.vals[newkey] = enum_def['values'][k]
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
        if member.name in self.members:
            raise Exception('Duplicate member %s' % member.name)

        if not isinstance(member, Struct) and not isinstance(member, Struct.Member):
            raise ValueError('Node must be a member or a substruct')

        self.members[member.name] = member


class Variable:

    class BaseCodec(ABC):
        def __init__(self):
            pass

        @abstractmethod
        def decode(self, data: Union[bytes, bytearray], endianness: Endianness) -> Union[int, float, bool, None]:
            pass

        @abstractmethod
        def encode(self, value: Union[int, float, bool], endianness: Endianness) -> bytes:
            pass

    class SIntCodec(BaseCodec):
        str_map = {
            1: 'b',
            2: 'h',
            4: 'l',
            8: 'q'
        }

        def __init__(self, size: int):
            super().__init__()
            if size not in self.str_map:
                raise NotImplementedError('Does not support signed int of %d bytes', size)
            self.str = self.str_map[size]

        def decode(self, data: Union[bytes, bytearray], endianness: Endianness) -> int:
            endianness_char = '<' if endianness == Endianness.Little else '>'
            return struct.unpack(endianness_char + self.str, data)[0]

        def encode(self, value: Union[int, float, bool], endianness: Endianness) -> bytes:
            endianness_char = '<' if endianness == Endianness.Little else '>'
            return struct.pack(endianness_char + self.str, value)

    class UIntCodec(BaseCodec):
        str_map = {
            1: 'B',
            2: 'H',
            4: 'L',
            8: 'Q'
        }

        def __init__(self, size):
            super().__init__()
            if size not in self.str_map:
                raise NotImplementedError('Does not support signed int of %d bytes', size)
            self.str = self.str_map[size]

        def decode(self, data: Union[bytes, bytearray], endianness: Endianness) -> int:
            endianness_char = '<' if endianness == Endianness.Little else '>'
            return struct.unpack(endianness_char + self.str, data)[0]

        def encode(self, value: Union[int, float, bool], endianness: Endianness) -> bytes:
            endianness_char = '<' if endianness == Endianness.Little else '>'
            return struct.pack(endianness_char + self.str, value)

    class FloatCodec(BaseCodec):
        str_map = {
            4: 'f',
            8: 'd'
        }

        def __init__(self, size):
            super().__init__()
            if size not in self.str_map:
                raise NotImplementedError('Does not support float of %d bytes', size)
            self.str = self.str_map[size]

        def decode(self, data: Union[bytes, bytearray], endianness: Endianness) -> float:
            endianness_char = '<' if endianness == Endianness.Little else '>'
            return struct.unpack(endianness_char + self.str, data)[0]

        def encode(self, value: Union[int, float, bool], endianness: Endianness) -> bytes:
            endianness_char = '<' if endianness == Endianness.Little else '>'

            return struct.pack(endianness_char + self.str, value)

    class BoolCodec(BaseCodec):
        def __init__(self):
            super().__init__()

        def decode(self, data: Union[bytes, bytearray], endianness: Endianness) -> bool:
            return True if data[0] != 0 else False

        def encode(self, value: Union[int, float, bool], endianness: Endianness) -> bytes:
            v = 1 if value is True else 0
            return struct.pack('B', v)

    class NotImplementedCodec(BaseCodec):
        def __init__(self, type_name: str):
            self.type_name = type_name

        def decode(self, data: Union[bytes, bytearray], endianness: Endianness) -> None:
            raise NotImplementedError('Decoding data for type %s is not supported yet' % self.type_name)

        def encode(self, value: Union[int, float, bool], endianness: Endianness) -> bytes:
            raise NotImplementedError('Encoding data for type %s is not supported yet' % self.type_name)

    name: str
    vartype: VariableType
    path_segments: List[str]
    location: VariableLocation
    endianness: Endianness
    bitsize: Optional[int]
    bitfield: Optional[int]
    bitoffset: Optional[int]
    enum: Optional[VariableEnum]

    TYPE_TO_CODEC_MAP: Dict[VariableType, BaseCodec] = {
        VariableType.sint8: SIntCodec(1),
        VariableType.sint16: SIntCodec(2),
        VariableType.sint32: SIntCodec(4),
        VariableType.sint64: SIntCodec(8),
        VariableType.sint128: NotImplementedCodec(VariableType.sint128.name),
        VariableType.sint256: NotImplementedCodec(VariableType.sint256.name),

        VariableType.uint8: UIntCodec(1),
        VariableType.uint16: UIntCodec(2),
        VariableType.uint32: UIntCodec(4),
        VariableType.uint64: UIntCodec(8),
        VariableType.uint128: NotImplementedCodec(VariableType.uint128.name),
        VariableType.uint256: NotImplementedCodec(VariableType.uint256.name),

        VariableType.float8: NotImplementedCodec(VariableType.float8.name),
        VariableType.float16: NotImplementedCodec(VariableType.float16.name),
        VariableType.float32: FloatCodec(4),
        VariableType.float64: FloatCodec(8),
        VariableType.float128: NotImplementedCodec(VariableType.float128.name),
        VariableType.float256: NotImplementedCodec(VariableType.float256.name),

        VariableType.cfloat8: NotImplementedCodec(VariableType.cfloat8.name),
        VariableType.cfloat16: NotImplementedCodec(VariableType.cfloat16.name),
        VariableType.cfloat32: NotImplementedCodec(VariableType.cfloat32.name),
        VariableType.cfloat64: NotImplementedCodec(VariableType.cfloat64.name),
        VariableType.cfloat128: NotImplementedCodec(VariableType.cfloat128.name),
        VariableType.cfloat256: NotImplementedCodec(VariableType.cfloat256.name),

        VariableType.boolean: BoolCodec(),
    }

    def __init__(self, name: str, vartype: VariableType, path_segments: List[str], location: Union[int, VariableLocation], endianness: Endianness, bitsize: Optional[int] = None, bitoffset: Optional[int] = None, enum: Optional[VariableEnum] = None):

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
                raise Exception('Cannot specify bitsize for variable of type %s' % str(VariableType))
            bitsize = var_size - bitoffset
        elif bitoffset is None and bitsize is not None:
            bitoffset = 0
        self.bitfield = False if bitoffset is None or bitsize is None else True
        self.bitsize = bitsize
        self.bitoffset = bitoffset
        self.enum = enum

    def decode(self, data: Union[bytes, bytearray]) -> Union[int, float, bool, None]:
        decoded = self.TYPE_TO_CODEC_MAP[self.vartype].decode(data, self.endianness)

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

        decoded = self.TYPE_TO_CODEC_MAP[self.vartype].decode(data, self.endianness)
        return decoded

    def encode(self, value: Union[int, float, bool]) -> Tuple[bytes, Optional[bytes]]:
        write_mask = None
        data = self.TYPE_TO_CODEC_MAP[self.vartype].encode(value, self.endianness)

        # todo bitfield set write_mask
        return data, write_mask

    def get_fullname(self) -> str:
        if len(self.path_segments) == 0:
            path_str = '/'
        else:
            path_str = '/' + '/'.join(self.path_segments)
        return '%s/%s' % (path_str, self.name)

    def get_type(self) -> VariableType:
        return self.vartype

    def get_path_segments(self) -> List[str]:
        return self.path_segments

    def get_address(self) -> int:
        return self.location.get_address()

    def has_enum(self) -> bool:
        return self.enum is not None

    def get_enum(self) -> Optional[VariableEnum]:
        return self.enum

    def get_size(self) -> Optional[int]:
        size_bit = self.vartype.get_size_bit()
        if size_bit is None:
            return size_bit
        else:
            return int(size_bit / 8)

    def __repr__(self):
        return '<%s - %s (%s) @ %s>' % (self.__class__.__name__, self.get_fullname(), self.vartype, self.location)
