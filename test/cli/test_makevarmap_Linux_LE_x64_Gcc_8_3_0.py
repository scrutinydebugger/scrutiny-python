#    test_makevarmap_Linux_LE_x64_Gcc_8_3_0.py
#        Test that we can make a valid VarMap out of a known binary.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import unittest
import subprocess
import json
import os
import sys

from scrutiny.core.varmap import VarMap
from scrutiny.core.basic_types import *
from scrutiny.core.variable import *
from scrutiny.core.bintools.elf_dwarf_var_extractor import ElfDwarfVarExtractor
from scrutiny.core.memory_content import MemoryContent
from scrutiny.exceptions import EnvionmentNotSetUpException
from test import SkipOnException
from test.artifacts import get_artifact


class TestMakeVarMap_LinuxLEx64_Gcc8_3_0(unittest.TestCase):

    bin_filename = get_artifact('testappDebianLEx64_gcc8_3_0')
    memdump_filename = get_artifact('testappDebianLEx64_gcc8_3_0.memdump')

    @classmethod
    def setUpClass(cls):
        cls.init_exception = None
        try:
            extractor = ElfDwarfVarExtractor(cls.bin_filename)
            varmap = extractor.get_varmap()
            cls.varmap = VarMap(varmap.get_json())
            cls.memdump = MemoryContent(cls.memdump_filename)
        except Exception as e:
            cls.init_exception = e  # Let's remember the exception and throw it for each test for good logging.

    @SkipOnException(EnvionmentNotSetUpException)
    def setUp(self) -> None:
        if self.init_exception is not None:
            raise self.init_exception

    def load_var(self, fullname):
        return self.varmap.get_var(fullname)

    def assert_var(self, fullname, thetype, addr=None, bitsize=None, bitoffset=None, value_at_loc=None, float_tol=0.00001):
        v = self.load_var(fullname)
        self.assertEqual(thetype, v.get_type())

        if bitsize is not None:
            self.assertEqual(v.bitsize, bitsize)

        if bitoffset is not None:
            self.assertEqual(v.bitoffset, bitoffset)

        if addr is not None:
            self.assertEqual(addr, v.get_address())

        if value_at_loc is not None:
            data = self.memdump.read(v.get_address(), v.get_size())
            val = v.decode(data)
            if thetype in [EmbeddedDataType.float32, EmbeddedDataType.float64]:
                self.assertAlmostEqual(val, value_at_loc, delta=float_tol)
            else:
                self.assertEqual(val, value_at_loc)
        return v

    def assert_is_enum(self, v):
        self.assertIsNotNone(v.enum)

    def assert_has_enum(self, v, name:str, value:int):
        self.assert_is_enum(v)
        value2 = v.enum.get_value(name)
        self.assertIsNotNone(value2)
        self.assertEqual(value2, value)

    def test_env(self):
        self.assertEqual(self.varmap.endianness, Endianness.Little)

    def test_file1_globals_basic_types(self):
        self.assert_var('/global/file1GlobalChar', EmbeddedDataType.sint8, value_at_loc=-10)
        self.assert_var('/global/file1GlobalInt', EmbeddedDataType.sint32, value_at_loc=-1000)
        self.assert_var('/global/file1GlobalShort', EmbeddedDataType.sint16, value_at_loc=-999)
        self.assert_var('/global/file1GlobalLong', EmbeddedDataType.sint64, value_at_loc=-100000)
        self.assert_var('/global/file1GlobalUnsignedChar', EmbeddedDataType.uint8, value_at_loc=55)
        self.assert_var('/global/file1GlobalUnsignedInt', EmbeddedDataType.uint32, value_at_loc=100001)
        self.assert_var('/global/file1GlobalUnsignedShort', EmbeddedDataType.uint16, value_at_loc=50000)
        self.assert_var('/global/file1GlobalUnsignedLong', EmbeddedDataType.uint64, value_at_loc=100002)
        self.assert_var('/global/file1GlobalFloat', EmbeddedDataType.float32, value_at_loc=3.1415926)
        self.assert_var('/global/file1GlobalDouble', EmbeddedDataType.float64, value_at_loc=1.71)
        self.assert_var('/global/file1GlobalBool', EmbeddedDataType.boolean, value_at_loc=True)

    def test_file2_globals_basic_types(self):
        self.assert_var('/global/file2GlobalChar', EmbeddedDataType.sint8, value_at_loc=20)
        self.assert_var('/global/file2GlobalInt', EmbeddedDataType.sint32, value_at_loc=2000)
        self.assert_var('/global/file2GlobalShort', EmbeddedDataType.sint16, value_at_loc=998)
        self.assert_var('/global/file2GlobalLong', EmbeddedDataType.sint64, value_at_loc=555555)
        self.assert_var('/global/file2GlobalUnsignedChar', EmbeddedDataType.uint8, value_at_loc=254)
        self.assert_var('/global/file2GlobalUnsignedInt', EmbeddedDataType.uint32, value_at_loc=123456)
        self.assert_var('/global/file2GlobalUnsignedShort', EmbeddedDataType.uint16, value_at_loc=12345)
        self.assert_var('/global/file2GlobalUnsignedLong', EmbeddedDataType.uint64, value_at_loc=1234567)
        self.assert_var('/global/file2GlobalFloat', EmbeddedDataType.float32, value_at_loc=0.1)
        self.assert_var('/global/file2GlobalDouble', EmbeddedDataType.float64, value_at_loc=0.11111111111111)
        self.assert_var('/global/file2GlobalBool', EmbeddedDataType.boolean, value_at_loc=False)

    def test_file1_static_basic_types(self):
        self.assert_var('/static/file1.cpp/file1StaticChar', EmbeddedDataType.sint8, value_at_loc=99)
        self.assert_var('/static/file1.cpp/file1StaticInt', EmbeddedDataType.sint32, value_at_loc=987654)
        self.assert_var('/static/file1.cpp/file1StaticShort', EmbeddedDataType.sint16, value_at_loc=-666)
        self.assert_var('/static/file1.cpp/file1StaticLong', EmbeddedDataType.sint64, value_at_loc=-55555)
        self.assert_var('/static/file1.cpp/file1StaticUnsignedChar', EmbeddedDataType.uint8, value_at_loc=44)
        self.assert_var('/static/file1.cpp/file1StaticUnsignedInt', EmbeddedDataType.uint32, value_at_loc=3333)
        self.assert_var('/static/file1.cpp/file1StaticUnsignedShort', EmbeddedDataType.uint16, value_at_loc=22222)
        self.assert_var('/static/file1.cpp/file1StaticUnsignedLong', EmbeddedDataType.uint64, value_at_loc=321321)
        self.assert_var('/static/file1.cpp/file1StaticFloat', EmbeddedDataType.float32, value_at_loc=1.23456789)
        self.assert_var('/static/file1.cpp/file1StaticDouble', EmbeddedDataType.float64, value_at_loc=9.87654321)
        self.assert_var('/static/file1.cpp/file1StaticBool', EmbeddedDataType.boolean, value_at_loc=True)

    def test_file2_static_basic_types(self):
        self.assert_var('/static/file2.cpp/file2StaticChar', EmbeddedDataType.sint8, value_at_loc=-66)
        self.assert_var('/static/file2.cpp/file2StaticInt', EmbeddedDataType.sint32, value_at_loc=-8745)
        self.assert_var('/static/file2.cpp/file2StaticShort', EmbeddedDataType.sint16, value_at_loc=-9876)
        self.assert_var('/static/file2.cpp/file2StaticLong', EmbeddedDataType.sint64, value_at_loc=-12345678)
        self.assert_var('/static/file2.cpp/file2StaticUnsignedChar', EmbeddedDataType.uint8, value_at_loc=12)
        self.assert_var('/static/file2.cpp/file2StaticUnsignedInt', EmbeddedDataType.uint32, value_at_loc=34)
        self.assert_var('/static/file2.cpp/file2StaticUnsignedShort', EmbeddedDataType.uint16, value_at_loc=56)
        self.assert_var('/static/file2.cpp/file2StaticUnsignedLong', EmbeddedDataType.uint64, value_at_loc=78)
        self.assert_var('/static/file2.cpp/file2StaticFloat', EmbeddedDataType.float32, value_at_loc=2.22222)
        self.assert_var('/static/file2.cpp/file2StaticDouble', EmbeddedDataType.float64, value_at_loc=3.3333)
        self.assert_var('/static/file2.cpp/file2StaticBool', EmbeddedDataType.boolean, value_at_loc=True)

    def test_func_static(self):
        self.assert_var('/static/file2.cpp/file2func1()/file2func1Var', EmbeddedDataType.sint32, value_at_loc=-88778877)
        self.assert_var('/static/file2.cpp/file2func1(int)/file2func1Var', EmbeddedDataType.float64, value_at_loc=963258741.123)
        self.assert_var('/static/main.cpp/main/staticIntInMainFunc', EmbeddedDataType.sint32, value_at_loc=22222)
        self.assert_var('/static/main.cpp/mainfunc1()/mainfunc1Var', EmbeddedDataType.sint32, value_at_loc=7777777)
        self.assert_var('/static/main.cpp/mainfunc1(int)/mainfunc1Var', EmbeddedDataType.float64, value_at_loc=8888888.88)
        self.assert_var('/static/file1.cpp/funcInFile1(int, int)/staticLongInFuncFile1', EmbeddedDataType.sint64, value_at_loc=-0x123456789abcdef)

    def test_namespace(self):
        self.assert_var('/global/NamespaceInFile1/NamespaceInFile1Nested1/file1GlobalNestedVar1', EmbeddedDataType.uint64, value_at_loc=1111111111)
        self.assert_var('/static/file1.cpp/NamespaceInFile1/NamespaceInFile1Nested1/file1StaticNestedVar1',
                        EmbeddedDataType.uint64, value_at_loc=945612345)

    def assert_is_enumA(self, fullpath, value_at_loc=None):
        v = self.assert_var(fullpath, EmbeddedDataType.uint32, value_at_loc=value_at_loc)
        self.assert_has_enum(v, 'eVal1', 0)
        self.assert_has_enum(v, 'eVal2', 1)
        self.assert_has_enum(v, 'eVal3', 100)
        self.assert_has_enum(v, 'eVal4', 101)

    def test_enum(self):
        self.assert_is_enumA('/global/NamespaceInFile2/instance_enumA', value_at_loc=1)
        self.assert_is_enumA('/global/instance2_enumA', value_at_loc=101)
        self.assert_is_enumA('/static/file2.cpp/staticInstance2_enumA', value_at_loc=0)
        self.assert_is_enumA('/static/file2.cpp/NamespaceInFile2/staticInstance_enumA', value_at_loc=100)

    def test_structA(self):
        v = self.assert_var('/global/file1StructAInstance/structAMemberInt', EmbeddedDataType.sint32, value_at_loc=-654)
        self.assert_var('/global/file1StructAInstance/structAMemberUInt', EmbeddedDataType.uint32, addr=v.get_address() + 4, value_at_loc=258147)
        self.assert_var('/global/file1StructAInstance/structAMemberFloat', EmbeddedDataType.float32, addr=v.get_address() + 8, value_at_loc=77.77)
        self.assert_var('/global/file1StructAInstance/structAMemberDouble', EmbeddedDataType.float64, addr=v.get_address() + 12, value_at_loc=66.66)
        self.assert_var('/global/file1StructAInstance/structAMemberBool', EmbeddedDataType.boolean, addr=v.get_address() + 20, value_at_loc=False)

    def test_structB(self):
        v = self.assert_var('/global/file1StructBInstance/structBMemberInt', EmbeddedDataType.sint32, value_at_loc=55555)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberInt',
                        EmbeddedDataType.sint32, addr=v.get_address() + 4, value_at_loc=-199999)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberUInt',
                        EmbeddedDataType.uint32, addr=v.get_address() + 8, value_at_loc=33333)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberFloat',
                        EmbeddedDataType.float32, addr=v.get_address() + 12, value_at_loc=33.33)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberDouble',
                        EmbeddedDataType.float64, addr=v.get_address() + 16, value_at_loc=22.22)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberBool',
                        EmbeddedDataType.boolean, addr=v.get_address() + 24, value_at_loc=True)

    def test_structC(self):
        v = self.assert_var('/global/file1StructCInstance/structCMemberInt', EmbeddedDataType.sint32, value_at_loc=888874)
        self.assert_var('/global/file1StructCInstance/nestedStructInstance/nestedStructMemberInt',
                        EmbeddedDataType.sint32, addr=v.get_address() + 4, value_at_loc=2298744)
        self.assert_var('/global/file1StructCInstance/nestedStructInstance/nestedStructMemberFloat',
                        EmbeddedDataType.float32, addr=v.get_address() + 8, value_at_loc=-147.55)
        self.assert_var('/global/file1StructCInstance/nestedStructInstance/nestedStructInstance2/nestedStructInstance2MemberDouble',
                        EmbeddedDataType.float64, addr=v.get_address() + 12, value_at_loc=654.654)

    def test_structD(self):
        v = self.assert_var('/global/file1StructDInstance/bitfieldA', EmbeddedDataType.uint32, bitoffset=0, bitsize=4, value_at_loc=13)
        self.assert_var('/global/file1StructDInstance/bitfieldB', EmbeddedDataType.uint32,
                        bitoffset=4, bitsize=13, value_at_loc=4100, addr=v.get_address())
        self.assert_var('/global/file1StructDInstance/bitfieldC', EmbeddedDataType.uint32,
                        bitoffset=13 + 4, bitsize=8, value_at_loc=222, addr=v.get_address())
        self.assert_var('/global/file1StructDInstance/bitfieldD', EmbeddedDataType.uint32, value_at_loc=1234567, addr=v.get_address() + 4)
        self.assert_var('/global/file1StructDInstance/bitfieldE', EmbeddedDataType.uint32,
                        bitoffset=0, bitsize=10, value_at_loc=777, addr=v.get_address() + 8)

    @unittest.skip("Not implemented yet")
    def test_array1(self):
        self.assert_var('/global/file2GlobalArray1Int5[0]', EmbeddedDataType.sint32, value_at_loc=1111)
        self.assert_var('/global/file2GlobalArray1Int5[1]', EmbeddedDataType.sint32, value_at_loc=2222)
        self.assert_var('/global/file2GlobalArray1Int5[2]', EmbeddedDataType.sint32, value_at_loc=3333)
        self.assert_var('/global/file2GlobalArray1Int5[3]', EmbeddedDataType.sint32, value_at_loc=4444)
        self.assert_var('/global/file2GlobalArray1Int5[4]', EmbeddedDataType.sint32, value_at_loc=5555)

    @unittest.skip("Not implemented yet")
    def test_array_2d(self):
        self.assert_var('/global/file2GlobalArray2x2Float[0]', EmbeddedDataType.float32, value_at_loc=1.1)
        self.assert_var('/global/file2GlobalArray2x2Float[1]', EmbeddedDataType.float32, value_at_loc=2.2)
        self.assert_var('/global/file2GlobalArray2x2Float[2]', EmbeddedDataType.float32, value_at_loc=3.3)
        self.assert_var('/global/file2GlobalArray2x2Float[3]', EmbeddedDataType.float32, value_at_loc=4.4)

    def test_class_file2(self):
        self.assert_var('/global/file2ClassBInstance/intInClassB', EmbeddedDataType.sint32, value_at_loc=-11111)
        self.assert_var('/global/file2ClassBInstance/nestedClassInstance/intInClassBA', EmbeddedDataType.sint32, value_at_loc=-22222)
        self.assert_var('/global/file2ClassBInstance/nestedClassInstance/classAInstance/intInClassA', EmbeddedDataType.sint32, value_at_loc=-33333)

        self.assert_var('/static/file2.cpp/file2ClassBStaticInstance/intInClassB', EmbeddedDataType.sint32, value_at_loc=-44444)
        self.assert_var('/static/file2.cpp/file2ClassBStaticInstance/nestedClassInstance/intInClassBA', EmbeddedDataType.sint32, value_at_loc=-55555)
        self.assert_var('/static/file2.cpp/file2ClassBStaticInstance/nestedClassInstance/classAInstance/intInClassA',
                        EmbeddedDataType.sint32, value_at_loc=-66666)
