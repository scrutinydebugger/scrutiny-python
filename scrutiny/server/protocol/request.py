#    request.py
#        Represent a request sent by the server and received by the device
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import struct
import inspect
from enum import Enum

from .crc32 import crc32
from .commands.base_command import BaseCommand

from typing import Union, Type


class Request:
    command: Type[BaseCommand]
    subfn: Union[int, Enum]
    payload: bytes
    response_payload_size: int

    OVERHEAD_SIZE: int = 8

    def __init__(self, command: Union[Type[BaseCommand], int], subfn: Union[int, Enum], payload: bytes = b'', response_payload_size: int = 0):
        if inspect.isclass(command) and issubclass(command, BaseCommand):
            self.command = command
        elif isinstance(command, int):
            self.command = BaseCommand.from_command_id(command)
        else:
            raise ValueError('Command must be an integer or an instance of BaseCommand')

        self.command_id = self.command.request_id()
        if isinstance(subfn, Enum):
            self.subfn = subfn.value
        else:
            self.subfn = subfn
        self.payload = bytes(payload)
        self.response_payload_size = response_payload_size

    def make_bytes_no_crc(self) -> bytes:
        data = struct.pack('>BB', (self.command_id & 0x7F), self.subfn)
        data += struct.pack('>H', len(self.payload))
        data += self.payload

        return data

    def to_bytes(self) -> bytes:
        data = self.make_bytes_no_crc()
        data += struct.pack('>L', crc32(data))
        return data

    def get_expected_response_size(self) -> int:
        return 9 + self.response_payload_size

    def size(self) -> int:
        return 8 + len(self.payload)

    @classmethod
    def from_bytes(cls, data: bytes):
        if len(data) < 8:
            raise Exception('Not enough data in payload')

        cmd, subfn = struct.unpack('>BB', data[:2])
        if (cmd & 0x80) > 0:
            raise Exception('Command MSB indicates this message is a Response.')

        req = Request(cmd, subfn)
        length, = struct.unpack('>H', data[2:4])
        req.payload = data[4:-4]
        if length != len(req.payload):
            raise Exception('Length mismatch between real payload length (%d) and encoded length (%d)' % (len(req.payload), length))
        crc = crc32(req.make_bytes_no_crc())
        received_crc, = struct.unpack('>L', data[-4:])

        if crc != received_crc:
            raise Exception('CRC mismatch. Expecting %d, received %d' % (crc, received_crc))

        return req

    def __repr__(self):
        try:
            enum_instance = self.command.Subfunction(self.subfn)
            subfn_name = '%s(%d)' % (enum_instance.name, enum_instance.value)
        except:
            subfn_name = '%d' % self.subfn

        s = '<%s: %s(0x%02X), subfn=%s. %d bytes of data >' % (
            __class__.__name__,
            self.command.__name__,
            self.command_id,
            subfn_name,
            len(self.payload)
        )
        return s

    def __str__(self):
        return self.__repr__()
