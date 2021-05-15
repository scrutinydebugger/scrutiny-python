import unittest
import subprocess
import json
import IPython
import os,sys
from .memdump import Memdump

scrutiny_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.append(scrutiny_folder)

import core

class TestLinuxLEx64_Gcc8_3_0(unittest.TestCase):

    bin_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'files', 'testappDebianLEx64_gcc8_3_0')
    memdump_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'files', 'testappDebianLEx64_gcc8_3_0.memdump')

    @classmethod
    def setUpClass(cls):
        process = subprocess.Popen('python elf2vardesc.py %s' % cls.bin_filename, stdout=subprocess.PIPE, stdin=subprocess.PIPE, universal_newlines=True)
        cls.vardesc = core.VarDesc(process.communicate(input='')[0])
        cls.memdump = Memdump(cls.memdump_filename)

    def load_var(self, fullname):
        return  self.vardesc.get_var(fullname)

    def assert_var(self, fullname, thetype, bitsize=None, bitoffset=None, value_at_loc=None, float_tol=0.00001):
        v = self.load_var(fullname)
        self.assertEqual(thetype, v.get_type())
        
        if bitsize is not None:
           self.assertEqual(v.bitsize, bitsize) 

        if bitoffset is not None:
           self.assertEqual(v.bitoffset, bitoffset) 

        if value_at_loc is not None:
            data = self.memdump.read(v.get_address(), v.get_size())
            val = v.decode(data)
            if thetype in [core.VariableType.float32, core.VariableType.float64]:
                self.assertAlmostEqual(val, value_at_loc, delta=float_tol)
            else:
                self.assertEqual(val, value_at_loc)

    def assert_is_enum(self, v):
        self.assertIsNotNone(v.enum)

    def assert_has_enum(self, v, value, name):
        self.assert_is_enum(v)
        valname = v.enum.get_name(value)
        self.assertIsNotNone(valname)
        self.assertEqual(name, valname)

    def test_env(self):
        self.assertEqual(self.vardesc.endianness, 'little')

    def test_file1_globals_basic_types(self):
        self.assert_var('/global/file1GlobalChar', core.VariableType.sint8, value_at_loc =  -10)
        self.assert_var('/global/file1GlobalInt', core.VariableType.sint32, value_at_loc =  -1000)
        self.assert_var('/global/file1GlobalShort', core.VariableType.sint16, value_at_loc =  -999)
        self.assert_var('/global/file1GlobalLong', core.VariableType.sint64, value_at_loc =  -100000)
        self.assert_var('/global/file1GlobalUnsignedChar', core.VariableType.uint8, value_at_loc =  55)
        self.assert_var('/global/file1GlobalUnsignedInt', core.VariableType.uint32, value_at_loc =  100001)
        self.assert_var('/global/file1GlobalUnsignedShort', core.VariableType.uint16, value_at_loc =  50000)
        self.assert_var('/global/file1GlobalUnsignedLong', core.VariableType.uint64, value_at_loc =  100002)
        self.assert_var('/global/file1GlobalFloat', core.VariableType.float32, value_at_loc =  3.1415926)
        self.assert_var('/global/file1GlobalDouble', core.VariableType.float64, value_at_loc =  1.71)
        self.assert_var('/global/file1GlobalBool', core.VariableType.boolean, value_at_loc =  True)

    def test_file2_globals_basic_types(self):
        self.assert_var('/global/file2GlobalChar', core.VariableType.sint8, value_at_loc = 20)
        self.assert_var('/global/file2GlobalInt', core.VariableType.sint32, value_at_loc =  2000)
        self.assert_var('/global/file2GlobalShort', core.VariableType.sint16, value_at_loc =  998)
        self.assert_var('/global/file2GlobalLong', core.VariableType.sint64, value_at_loc =  555555)
        self.assert_var('/global/file2GlobalUnsignedChar', core.VariableType.uint8, value_at_loc =  254)
        self.assert_var('/global/file2GlobalUnsignedInt', core.VariableType.uint32, value_at_loc =  123456)
        self.assert_var('/global/file2GlobalUnsignedShort', core.VariableType.uint16, value_at_loc =  12345)
        self.assert_var('/global/file2GlobalUnsignedLong', core.VariableType.uint64, value_at_loc =  1234567)
        self.assert_var('/global/file2GlobalFloat', core.VariableType.float32, value_at_loc =  0.1)
        self.assert_var('/global/file2GlobalDouble', core.VariableType.float64, value_at_loc =  0.11111111111111)
        self.assert_var('/global/file2GlobalBool', core.VariableType.boolean, value_at_loc =  False)
   
    def test_file1_static_basic_types(self):
        self.assert_var('/static/file1.cpp/file1StaticChar', core.VariableType.sint8, value_at_loc = 99)
        self.assert_var('/static/file1.cpp/file1StaticInt', core.VariableType.sint32, value_at_loc = 987654)
        self.assert_var('/static/file1.cpp/file1StaticShort', core.VariableType.sint16, value_at_loc = -666)
        self.assert_var('/static/file1.cpp/file1StaticLong', core.VariableType.sint64, value_at_loc = -55555)
        self.assert_var('/static/file1.cpp/file1StaticUnsignedChar', core.VariableType.uint8, value_at_loc = 44)
        self.assert_var('/static/file1.cpp/file1StaticUnsignedInt', core.VariableType.uint32, value_at_loc = 3333)
        self.assert_var('/static/file1.cpp/file1StaticUnsignedShort', core.VariableType.uint16, value_at_loc = 22222)
        self.assert_var('/static/file1.cpp/file1StaticUnsignedLong', core.VariableType.uint64, value_at_loc = 321321)
        self.assert_var('/static/file1.cpp/file1StaticFloat', core.VariableType.float32, value_at_loc = 1.23456789)
        self.assert_var('/static/file1.cpp/file1StaticDouble', core.VariableType.float64, value_at_loc = 9.87654321)
        self.assert_var('/static/file1.cpp/file1StaticBool', core.VariableType.boolean, value_at_loc = True)

    def test_file2_static_basic_types(self):
        self.assert_var('/static/file2.cpp/file2StaticChar', core.VariableType.sint8, value_at_loc =  -66)
        self.assert_var('/static/file2.cpp/file2StaticInt', core.VariableType.sint32, value_at_loc =  -8745)
        self.assert_var('/static/file2.cpp/file2StaticShort', core.VariableType.sint16, value_at_loc =  -9876)
        self.assert_var('/static/file2.cpp/file2StaticLong', core.VariableType.sint64, value_at_loc =  -12345678)
        self.assert_var('/static/file2.cpp/file2StaticUnsignedChar', core.VariableType.uint8, value_at_loc =  12)
        self.assert_var('/static/file2.cpp/file2StaticUnsignedInt', core.VariableType.uint32, value_at_loc =  34)
        self.assert_var('/static/file2.cpp/file2StaticUnsignedShort', core.VariableType.uint16, value_at_loc =  56)
        self.assert_var('/static/file2.cpp/file2StaticUnsignedLong', core.VariableType.uint64, value_at_loc =  78)
        self.assert_var('/static/file2.cpp/file2StaticFloat', core.VariableType.float32, value_at_loc =  2.22222)
        self.assert_var('/static/file2.cpp/file2StaticDouble', core.VariableType.float64, value_at_loc =  3.3333)
        self.assert_var('/static/file2.cpp/file2StaticBool', core.VariableType.boolean, value_at_loc =  True)        

    def test_func_static(self):
        self.assert_var('/static/file2.cpp/file2func1()/file2func1Var', core.VariableType.sint32)
        self.assert_var('/static/file2.cpp/file2func1(int)/file2func1Var', core.VariableType.float64)
        self.assert_var('/static/main.cpp/main/staticIntInMainFunc', core.VariableType.sint32)
        self.assert_var('/static/main.cpp/mainfunc1()/mainfunc1Var', core.VariableType.sint32)
        self.assert_var('/static/main.cpp/mainfunc1(int)/mainfunc1Var', core.VariableType.float64)
        self.assert_var('/static/file1.cpp/funcInFile1(int, int)/staticLongInFuncFile1', core.VariableType.sint64)

    def test_namespace(self):
        self.assert_var('/global/NamespaceInFile1/NamespaceInFile1Nested1/file1GlobalNestedVar1', core.VariableType.uint64)
        self.assert_var('/static/file1.cpp/NamespaceInFile1/NamespaceInFile1Nested1/file1StaticNestedVar1', core.VariableType.uint64)

    def test_enum(self):
        self.assert_var('/global/NamespaceInFile2/instance_enumA', core.VariableType.uint32)
        v = self.load_var('/global/NamespaceInFile2/instance_enumA')
        self.assert_has_enum(v, 0, 'eVal1')
        self.assert_has_enum(v, 1, 'eVal2')
        self.assert_has_enum(v, 100, 'eVal3')
        self.assert_has_enum(v, 101, 'eVal4')

        self.assert_var('/global/instance2_enumA', core.VariableType.uint32)
        v = self.load_var('/global/instance2_enumA')
        self.assert_has_enum(v, 0, 'eVal1')
        self.assert_has_enum(v, 1, 'eVal2')
        self.assert_has_enum(v, 100, 'eVal3')
        self.assert_has_enum(v, 101, 'eVal4')

        self.assert_var('/static/file2.cpp/staticInstance2_enumA', core.VariableType.uint32)
        v = self.load_var('/static/file2.cpp/staticInstance2_enumA')
        self.assert_has_enum(v, 0, 'eVal1')
        self.assert_has_enum(v, 1, 'eVal2')
        self.assert_has_enum(v, 100, 'eVal3')
        self.assert_has_enum(v, 101, 'eVal4')

        self.assert_var('/static/file2.cpp/NamespaceInFile2/staticInstance_enumA', core.VariableType.uint32)
        v = self.load_var('/static/file2.cpp/NamespaceInFile2/staticInstance_enumA')
        self.assert_has_enum(v, 0, 'eVal1')
        self.assert_has_enum(v, 1, 'eVal2')
        self.assert_has_enum(v, 100, 'eVal3')
        self.assert_has_enum(v, 101, 'eVal4')

    def test_struct(self):
        self.assert_var('/global/file1StructAInstance/structAMemberInt', core.VariableType.sint32, bitoffset=0)
        self.assert_var('/global/file1StructAInstance/structAMemberUInt', core.VariableType.uint32, bitoffset=32)
        self.assert_var('/global/file1StructAInstance/structAMemberFloat', core.VariableType.float32, bitoffset=64)
        self.assert_var('/global/file1StructAInstance/structAMemberDouble', core.VariableType.float64, bitoffset=96)
        self.assert_var('/global/file1StructAInstance/structAMemberBool', core.VariableType.boolean, bitoffset=160)

        self.assert_var('/global/file1StructBInstance/structBMemberInt', core.VariableType.sint32, bitoffset=0)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberInt', core.VariableType.sint32, bitoffset=0+32)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberUInt', core.VariableType.uint32, bitoffset=32+32)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberFloat', core.VariableType.float32, bitoffset=64+32)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberDouble', core.VariableType.float64, bitoffset=96+32)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberBool', core.VariableType.boolean, bitoffset=160+32)

    def test_bitfield(self):
        self.assert_var('/global/file1StructDInstance/bitfieldA', core.VariableType.uint32, bitoffset=0, bitsize=1)
        self.assert_var('/global/file1StructDInstance/bitfieldB', core.VariableType.uint32, bitoffset=1, bitsize=9)
        self.assert_var('/global/file1StructDInstance/bitfieldC', core.VariableType.uint32, bitoffset=10, bitsize=3)
        self.assert_var('/global/file1StructDInstance/bitfieldD', core.VariableType.uint32, bitoffset=16, bitsize=None)
