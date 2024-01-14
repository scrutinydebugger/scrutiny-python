#    response.py
#        Represent a response sent by the device and received by the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import struct
import inspect
from enum import Enum

from .crc32 import crc32
from .commands.base_command import BaseCommand

from typing import Union, Type


class Response:
    """
    Represent a response that can be received from a device using the Scrutiny embedded protocol
    """
    command: Type[BaseCommand]
    subfn: int
    code: "ResponseCode"
    payload: bytes

    OVERHEAD_SIZE: int = 9

    class ResponseCode(Enum):
        OK = 0
        InvalidRequest = 1      # When the payload makes no sense for the given command
        UnsupportedFeature = 2  # When we request for a feature that is not supported
        Overflow = 3            # When the response cannot be sent because it would overflow a buffer
        Busy = 4                # When the request cannot be handled because the device is doing something else.
        FailureToProceed = 5    # Generic error for all other types of failures

    def __init__(self, command: Union[Type[BaseCommand], int], subfn: Union[int, Enum], code: ResponseCode, payload: bytes = b'') -> None:
        if inspect.isclass(command) and issubclass(command, BaseCommand):
            self.command = command
        elif isinstance(command, int):
            self.command = BaseCommand.from_command_id(command)
        else:
            raise ValueError('Command must be an integer or an instance of BaseCommand')

        self.command_id = self.command.response_id()
        if isinstance(subfn, Enum):
            self.subfn = subfn.value
        else:
            self.subfn = subfn
        self.code = self.ResponseCode(code)
        self.payload = bytes(payload)

    def size(self) -> int:
        """Returns the size of the byte encoded response"""
        return 9 + len(self.payload)

    def data_size(self) -> int:
        """Returns the length of the payload only (without protocol overhead)"""
        return len(self.payload)

    def make_bytes_no_crc(self) -> bytes:
        """Encode the response to bytes, without adding a CRC at the end"""
        data = struct.pack('>BBB', self.command_id, self.subfn, self.code.value)
        data += struct.pack('>H', len(self.payload))
        data += self.payload
        return data

    def to_bytes(self) -> bytes:
        """Encode the response to bytes"""
        data = self.make_bytes_no_crc()
        data += struct.pack('>L', crc32(data))
        return data

    @classmethod
    def from_bytes(cls, data: bytes) -> "Response":
        """Recreate a Response object from a byte-encoded response"""
        if len(data) < 9:
            raise Exception('Not enough data in payload')

        cmd, subfn, code = struct.unpack('>BBB', data[:3])
        response = Response(cmd, subfn, code)
        length, = struct.unpack('>H', data[3:5])
        response.payload = data[5:-4]
        if length != len(response.payload):
            raise Exception('Length mismatch between real payload length (%d) and encoded length (%d)' % (len(response.payload), length))
        crc = crc32(response.make_bytes_no_crc())
        received_crc, = struct.unpack('>L', data[-4:])

        if crc != received_crc:
            raise Exception('CRC mismatch. Expecting %d, received %d' % (crc, received_crc))

        return response

    def __repr__(self) -> str:
        if hasattr(self.command, 'Subfunction') and issubclass(self.command.Subfunction, Enum):
            try:
                enum_instance = self.command.Subfunction(self.subfn)
                subfn_name = '%s(%d)' % (enum_instance.name, enum_instance.value)
            except Exception:
                subfn_name = '%d' % self.subfn
        else:
            subfn_name = '%d' % self.subfn

        s = '<%s: %s(0x%02X), subfn=%s with code %s(%d). %d bytes of data >' % (
            self.__class__.__name__,
            self.command.__name__,
            self.command_id,
            subfn_name,
            self.code.name,
            self.code.value,
            len(self.payload)
        )
        return s

    def __str__(self) -> str:
        return self.__repr__()
