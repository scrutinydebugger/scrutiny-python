#    test_crc.py
#        Make sure the CRC32 is working for the protocol
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.server.protocol.crc32 import crc32
from test import ScrutinyUnitTest


class TestCRC(ScrutinyUnitTest):

    def test_crc32(self):
        data = bytes([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        self.assertEqual(crc32(data), 622876539)


if __name__ == '__main__':
    import unittest
    unittest.main()
