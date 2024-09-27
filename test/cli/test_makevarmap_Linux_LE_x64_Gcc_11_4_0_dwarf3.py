#    test_makevarmap_Linux_LE_x64_Gcc_11_4_0_dwarf3.py
#        Test suite for symbol extraction. GCC dwarf V3
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


class TestMakeVarMap_CPP_LinuxLEx64_Gcc11_4_0_Dwarf3(BaseTestAppMakeVarmapTest, ScrutinyUnitTest):
    bin_filename = get_artifact('testapp20240505_UbuntuLEx64_gcc11_4_0-dwarf3')
    memdump_filename = get_artifact('testapp20240505_UbuntuLEx64_gcc11_4_0-dwarf3.memdump')

    def test_dwarf_version(self):
        self.assert_dwarf_version(self.bin_filename, 3)

class TestMakeVarMap_C_LinuxLEx64_Gcc11_4_0_Dwarf3(BaseCTestAppMakeVarmapTest, ScrutinyUnitTest):
    bin_filename = get_artifact('ctestapp20240530_UbuntuLEx64_gcc11_4_0-dwarf3')
    memdump_filename = get_artifact('ctestapp20240530_UbuntuLEx64_gcc11_4_0-dwarf3.memdump')

    def test_dwarf_version(self):
        self.assert_dwarf_version(self.bin_filename, 3)


if __name__ == '__main__':
    import unittest
    unittest.main()
