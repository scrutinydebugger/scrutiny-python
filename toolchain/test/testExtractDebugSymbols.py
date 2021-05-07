import unittest
import subprocess
import json
import IPython
import os,sys

scrutiny_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.append(scrutiny_folder)

import core

class TestLinuxLEx64_Gcc8_3_0(unittest.TestCase):

    bin_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'files', 'testappDebianLEx64_gcc8_3_0')

    @classmethod
    def setUpClass(cls):
        process = subprocess.Popen('python elf2vardesc.py %s' % cls.bin_filename, stdout=subprocess.PIPE, stdin=subprocess.PIPE, universal_newlines=True)
        cls.vardesc = core.VarDesc(process.communicate(input='')[0])

    def load_var(self, fullname):
        return  self.vardesc.get_var(fullname)

    def assert_vartype(self, fullname, thetype):
        v = self.load_var(fullname)
        self.assertEqual(thetype, v.get_type())

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
        self.assert_vartype('/global/file1GlobalChar', core.VariableType.sint8)
        self.assert_vartype('/global/file1GlobalInt', core.VariableType.sint32)
        self.assert_vartype('/global/file1GlobalShort', core.VariableType.sint16)
        self.assert_vartype('/global/file1GlobalLong', core.VariableType.sint64)
        self.assert_vartype('/global/file1GlobalUnsignedChar', core.VariableType.uint8)
        self.assert_vartype('/global/file1GlobalUnsignedInt', core.VariableType.uint32)
        self.assert_vartype('/global/file1GlobalUnsignedShort', core.VariableType.uint16)
        self.assert_vartype('/global/file1GlobalUnsignedLong', core.VariableType.uint64)
        self.assert_vartype('/global/file1GlobalFloat', core.VariableType.float32)
        self.assert_vartype('/global/file1GlobalDouble', core.VariableType.float64)
        self.assert_vartype('/global/file1GlobalBool', core.VariableType.boolean)

    def test_file1_static_basic_types(self):
        self.assert_vartype('/static/file1.cpp/file1StaticChar', core.VariableType.sint8)
        self.assert_vartype('/static/file1.cpp/file1StaticInt', core.VariableType.sint32)
        self.assert_vartype('/static/file1.cpp/file1StaticShort', core.VariableType.sint16)
        self.assert_vartype('/static/file1.cpp/file1StaticLong', core.VariableType.sint64)
        self.assert_vartype('/static/file1.cpp/file1StaticUnsignedChar', core.VariableType.uint8)
        self.assert_vartype('/static/file1.cpp/file1StaticUnsignedInt', core.VariableType.uint32)
        self.assert_vartype('/static/file1.cpp/file1StaticUnsignedShort', core.VariableType.uint16)
        self.assert_vartype('/static/file1.cpp/file1StaticUnsignedLong', core.VariableType.uint64)
        self.assert_vartype('/static/file1.cpp/file1StaticFloat', core.VariableType.float32)
        self.assert_vartype('/static/file1.cpp/file1StaticDouble', core.VariableType.float64)
        self.assert_vartype('/static/file1.cpp/file1StaticBool', core.VariableType.boolean)

    def test_file2_globals_basic_types(self):
        self.assert_vartype('/global/file2GlobalChar', core.VariableType.sint8)
        self.assert_vartype('/global/file2GlobalInt', core.VariableType.sint32)
        self.assert_vartype('/global/file2GlobalShort', core.VariableType.sint16)
        self.assert_vartype('/global/file2GlobalLong', core.VariableType.sint64)
        self.assert_vartype('/global/file2GlobalUnsignedChar', core.VariableType.uint8)
        self.assert_vartype('/global/file2GlobalUnsignedInt', core.VariableType.uint32)
        self.assert_vartype('/global/file2GlobalUnsignedShort', core.VariableType.uint16)
        self.assert_vartype('/global/file2GlobalUnsignedLong', core.VariableType.uint64)
        self.assert_vartype('/global/file2GlobalFloat', core.VariableType.float32)
        self.assert_vartype('/global/file2GlobalDouble', core.VariableType.float64)
        self.assert_vartype('/global/file2GlobalBool', core.VariableType.boolean)
   
    def test_file2_static_basic_types(self):
        self.assert_vartype('/static/file2.cpp/file2StaticChar', core.VariableType.sint8)
        self.assert_vartype('/static/file2.cpp/file2StaticInt', core.VariableType.sint32)
        self.assert_vartype('/static/file2.cpp/file2StaticShort', core.VariableType.sint16)
        self.assert_vartype('/static/file2.cpp/file2StaticLong', core.VariableType.sint64)
        self.assert_vartype('/static/file2.cpp/file2StaticUnsignedChar', core.VariableType.uint8)
        self.assert_vartype('/static/file2.cpp/file2StaticUnsignedInt', core.VariableType.uint32)
        self.assert_vartype('/static/file2.cpp/file2StaticUnsignedShort', core.VariableType.uint16)
        self.assert_vartype('/static/file2.cpp/file2StaticUnsignedLong', core.VariableType.uint64)
        self.assert_vartype('/static/file2.cpp/file2StaticFloat', core.VariableType.float32)
        self.assert_vartype('/static/file2.cpp/file2StaticDouble', core.VariableType.float64)
        self.assert_vartype('/static/file2.cpp/file2StaticBool', core.VariableType.boolean)        

    def test_func_static(self):
        self.assert_vartype('/static/file2.cpp/file2func1()/file2func1Var', core.VariableType.sint32)
        self.assert_vartype('/static/file2.cpp/file2func1(int)/file2func1Var', core.VariableType.float64)
        self.assert_vartype('/static/main.cpp/main/staticIntInMainFunc', core.VariableType.sint32)
        self.assert_vartype('/static/main.cpp/mainfunc1()/mainfunc1Var', core.VariableType.sint32)
        self.assert_vartype('/static/main.cpp/mainfunc1(int)/mainfunc1Var', core.VariableType.float64)
        self.assert_vartype('/static/file1.cpp/funcInFile1(int, int)/staticLongInFuncFile1', core.VariableType.sint64)

    def test_namespace(self):
        self.assert_vartype('/global/NamespaceInFile1/NamespaceInFile1Nested1/file1GlobalNestedVar1', core.VariableType.uint64)
        self.assert_vartype('/static/file1.cpp/NamespaceInFile1/NamespaceInFile1Nested1/file1StaticNestedVar1', core.VariableType.uint64)

    def test_enum(self):
        v = self.load_var('/global/NamespaceInFile2/instance_enumA')
        self.assert_has_enum(v, 0, 'eVal1')
        self.assert_has_enum(v, 1, 'eVal2')
        self.assert_has_enum(v, 100, 'eVal3')
        self.assert_has_enum(v, 101, 'eVal4')

        v = self.load_var('/global/instance2_enumA')
        self.assert_has_enum(v, 0, 'eVal1')
        self.assert_has_enum(v, 1, 'eVal2')
        self.assert_has_enum(v, 100, 'eVal3')
        self.assert_has_enum(v, 101, 'eVal4')

        v = self.load_var('/static/file2.cpp/instance3_enumA')
        self.assert_has_enum(v, 0, 'eVal1')
        self.assert_has_enum(v, 1, 'eVal2')
        self.assert_has_enum(v, 100, 'eVal3')
        self.assert_has_enum(v, 101, 'eVal4')
