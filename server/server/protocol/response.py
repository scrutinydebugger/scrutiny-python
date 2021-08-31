import struct
from enum import Enum
from .crc32 import crc32

class Response:

    class ResponseCode(Enum):
        OK = 0
        InvalidRequest = 1
        UnsupportedFeature = 2
        Overflow = 3
        Busy = 4

    def __init__(self, command, subfn, code, payload=b''):
        self.command = (command & 0x7F)
        self.subfn = subfn
        self.code = code
        self.payload = payload

    def make_bytes_no_crc(self):
        data = struct.pack('>BBB', (self.command | 0x80), self.subfn, self.code)
        data += struct.pack('>H', len(self.payload))
        data += self.payload
        return data

    def to_bytes(self):
        data = self.make_bytes_no_crc()
        data += struct.pack('>L', crc32(data))
        return data

    @classmethod
    def from_bytes(cls, data):
        if len(data) < 9:
            raise Exception('Not enough data in payload')

        cmd, subfn, code = struct.unpack('>BBB', data[:3])
        response = Response(cmd, subfn, code)
        length, = struct.unpack('>H', data[3:5])        
        response.payload = data[5:-4]
        if length != len(response.payload):
            raise Exception('Length mismatch between real payload length (%d) and encoded length (%d)' % (len(req.payload), length))
        crc = crc32(response.make_bytes_no_crc())
        received_crc, = struct.unpack('>L', data[-4:])

        if crc != received_crc:
            raise Exception('CRC mismatch. Expecting %d, received %d' % (crc, received_crc))

        return response


