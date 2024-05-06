#    test_makevarmap_Linux_LE_x64_Gcc_8_3_0.py
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


class TestMakeVarMap_LinuxLEx64_Gcc11_4_0(BaseTestAppMakeVarmapTest, ScrutinyUnitTest):
    bin_filename = get_artifact('testapp20240505_UbuntuLEx64_gcc11_4_0-dwarf3')
    memdump_filename = get_artifact('testapp20240505_UbuntuLEx64_gcc11_4_0-dwarf3.memdump')


if __name__ == '__main__':
    import unittest
    unittest.main()
