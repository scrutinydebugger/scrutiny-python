#    test_makevarmap_Linux_LE_x64_Clang_14_0_0.py
#        Test that we can make a valid VarMap out of a known binary.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import unittest
from test.artifacts import get_artifact
from test.cli.base_testapp_makevarmap_test import BaseTestAppMakeVarmapTest
from test import ScrutinyUnitTest


class TestMakeVarMap_LinuxLEx64_Clang_14_0_0(BaseTestAppMakeVarmapTest, ScrutinyUnitTest):
    bin_filename = get_artifact('testapp20240505_UbuntuLEx64_clang14_0_0-dwarf4')
    memdump_filename = get_artifact('testapp20240505_UbuntuLEx64_clang14_0_0-dwarf4.memdump')


if __name__ == '__main__':
    import unittest
    unittest.main()
