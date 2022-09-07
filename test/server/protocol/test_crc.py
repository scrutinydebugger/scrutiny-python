#    test_crc.py
#        Make sure the CRC32 is working for the protocol
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import unittest

from scrutiny.server.protocol.crc32 import crc32

class TestCRC(unittest.TestCase):

    def test_crc32(self):
        data = bytes([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        self.assertEqual(crc32(data), 622876539)
