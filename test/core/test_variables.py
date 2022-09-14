#    test_variables.py
#        Test the behavior of variable manipulation tools
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import unittest
import struct

from scrutiny.core.variable import *


def d2f(d):
    return struct.unpack('f', struct.pack('f', d))[0]


class TestVariables(unittest.TestCase):
    def test_variable_encode_no_bitfield(self):
        # Floating point
        f32_le = Variable('float32_le', vartype=EmbeddedDataType.float32, path_segments=[], location=0, endianness=Endianness.Little)
        f32_be = Variable('float32_be', vartype=EmbeddedDataType.float32, path_segments=[], location=0, endianness=Endianness.Big)
        f64_le = Variable('float64_le', vartype=EmbeddedDataType.float64, path_segments=[], location=0, endianness=Endianness.Little)
        f64_be = Variable('float64_be', vartype=EmbeddedDataType.float64, path_segments=[], location=0, endianness=Endianness.Big)

        self.assertEqual(f32_le.encode(-1.2)[0], struct.pack('<f', -1.2))
        self.assertEqual(f32_be.encode(1.2)[0], struct.pack('>f', 1.2))
        self.assertEqual(f64_le.encode(-1.2)[0], struct.pack('<d', -1.2))
        self.assertEqual(f64_be.encode(1.2)[0], struct.pack('>d', 1.2))

        # Signed int
        int8_le = Variable('int8_le', vartype=EmbeddedDataType.sint8, path_segments=[], location=0, endianness=Endianness.Little)
        int8_be = Variable('int8_be', vartype=EmbeddedDataType.sint8, path_segments=[], location=0, endianness=Endianness.Big)
        int16_le = Variable('int16_le', vartype=EmbeddedDataType.sint16, path_segments=[], location=0, endianness=Endianness.Little)
        int16_be = Variable('int16_be', vartype=EmbeddedDataType.sint16, path_segments=[], location=0, endianness=Endianness.Big)
        int32_le = Variable('int32_le', vartype=EmbeddedDataType.sint32, path_segments=[], location=0, endianness=Endianness.Little)
        int32_be = Variable('int32_be', vartype=EmbeddedDataType.sint32, path_segments=[], location=0, endianness=Endianness.Big)
        int64_le = Variable('int64_le', vartype=EmbeddedDataType.sint64, path_segments=[], location=0, endianness=Endianness.Little)
        int64_be = Variable('int64_be', vartype=EmbeddedDataType.sint64, path_segments=[], location=0, endianness=Endianness.Big)

        self.assertEqual(int8_le.encode(-42)[0], struct.pack('<b', -42))
        self.assertEqual(int8_be.encode(43)[0], struct.pack('>b', 43))
        self.assertEqual(int16_le.encode(0x1234)[0], struct.pack('<h', 0x1234))
        self.assertEqual(int16_be.encode(-0x2222)[0], struct.pack('>h', -0x2222))
        self.assertEqual(int32_le.encode(-0x11223344)[0], struct.pack('<l', -0x11223344))
        self.assertEqual(int32_be.encode(0x11223344)[0], struct.pack('>l', 0x11223344))
        self.assertEqual(int64_le.encode(-0x1122334455667788)[0], struct.pack('<q', -0x1122334455667788))
        self.assertEqual(int64_be.encode(0x1122334455667788)[0], struct.pack('>q', 0x1122334455667788))

        # Unsigned int
        uint8_le = Variable('uint8_le', vartype=EmbeddedDataType.uint8, path_segments=[], location=0, endianness=Endianness.Little)
        uint8_be = Variable('uint8_be', vartype=EmbeddedDataType.uint8, path_segments=[], location=0, endianness=Endianness.Big)
        uint16_le = Variable('uint16_le', vartype=EmbeddedDataType.uint16, path_segments=[], location=0, endianness=Endianness.Little)
        uint16_be = Variable('uint16_be', vartype=EmbeddedDataType.uint16, path_segments=[], location=0, endianness=Endianness.Big)
        uint32_le = Variable('uint32_le', vartype=EmbeddedDataType.uint32, path_segments=[], location=0, endianness=Endianness.Little)
        uint32_be = Variable('uint32_be', vartype=EmbeddedDataType.uint32, path_segments=[], location=0, endianness=Endianness.Big)
        uint64_le = Variable('uint64_le', vartype=EmbeddedDataType.uint64, path_segments=[], location=0, endianness=Endianness.Little)
        uint64_be = Variable('uint64_be', vartype=EmbeddedDataType.uint64, path_segments=[], location=0, endianness=Endianness.Big)

        self.assertEqual(uint8_le.encode(0xaa)[0], struct.pack('<B', 0xaa))
        self.assertEqual(uint8_be.encode(0x55)[0], struct.pack('>B', 0x55))
        self.assertEqual(uint16_le.encode(0x1234)[0], struct.pack('<H', 0x1234))
        self.assertEqual(uint16_be.encode(0xfdec)[0], struct.pack('>H', 0xfdec))
        self.assertEqual(uint32_le.encode(0x11223344)[0], struct.pack('<L', 0x11223344))
        self.assertEqual(uint32_be.encode(0xffeeddcc)[0], struct.pack('>L', 0xffeeddcc))
        self.assertEqual(uint64_le.encode(0x1122334455667788)[0], struct.pack('<Q', 0x1122334455667788))
        self.assertEqual(uint64_be.encode(0xffeeddccbbaa9988)[0], struct.pack('>Q', 0xffeeddccbbaa9988))

        # Booleans
        bool_le = Variable('bool_le', vartype=EmbeddedDataType.boolean, path_segments=[], location=0, endianness=Endianness.Little)
        bool_be = Variable('bool_be', vartype=EmbeddedDataType.boolean, path_segments=[], location=0, endianness=Endianness.Little)

        self.assertEqual(uint8_le.encode(True)[0], struct.pack('<B', 1))
        self.assertEqual(uint8_be.encode(True)[0], struct.pack('>B', 1))
        self.assertEqual(uint8_le.encode(False)[0], struct.pack('<B', 0))
        self.assertEqual(uint8_be.encode(False)[0], struct.pack('>B', 0))

    def test_variable_decode_no_bitfield(self):
        # Floating point
        f32_le = Variable('float32_le', vartype=EmbeddedDataType.float32, path_segments=[], location=0, endianness=Endianness.Little)
        f32_be = Variable('float32_be', vartype=EmbeddedDataType.float32, path_segments=[], location=0, endianness=Endianness.Big)
        f64_le = Variable('float64_le', vartype=EmbeddedDataType.float64, path_segments=[], location=0, endianness=Endianness.Little)
        f64_be = Variable('float64_be', vartype=EmbeddedDataType.float64, path_segments=[], location=0, endianness=Endianness.Big)

        self.assertEqual(f32_le.decode(struct.pack('<f', -1.2)), d2f(-1.2))
        self.assertEqual(f32_be.decode(struct.pack('>f', 1.2)), d2f(1.2))
        self.assertEqual(f64_le.decode(struct.pack('<d', -1.2)), -1.2)
        self.assertEqual(f64_be.decode(struct.pack('>d', 1.2)), 1.2)

        # Signed int
        int8_le = Variable('int8_le', vartype=EmbeddedDataType.sint8, path_segments=[], location=0, endianness=Endianness.Little)
        int8_be = Variable('int8_be', vartype=EmbeddedDataType.sint8, path_segments=[], location=0, endianness=Endianness.Big)
        int16_le = Variable('int16_le', vartype=EmbeddedDataType.sint16, path_segments=[], location=0, endianness=Endianness.Little)
        int16_be = Variable('int16_be', vartype=EmbeddedDataType.sint16, path_segments=[], location=0, endianness=Endianness.Big)
        int32_le = Variable('int32_le', vartype=EmbeddedDataType.sint32, path_segments=[], location=0, endianness=Endianness.Little)
        int32_be = Variable('int32_be', vartype=EmbeddedDataType.sint32, path_segments=[], location=0, endianness=Endianness.Big)
        int64_le = Variable('int64_le', vartype=EmbeddedDataType.sint64, path_segments=[], location=0, endianness=Endianness.Little)
        int64_be = Variable('int64_be', vartype=EmbeddedDataType.sint64, path_segments=[], location=0, endianness=Endianness.Big)

        self.assertEqual(int8_le.decode(struct.pack('<b', -42)), -42)
        self.assertEqual(int8_be.decode(struct.pack('>b', 43)), 43)
        self.assertEqual(int16_le.decode(struct.pack('<h', 0x1234)), 0x1234)
        self.assertEqual(int16_be.decode(struct.pack('>h', -0x2222)), -0x2222)
        self.assertEqual(int32_le.decode(struct.pack('<l', -0x11223344)), -0x11223344)
        self.assertEqual(int32_be.decode(struct.pack('>l', 0x11223344)), 0x11223344)
        self.assertEqual(int64_le.decode(struct.pack('<q', -0x1122334455667788)), -0x1122334455667788)
        self.assertEqual(int64_be.decode(struct.pack('>q', 0x1122334455667788)), 0x1122334455667788)

        # Unsigned int
        uint8_le = Variable('uint8_le', vartype=EmbeddedDataType.uint8, path_segments=[], location=0, endianness=Endianness.Little)
        uint8_be = Variable('uint8_be', vartype=EmbeddedDataType.uint8, path_segments=[], location=0, endianness=Endianness.Big)
        uint16_le = Variable('uint16_le', vartype=EmbeddedDataType.uint16, path_segments=[], location=0, endianness=Endianness.Little)
        uint16_be = Variable('uint16_be', vartype=EmbeddedDataType.uint16, path_segments=[], location=0, endianness=Endianness.Big)
        uint32_le = Variable('uint32_le', vartype=EmbeddedDataType.uint32, path_segments=[], location=0, endianness=Endianness.Little)
        uint32_be = Variable('uint32_be', vartype=EmbeddedDataType.uint32, path_segments=[], location=0, endianness=Endianness.Big)
        uint64_le = Variable('uint64_le', vartype=EmbeddedDataType.uint64, path_segments=[], location=0, endianness=Endianness.Little)
        uint64_be = Variable('uint64_be', vartype=EmbeddedDataType.uint64, path_segments=[], location=0, endianness=Endianness.Big)

        self.assertEqual(uint8_le.decode(struct.pack('<B', 0xaa)), 0xaa)
        self.assertEqual(uint8_be.decode(struct.pack('>B', 0x55)), 0x55)
        self.assertEqual(uint16_le.decode(struct.pack('<H', 0x1234)), 0x1234)
        self.assertEqual(uint16_be.decode(struct.pack('>H', 0xfdec)), 0xfdec)
        self.assertEqual(uint32_le.decode(struct.pack('<L', 0x11223344)), 0x11223344)
        self.assertEqual(uint32_be.decode(struct.pack('>L', 0xffeeddcc)), 0xffeeddcc)
        self.assertEqual(uint64_le.decode(struct.pack('<Q', 0x1122334455667788)), 0x1122334455667788)
        self.assertEqual(uint64_be.decode(struct.pack('>Q', 0xffeeddccbbaa9988)), 0xffeeddccbbaa9988)

        # Booleans
        bool_le = Variable('bool_le', vartype=EmbeddedDataType.boolean, path_segments=[], location=0, endianness=Endianness.Little)
        bool_be = Variable('bool_be', vartype=EmbeddedDataType.boolean, path_segments=[], location=0, endianness=Endianness.Little)

        self.assertEqual(uint8_le.decode(struct.pack('<B', 1)), True)
        self.assertEqual(uint8_be.decode(struct.pack('>B', 1)), True)
        self.assertEqual(uint8_le.decode(struct.pack('<B', 0)), False)
        self.assertEqual(uint8_be.decode(struct.pack('>B', 0)), False)
