#    crc32.py
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

def crc32(data: bytes) -> int:
    crc = 0xFFFFFFFF;
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
