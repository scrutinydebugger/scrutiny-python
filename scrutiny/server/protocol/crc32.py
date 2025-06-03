#    crc32.py
#        Compute a CRC32 for protocol validation
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

__all__ = ['crc32']

from typing import Union


def crc32(data: Union[bytes, bytearray]) -> int:
    """Computes the CRC32 of a byte array"""
    crc = 0xFFFFFFFF
    for i in range(len(data)):
        byte = data[i]
        for j in range(8):
            lsb = (byte ^ crc) & 1
            crc >>= 1
            if lsb:
                crc ^= 0xEDB88320
            byte >>= 1

    return not32(crc)


def not32(n: int) -> int:
    return (~n) & 0xFFFFFFFF
