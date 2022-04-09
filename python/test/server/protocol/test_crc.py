import unittest

from scrutiny.server.protocol.crc32 import crc32

class TestCRC(unittest.TestCase):

    def test_crc32(self):
        data = bytes([1,2,3,4,5,6,7,8,9,10])
        self.assertEqual(crc32(data), 622876539)