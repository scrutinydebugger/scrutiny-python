#    test_memdump.py
#        Test the Memdump class functionalities
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import unittest
from scrutiny.core.memdump import Memdump


class TestMemdump(unittest.TestCase):
    def test_read_write_basic(self):
        memdump = Memdump()
        addr = 0x1234
        data = bytes(range(10))
        memdump.write(addr, data)
        data2 = memdump.read(addr, len(data))

        self.assertEqual(data, data2)

    def test_read_overflow(self):
        memdump = Memdump()
        addr = 0x1234
        data = bytes(range(10))
        memdump.write(addr, data)

        with self.assertRaises(Exception):
            memdump.read(addr - 1, len(data))

        with self.assertRaises(Exception):
            memdump.read(addr + 1, len(data))

    def test_merge_write(self):
        memdump = Memdump()
        data = bytes(range(10))
        memdump.write(0x1000, data)
        memdump.write(0x1005, data)
        data2 = memdump.read(0x1000, 15)
        self.assertEqual(data[0:5] + data, data2)

    def test_merge_write_limit_low_left(self):
        memdump = Memdump()
        data = bytes(range(10))
        memdump.write(1000, data)
        memdump.write(990, data)
        data2 = memdump.read(990, 20)
        self.assertEqual(data + data, data2)

    def test_merge_write_limit_high(self):
        memdump = Memdump()
        data = bytes(range(10))
        memdump.write(990, data)
        memdump.write(1000, data)
        data2 = memdump.read(990, 20)
        self.assertEqual(data + data, data2)

    def test_merge_write_middle(self):
        memdump = Memdump()
        data1 = bytes(range(30))
        data2 = bytes(range(10))
        memdump.write(1000, data1)
        memdump.write(1010, data2)
        data3 = memdump.read(1000, 30)
        self.assertEqual(data1[0:10] + data2 + data1[20:30], data3)

    def test_write_mutiple_overlap(self):
        memdump = Memdump()
        data = bytes(range(10))
        memdump.write(990, data)
        memdump.write(1000, data)
        memdump.write(1005, data)
        memdump.write(800, data)
        memdump.write(1100, data)
        memdump.write(995, data)
        self.assertEqual(data, memdump.read(800, len(data)))
        self.assertEqual(data, memdump.read(1100, len(data)))
        data2 = memdump.read(990, 25)
        self.assertEqual(data[0:5] + data + data, data2)
