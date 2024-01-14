#    codecs.py
#        Contains classes capable to encode/decode data exchanged with embedded side
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = [
    'Encodable',
    'BaseCodec',
    'SIntCodec',
    'UIntCodec',
    'FloatCodec',
    'BoolCodec',
    'Codecs'
]

from abc import ABC, abstractmethod
from scrutiny.core.basic_types import Endianness, EmbeddedDataType
import struct

from typing import Union, Optional
import math

Encodable = Union[int, float, bool]


class BaseCodec(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def decode(self, data: Union[bytes, bytearray]) -> Encodable:
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

    def __init__(self, size: int, endianness: Endianness) -> None:
        super().__init__()
        if size not in self.str_map:
            raise NotImplementedError('Does not support signed int of %d bytes', size)
        endianness_char = '<' if endianness == Endianness.Little else '>'
        self.packstr = endianness_char + self.str_map[size]

    def decode(self, data: Union[bytes, bytearray]) -> int:
        return int(struct.unpack(self.packstr, data)[0])

    def encode(self, value: Encodable) -> bytes:
        return struct.pack(self.packstr, value)


class UIntCodec(BaseCodec):
    str_map = {
        1: 'B',
        2: 'H',
        4: 'L',
        8: 'Q'
    }

    def __init__(self, size: int, endianness: Endianness) -> None:
        super().__init__()
        if size not in self.str_map:
            raise NotImplementedError('Does not support unsigend signed int of %d bytes', size)
        endianness_char = '<' if endianness == Endianness.Little else '>'
        self.packstr = endianness_char + self.str_map[size]

    def decode(self, data: Union[bytes, bytearray]) -> int:
        return int(struct.unpack(self.packstr, data)[0])

    def encode(self, value: Encodable) -> bytes:
        return struct.pack(self.packstr, value)


class FloatCodec(BaseCodec):
    str_map = {
        4: 'f',
        8: 'd'
    }

    def __init__(self, size: int, endianness: Endianness) -> None:
        super().__init__()
        if size not in self.str_map:
            raise NotImplementedError('Does not support float of %d bytes', size)
        endianness_char = '<' if endianness == Endianness.Little else '>'
        self.packstr = endianness_char + self.str_map[size]

    def decode(self, data: Union[bytes, bytearray]) -> float:
        return float(struct.unpack(self.packstr, data)[0])

    def encode(self, value: Encodable) -> bytes:
        return struct.pack(self.packstr, value)


class BoolCodec(BaseCodec):
    def __init__(self) -> None:
        super().__init__()

    def decode(self, data: Union[bytes, bytearray]) -> bool:
        return True if data[0] != 0 else False

    def encode(self, value: Encodable) -> bytes:
        v = 1 if value else 0
        return struct.pack('B', v)


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

    @staticmethod
    def make_value_valid(vartype: EmbeddedDataType, val: Encodable, bitsize: Optional[int] = None) -> Encodable:
        if not math.isfinite(val):
            raise ValueError("Does not support non-finite values")
        if vartype == EmbeddedDataType.boolean:
            return False if int(val) == 0 else True

        if isinstance(val, bool):
            val = int(val)
        signed = vartype.is_signed()

        if vartype.is_integer():
            data_size = vartype.get_size_bit()
            if bitsize is not None:
                data_size = min(data_size, bitsize)
            if data_size <= 0 or data_size > 256:
                ValueError("Does not support this data size: %d bits" % data_size)

            val = int(val)
            if signed:
                upper_limit = 1 << (data_size - 1)
                val = min(val, upper_limit - 1)
                val = max(val, -upper_limit)
            else:
                upper_limit = 1 << (data_size)
                val = min(val, upper_limit - 1)
                val = max(val, 0)

        elif vartype.is_float():
            val = float(val)
            if not math.isfinite(val):
                raise ValueError("Float values must be finite")

        return val
