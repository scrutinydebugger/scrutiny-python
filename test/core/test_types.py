#    test_types.py
#        Make some checks on Scrutiny basic types used project wide
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import unittest

from scrutiny.core.basic_types import *


class TestTypes(unittest.TestCase):

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

        self.assertIsNone(EmbeddedDataType.struct.get_size_byte())
