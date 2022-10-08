#    codecs.py
#        Contains classes capable to encode/decode data exchanged with embedded side
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

from abc import ABC, abstractmethod
from scrutiny.core.basic_types import Endianness, EmbeddedDataType
import struct

from typing import Union, Optional, Tuple

Encodable = Union[int, float, bool]


class BaseCodec(ABC):
    def __init__(self,):
        pass

    @abstractmethod
    def decode(self, data: Union[bytes, bytearray], mask: Optional[bytes] = None) -> Encodable:
        pass

    @abstractmethod
    def encode(self, value: Encodable) -> bytes:
        pass


class SIntCodec(BaseCodec):
    str_map = {
        1: 'b',
        2: 'h',
        4: 'l',
        8: 'q'
    }

    def __init__(self, size: int, endianness: Endianness):
        super().__init__()
        if size not in self.str_map:
            raise NotImplementedError('Does not support signed int of %d bytes', size)
        endianness_char = '<' if endianness == Endianness.Little else '>'
        self.packstr = endianness_char + self.str_map[size]

    def decode(self, data: Union[bytes, bytearray], mask: Optional[bytes] = None) -> int:
        return struct.unpack(self.packstr, data)[0]

    def encode(self, value: Encodable) -> bytes:
        return struct.pack(self.packstr, value)


class UIntCodec(BaseCodec):
    str_map = {
        1: 'B',
        2: 'H',
        4: 'L',
        8: 'Q'
    }

    def __init__(self, size: int, endianness: Endianness):
        super().__init__()
        if size not in self.str_map:
            raise NotImplementedError('Does not support unsigend signed int of %d bytes', size)
        endianness_char = '<' if endianness == Endianness.Little else '>'
        self.packstr = endianness_char + self.str_map[size]

    def decode(self, data: Union[bytes, bytearray], mask: Optional[bytes] = None) -> int:
        return struct.unpack(self.packstr, data)[0]

    def encode(self, value: Encodable) -> bytes:
        return struct.pack(self.packstr, value)  # todo : Mask


class FloatCodec(BaseCodec):
    str_map = {
        4: 'f',
        8: 'd'
    }

    def __init__(self, size: int, endianness: Endianness):
        super().__init__()
        if size not in self.str_map:
            raise NotImplementedError('Does not support float of %d bytes', size)
        endianness_char = '<' if endianness == Endianness.Little else '>'
        self.packstr = endianness_char + self.str_map[size]

    def decode(self, data: Union[bytes, bytearray], mask: Optional[bytes] = None) -> float:
        return struct.unpack(self.packstr, data)[0]

    def encode(self, value: Encodable) -> bytes:
        return struct.pack(self.packstr, value)  # todo : Mask


class BoolCodec(BaseCodec):
    def __init__(self):
        super().__init__()

    def decode(self, data: Union[bytes, bytearray], mask: Optional[bytes] = None) -> bool:
        return True if data[0] != 0 else False

    def encode(self, value: Encodable) -> bytes:
        v = 1 if value else 0
        return struct.pack('B', v)  # todo : Mask


class Codecs:
    """
    Common interface to get the correct code for a given embedded datatype
    """
    @staticmethod
    def get(vartype: EmbeddedDataType, endianness: Endianness) -> BaseCodec:
        datasize = vartype.get_size_byte()

        if vartype in [EmbeddedDataType.sint8, EmbeddedDataType.sint16, EmbeddedDataType.sint32, EmbeddedDataType.sint64]:
            return SIntCodec(datasize, endianness=endianness)
        elif vartype in [EmbeddedDataType.uint8, EmbeddedDataType.uint16, EmbeddedDataType.uint32, EmbeddedDataType.uint64]:
            return UIntCodec(datasize, endianness=endianness)
        elif vartype in [EmbeddedDataType.float64, EmbeddedDataType.float32]:
            return FloatCodec(datasize, endianness=endianness)
        elif vartype in [EmbeddedDataType.boolean]:
            return BoolCodec()

        raise NotImplementedError("No codec defined for variable type %s" % vartype)
