#    test_variables.py
#        Test the behavior of variable manipulation tools
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

import struct

from scrutiny.core.variable import *
from binascii import unhexlify
from test import ScrutinyUnitTest
from scrutiny.core.basic_types import EmbeddedDataType, Endianness


def d2f(d):
    return struct.unpack('f', struct.pack('f', d))[0]


class TestVariables(ScrutinyUnitTest):
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

        self.assertEqual(bool_le.encode(True)[0], struct.pack('<B', 1))
        self.assertEqual(bool_be.encode(True)[0], struct.pack('>B', 1))
        self.assertEqual(bool_le.encode(False)[0], struct.pack('<B', 0))
        self.assertEqual(bool_be.encode(False)[0], struct.pack('>B', 0))

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

        self.assertEqual(bool_le.decode(struct.pack('<B', 1)), True)
        self.assertEqual(bool_be.decode(struct.pack('>B', 1)), True)
        self.assertEqual(bool_le.decode(struct.pack('<B', 0)), False)
        self.assertEqual(bool_be.decode(struct.pack('>B', 0)), False)

    def test_write_masks_no_bitfield(self):
        uint8_le = Variable('uint8_le', vartype=EmbeddedDataType.uint8, path_segments=[], location=0, endianness=Endianness.Little)
        uint8_be = Variable('uint8_be', vartype=EmbeddedDataType.uint8, path_segments=[], location=0, endianness=Endianness.Big)
        uint16_le = Variable('uint16_le', vartype=EmbeddedDataType.uint16, path_segments=[], location=0, endianness=Endianness.Little)
        uint16_be = Variable('uint16_be', vartype=EmbeddedDataType.uint16, path_segments=[], location=0, endianness=Endianness.Big)
        uint32_le = Variable('uint32_le', vartype=EmbeddedDataType.uint32, path_segments=[], location=0, endianness=Endianness.Little)
        uint32_be = Variable('uint32_be', vartype=EmbeddedDataType.uint32, path_segments=[], location=0, endianness=Endianness.Big)
        uint64_le = Variable('uint64_le', vartype=EmbeddedDataType.uint64, path_segments=[], location=0, endianness=Endianness.Little)
        uint64_be = Variable('uint64_be', vartype=EmbeddedDataType.uint64, path_segments=[], location=0, endianness=Endianness.Big)
        int8_le = Variable('int8_le', vartype=EmbeddedDataType.sint8, path_segments=[], location=0, endianness=Endianness.Little)
        int8_be = Variable('int8_be', vartype=EmbeddedDataType.sint8, path_segments=[], location=0, endianness=Endianness.Big)
        int16_le = Variable('int16_le', vartype=EmbeddedDataType.sint16, path_segments=[], location=0, endianness=Endianness.Little)
        int16_be = Variable('int16_be', vartype=EmbeddedDataType.sint16, path_segments=[], location=0, endianness=Endianness.Big)
        int32_le = Variable('int32_le', vartype=EmbeddedDataType.sint32, path_segments=[], location=0, endianness=Endianness.Little)
        int32_be = Variable('int32_be', vartype=EmbeddedDataType.sint32, path_segments=[], location=0, endianness=Endianness.Big)
        int64_le = Variable('int64_le', vartype=EmbeddedDataType.sint64, path_segments=[], location=0, endianness=Endianness.Little)
        int64_be = Variable('int64_be', vartype=EmbeddedDataType.sint64, path_segments=[], location=0, endianness=Endianness.Big)
        bool_le = Variable('bool_le', vartype=EmbeddedDataType.boolean, path_segments=[], location=0, endianness=Endianness.Little)
        bool_be = Variable('bool_be', vartype=EmbeddedDataType.boolean, path_segments=[], location=0, endianness=Endianness.Little)

        self.assertEqual(uint8_le.get_bitfield_mask(), unhexlify('FF'))
        self.assertEqual(uint8_be.get_bitfield_mask(), unhexlify('FF'))
        self.assertEqual(uint16_le.get_bitfield_mask(), unhexlify('FFFF'))
        self.assertEqual(uint16_be.get_bitfield_mask(), unhexlify('FFFF'))
        self.assertEqual(uint32_le.get_bitfield_mask(), unhexlify('FFFFFFFF'))
        self.assertEqual(uint32_be.get_bitfield_mask(), unhexlify('FFFFFFFF'))
        self.assertEqual(uint64_le.get_bitfield_mask(), unhexlify('FFFFFFFFFFFFFFFF'))
        self.assertEqual(uint64_be.get_bitfield_mask(), unhexlify('FFFFFFFFFFFFFFFF'))
        self.assertEqual(int8_le.get_bitfield_mask(), unhexlify('FF'))
        self.assertEqual(int8_be.get_bitfield_mask(), unhexlify('FF'))
        self.assertEqual(int16_le.get_bitfield_mask(), unhexlify('FFFF'))
        self.assertEqual(int16_be.get_bitfield_mask(), unhexlify('FFFF'))
        self.assertEqual(int32_le.get_bitfield_mask(), unhexlify('FFFFFFFF'))
        self.assertEqual(int32_be.get_bitfield_mask(), unhexlify('FFFFFFFF'))
        self.assertEqual(int64_le.get_bitfield_mask(), unhexlify('FFFFFFFFFFFFFFFF'))
        self.assertEqual(int64_be.get_bitfield_mask(), unhexlify('FFFFFFFFFFFFFFFF'))
        self.assertEqual(bool_le.get_bitfield_mask(), unhexlify('FF'))
        self.assertEqual(bool_be.get_bitfield_mask(), unhexlify('FF'))

    def assert_var_bitfield_mask(self, vartype: EmbeddedDataType, endianness: Endianness, bitoffset: int, bitsize: int, expected_mask: bytes) -> None:
        v = Variable('aaa', vartype=vartype, path_segments=[],
                     location=0, endianness=endianness, bitoffset=bitoffset, bitsize=bitsize)
        self.assertEqual(v.get_bitfield_mask(), expected_mask)

    def test_write_masks_bitfields(self):
        self.assert_var_bitfield_mask(EmbeddedDataType.uint8, Endianness.Little, bitoffset=5, bitsize=3, expected_mask=unhexlify('E0'))
        self.assert_var_bitfield_mask(EmbeddedDataType.uint16, Endianness.Little, bitoffset=4, bitsize=9, expected_mask=unhexlify('F01F'))
        self.assert_var_bitfield_mask(EmbeddedDataType.uint32, Endianness.Little, bitoffset=7, bitsize=13, expected_mask=unhexlify('80FF0F00'))
        self.assert_var_bitfield_mask(EmbeddedDataType.uint64, Endianness.Little, bitoffset=30,
                                      bitsize=33, expected_mask=unhexlify('000000C0FFFFFF7F'))
        self.assert_var_bitfield_mask(EmbeddedDataType.uint8, Endianness.Big, bitoffset=5, bitsize=3, expected_mask=unhexlify('E0'))
        self.assert_var_bitfield_mask(EmbeddedDataType.uint16, Endianness.Big, bitoffset=4, bitsize=9, expected_mask=unhexlify('1FF0'))
        self.assert_var_bitfield_mask(EmbeddedDataType.uint32, Endianness.Big, bitoffset=7, bitsize=13, expected_mask=unhexlify('000FFF80'))
        self.assert_var_bitfield_mask(EmbeddedDataType.uint64, Endianness.Big, bitoffset=30,
                                      bitsize=33, expected_mask=unhexlify('7FFFFFFFC0000000'))

        self.assert_var_bitfield_mask(EmbeddedDataType.sint8, Endianness.Little, bitoffset=5, bitsize=3, expected_mask=unhexlify('E0'))
        self.assert_var_bitfield_mask(EmbeddedDataType.sint16, Endianness.Little, bitoffset=4, bitsize=9, expected_mask=unhexlify('F01F'))
        self.assert_var_bitfield_mask(EmbeddedDataType.sint32, Endianness.Little, bitoffset=7, bitsize=13, expected_mask=unhexlify('80FF0F00'))
        self.assert_var_bitfield_mask(EmbeddedDataType.sint64, Endianness.Little, bitoffset=30,
                                      bitsize=33, expected_mask=unhexlify('000000C0FFFFFF7F'))
        self.assert_var_bitfield_mask(EmbeddedDataType.sint8, Endianness.Big, bitoffset=5, bitsize=3, expected_mask=unhexlify('E0'))
        self.assert_var_bitfield_mask(EmbeddedDataType.sint16, Endianness.Big, bitoffset=4, bitsize=9, expected_mask=unhexlify('1FF0'))
        self.assert_var_bitfield_mask(EmbeddedDataType.sint32, Endianness.Big, bitoffset=7, bitsize=13, expected_mask=unhexlify('000FFF80'))
        self.assert_var_bitfield_mask(EmbeddedDataType.sint64, Endianness.Big, bitoffset=30,
                                      bitsize=33, expected_mask=unhexlify('7FFFFFFFC0000000'))

        self.assert_var_bitfield_mask(EmbeddedDataType.boolean, Endianness.Little, bitoffset=5, bitsize=3, expected_mask=unhexlify('E0'))
        self.assert_var_bitfield_mask(EmbeddedDataType.boolean, Endianness.Big, bitoffset=5, bitsize=3, expected_mask=unhexlify('E0'))

        exception_combinations = [
            (EmbeddedDataType.boolean, 0, 9),
            (EmbeddedDataType.boolean, 5, 0),
            (EmbeddedDataType.boolean, 5, 4),
            (EmbeddedDataType.uint8, 5, 4),
            (EmbeddedDataType.sint8, 5, 4),
            (EmbeddedDataType.uint16, 5, 12),
            (EmbeddedDataType.sint16, 12, 5),
            (EmbeddedDataType.uint32, 20, 13),
            (EmbeddedDataType.sint32, 0, 33),
            (EmbeddedDataType.uint64, 0, 65),
            (EmbeddedDataType.sint64, 60, 5),
            (EmbeddedDataType.float32, 0, 31),
            (EmbeddedDataType.float32, 0, 32),
            (EmbeddedDataType.float32, 0, 33),
            (EmbeddedDataType.float64, 0, 64),
        ]

        for combination in exception_combinations:
            with self.assertRaises(ValueError):
                Variable('a', vartype=combination[0], path_segments=[], location=0,
                         endianness=Endianness.Little, bitoffset=combination[1], bitsize=combination[2])
            with self.assertRaises(ValueError):
                Variable('a', vartype=combination[0], path_segments=[], location=0,
                         endianness=Endianness.Big, bitoffset=combination[1], bitsize=combination[2])

        ok_combinations = [
            (EmbeddedDataType.boolean, 0, 8),
            (EmbeddedDataType.boolean, 5, 3),
            (EmbeddedDataType.uint8, 0, 8),
            (EmbeddedDataType.sint8, 7, 1),
            (EmbeddedDataType.uint16, 5, 11),
            (EmbeddedDataType.sint16, 11, 5),
            (EmbeddedDataType.uint32, 20, 12),
            (EmbeddedDataType.sint32, 0, 32),
            (EmbeddedDataType.uint64, 0, 64),
            (EmbeddedDataType.sint64, 60, 4)
        ]

        for combination in ok_combinations:
            Variable('a', vartype=combination[0], path_segments=[], location=0,
                     endianness=Endianness.Little, bitoffset=combination[1], bitsize=combination[2])
            Variable('a', vartype=combination[0], path_segments=[], location=0,
                     endianness=Endianness.Big, bitoffset=combination[1], bitsize=combination[2])


if __name__ == '__main__':
    import unittest
    unittest.main()
