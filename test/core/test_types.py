#    test_types.py
#        Make some checks on Scrutiny basic types used project wide
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

from scrutiny.core.basic_types import *
from scrutiny.core.codecs import *
from test import ScrutinyUnitTest
import math


class TestTypes(ScrutinyUnitTest):

    def test_type_size(self):
        self.assertEqual(EmbeddedDataType.sint8.get_size_byte(), 1)
        self.assertEqual(EmbeddedDataType.sint16.get_size_byte(), 2)
        self.assertEqual(EmbeddedDataType.sint32.get_size_byte(), 4)
        self.assertEqual(EmbeddedDataType.sint64.get_size_byte(), 8)
        self.assertEqual(EmbeddedDataType.sint128.get_size_byte(), 16)
        self.assertEqual(EmbeddedDataType.sint256.get_size_byte(), 32)

        self.assertEqual(EmbeddedDataType.uint8.get_size_byte(), 1)
        self.assertEqual(EmbeddedDataType.uint16.get_size_byte(), 2)
        self.assertEqual(EmbeddedDataType.uint32.get_size_byte(), 4)
        self.assertEqual(EmbeddedDataType.uint64.get_size_byte(), 8)
        self.assertEqual(EmbeddedDataType.uint128.get_size_byte(), 16)
        self.assertEqual(EmbeddedDataType.uint256.get_size_byte(), 32)

        self.assertEqual(EmbeddedDataType.float8.get_size_byte(), 1)
        self.assertEqual(EmbeddedDataType.float16.get_size_byte(), 2)
        self.assertEqual(EmbeddedDataType.float32.get_size_byte(), 4)
        self.assertEqual(EmbeddedDataType.float64.get_size_byte(), 8)
        self.assertEqual(EmbeddedDataType.float128.get_size_byte(), 16)
        self.assertEqual(EmbeddedDataType.float256.get_size_byte(), 32)

        self.assertEqual(EmbeddedDataType.cfloat8.get_size_byte(), 1)
        self.assertEqual(EmbeddedDataType.cfloat16.get_size_byte(), 2)
        self.assertEqual(EmbeddedDataType.cfloat32.get_size_byte(), 4)
        self.assertEqual(EmbeddedDataType.cfloat64.get_size_byte(), 8)
        self.assertEqual(EmbeddedDataType.cfloat128.get_size_byte(), 16)
        self.assertEqual(EmbeddedDataType.cfloat256.get_size_byte(), 32)

        self.assertEqual(EmbeddedDataType.boolean.get_size_byte(), 1)

    def test_is_signed(self):
        self.assertTrue(EmbeddedDataType.sint8.is_signed())
        self.assertTrue(EmbeddedDataType.sint16.is_signed())
        self.assertTrue(EmbeddedDataType.sint32.is_signed())
        self.assertTrue(EmbeddedDataType.sint64.is_signed())
        self.assertTrue(EmbeddedDataType.sint128.is_signed())
        self.assertTrue(EmbeddedDataType.sint256.is_signed())

        self.assertFalse(EmbeddedDataType.uint8.is_signed())
        self.assertFalse(EmbeddedDataType.uint16.is_signed())
        self.assertFalse(EmbeddedDataType.uint32.is_signed())
        self.assertFalse(EmbeddedDataType.uint64.is_signed())
        self.assertFalse(EmbeddedDataType.uint128.is_signed())
        self.assertFalse(EmbeddedDataType.uint256.is_signed())

        self.assertTrue(EmbeddedDataType.float8.is_signed())
        self.assertTrue(EmbeddedDataType.float16.is_signed())
        self.assertTrue(EmbeddedDataType.float32.is_signed())
        self.assertTrue(EmbeddedDataType.float64.is_signed())
        self.assertTrue(EmbeddedDataType.float128.is_signed())
        self.assertTrue(EmbeddedDataType.float256.is_signed())

        self.assertTrue(EmbeddedDataType.cfloat8.is_signed())
        self.assertTrue(EmbeddedDataType.cfloat16.is_signed())
        self.assertTrue(EmbeddedDataType.cfloat32.is_signed())
        self.assertTrue(EmbeddedDataType.cfloat64.is_signed())
        self.assertTrue(EmbeddedDataType.cfloat128.is_signed())
        self.assertTrue(EmbeddedDataType.cfloat256.is_signed())

        self.assertFalse(EmbeddedDataType.boolean.is_signed())

    def test_is_integer(self):
        self.assertTrue(EmbeddedDataType.sint8.is_integer())
        self.assertTrue(EmbeddedDataType.sint16.is_integer())
        self.assertTrue(EmbeddedDataType.sint32.is_integer())
        self.assertTrue(EmbeddedDataType.sint64.is_integer())
        self.assertTrue(EmbeddedDataType.sint128.is_integer())
        self.assertTrue(EmbeddedDataType.sint256.is_integer())

        self.assertTrue(EmbeddedDataType.uint8.is_integer())
        self.assertTrue(EmbeddedDataType.uint16.is_integer())
        self.assertTrue(EmbeddedDataType.uint32.is_integer())
        self.assertTrue(EmbeddedDataType.uint64.is_integer())
        self.assertTrue(EmbeddedDataType.uint128.is_integer())
        self.assertTrue(EmbeddedDataType.uint256.is_integer())

        self.assertFalse(EmbeddedDataType.float8.is_integer())
        self.assertFalse(EmbeddedDataType.float16.is_integer())
        self.assertFalse(EmbeddedDataType.float32.is_integer())
        self.assertFalse(EmbeddedDataType.float64.is_integer())
        self.assertFalse(EmbeddedDataType.float128.is_integer())
        self.assertFalse(EmbeddedDataType.float256.is_integer())

        self.assertFalse(EmbeddedDataType.cfloat8.is_integer())
        self.assertFalse(EmbeddedDataType.cfloat16.is_integer())
        self.assertFalse(EmbeddedDataType.cfloat32.is_integer())
        self.assertFalse(EmbeddedDataType.cfloat64.is_integer())
        self.assertFalse(EmbeddedDataType.cfloat128.is_integer())
        self.assertFalse(EmbeddedDataType.cfloat256.is_integer())

        self.assertFalse(EmbeddedDataType.boolean.is_integer())

    def test_is_float(self):
        self.assertFalse(EmbeddedDataType.sint8.is_float())
        self.assertFalse(EmbeddedDataType.sint16.is_float())
        self.assertFalse(EmbeddedDataType.sint32.is_float())
        self.assertFalse(EmbeddedDataType.sint64.is_float())
        self.assertFalse(EmbeddedDataType.sint128.is_float())
        self.assertFalse(EmbeddedDataType.sint256.is_float())

        self.assertFalse(EmbeddedDataType.uint8.is_float())
        self.assertFalse(EmbeddedDataType.uint16.is_float())
        self.assertFalse(EmbeddedDataType.uint32.is_float())
        self.assertFalse(EmbeddedDataType.uint64.is_float())
        self.assertFalse(EmbeddedDataType.uint128.is_float())
        self.assertFalse(EmbeddedDataType.uint256.is_float())

        self.assertTrue(EmbeddedDataType.float8.is_float())
        self.assertTrue(EmbeddedDataType.float16.is_float())
        self.assertTrue(EmbeddedDataType.float32.is_float())
        self.assertTrue(EmbeddedDataType.float64.is_float())
        self.assertTrue(EmbeddedDataType.float128.is_float())
        self.assertTrue(EmbeddedDataType.float256.is_float())

        self.assertTrue(EmbeddedDataType.cfloat8.is_float())
        self.assertTrue(EmbeddedDataType.cfloat16.is_float())
        self.assertTrue(EmbeddedDataType.cfloat32.is_float())
        self.assertTrue(EmbeddedDataType.cfloat64.is_float())
        self.assertTrue(EmbeddedDataType.cfloat128.is_float())
        self.assertTrue(EmbeddedDataType.cfloat256.is_float())

        self.assertFalse(EmbeddedDataType.boolean.is_float())


class TestCodecs(ScrutinyUnitTest):
    def test_make_valid_sint(self):
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint8, 128), 127)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint8, -129), -128)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint8, -50), -50)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint8, 50), 50)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint8, -50, bitsize=5), -16)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint8, 50, bitsize=5), 15)

        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint16, 0x8000), 0x7FFF)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint16, -0x8001), -0x8000)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint16, -1000), -1000)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint16, 2000), 2000)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint16, -1000, bitsize=5), -16)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint16, 2000, bitsize=5), 15)

        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint32, 0x80000000), 0x7fffffff)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint32, -0x80000001), -0x80000000)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint32, -1000000), -1000000)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint32, 2000000), 2000000)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint32, -1000000, bitsize=5), -16)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint32, 2000000, bitsize=5), 15)

        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint64, 0x8000000000000000), 0x7fffffffffffffff)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint64, -0x8000000000000001), -0x8000000000000000)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint64, -0x123456789), -0x123456789)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint64, 0x234567892), 0x234567892)

        for dtype in [EmbeddedDataType.sint8, EmbeddedDataType.sint16, EmbeddedDataType.sint32, EmbeddedDataType.sint64]:
            with self.assertRaises(ValueError):
                Codecs.make_value_valid(dtype, math.nan)
            with self.assertRaises(ValueError):
                Codecs.make_value_valid(dtype, math.inf)
            with self.assertRaises(ValueError):
                Codecs.make_value_valid(dtype, -math.inf)

    def test_make_valid_uint(self):
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint8, 0x100), 0xFF)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint8, -1), 0)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint8, 50), 50)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint8, 50, bitsize=5), 31)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint8, -5, bitsize=5), 0)

        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint16, 0x10000), 0xFFFF)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint16, -1), 0)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint16, 2000), 2000)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint16, 2000, bitsize=5), 31)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint16, -500, bitsize=5), 0)

        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint32, 0x100000000), 0xffffffff)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint32, -1), 0)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint32, 2000000), 2000000)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint32, 2000000, bitsize=5), 31)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint32, -500000, bitsize=5), 0)

        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint64, 0x10000000000000000), 0xffffffffffffffff)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint64, -0x10000000000000000), 0)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint64, -1), 0)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint64, 0x234567892), 0x234567892)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint64, 2000000, bitsize=5), 31)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint64, -500000, bitsize=5), 0)

        for dtype in [EmbeddedDataType.uint8, EmbeddedDataType.uint16, EmbeddedDataType.uint32, EmbeddedDataType.uint64]:
            with self.assertRaises(ValueError):
                Codecs.make_value_valid(dtype, math.nan)
            with self.assertRaises(ValueError):
                Codecs.make_value_valid(dtype, math.inf)
            with self.assertRaises(ValueError):
                Codecs.make_value_valid(dtype, -math.inf)

    def test_make_valid_bool(self):
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.boolean, 1), True)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.boolean, 0), False)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.boolean, 0.0), False)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.boolean, 10000000000), True)

        with self.assertRaises(ValueError):
            Codecs.make_value_valid(EmbeddedDataType.boolean, math.nan)
        with self.assertRaises(ValueError):
            Codecs.make_value_valid(EmbeddedDataType.boolean, math.inf)
        with self.assertRaises(ValueError):
            Codecs.make_value_valid(EmbeddedDataType.boolean, -math.inf)


if __name__ == '__main__':
    import unittest
    unittest.main()
