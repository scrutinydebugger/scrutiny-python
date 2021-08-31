import struct
from .crc32 import crc32

class Request:
    def __init__(self, command, subfn, payload=b''):
        self.command = (command & 0x7F)
        self.subfn = subfn
        self.payload = payload

    def make_bytes_no_crc(self):
        data = struct.pack('>BB', (self.command & 0x7F), self.subfn)
        data += struct.pack('>H', len(self.payload))
        data += self.payload

        return data

    def to_bytes(self):
        data = self.make_bytes_no_crc()
        data += struct.pack('>L', crc32(data))
        return data

    @classmethod
    def from_bytes(cls, data):
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


