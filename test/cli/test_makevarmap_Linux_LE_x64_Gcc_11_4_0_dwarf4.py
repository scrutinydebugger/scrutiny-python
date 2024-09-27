#    test_makevarmap_Linux_LE_x64_Gcc_11_4_0_dwarf4.py
#        Test suite for symbol extraction. GCC dwarf V4
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import unittest
from test.artifacts import get_artifact
from test.cli.base_testapp_makevarmap_test import BaseTestAppMakeVarmapTest
from test.cli.base_ctestapp_makevarmap_test import BaseCTestAppMakeVarmapTest
from test import ScrutinyUnitTest


class TestMakeVarMap_CPP_LinuxLEx64_Gcc11_4_0_Dwarf4(BaseTestAppMakeVarmapTest, ScrutinyUnitTest):
    bin_filename = get_artifact('testapp20240505_UbuntuLEx64_gcc11_4_0-dwarf4')
    memdump_filename = get_artifact('testapp20240505_UbuntuLEx64_gcc11_4_0-dwarf4.memdump')

    def test_dwarf_version(self):
        self.assert_dwarf_version(self.bin_filename, 4)

class TestMakeVarMap_C_LinuxLEx64_Gcc11_4_0_Dwarf4(BaseCTestAppMakeVarmapTest, ScrutinyUnitTest):
    bin_filename = get_artifact('ctestapp20240530_UbuntuLEx64_gcc11_4_0-dwarf4')
    memdump_filename = get_artifact('ctestapp20240530_UbuntuLEx64_gcc11_4_0-dwarf4.memdump')

    def test_dwarf_version(self):
        self.assert_dwarf_version(self.bin_filename, 4)


if __name__ == '__main__':
    import unittest
    unittest.main()
