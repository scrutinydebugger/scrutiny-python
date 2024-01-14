#    test_firmware_parser.py
#        Test basic capacities to parse a firmware a generate a valid firmware ID
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.core.firmware_parser import FirmwareParser
from test.artifacts import get_artifact
from test import ScrutinyUnitTest


class TestFirmwareParser(ScrutinyUnitTest):
    def test_get_firmwre_id(self):
        with open(get_artifact('demobin_firmwareid')) as f:
            demobin_firmware_id_ascii = f.read()

        parser = FirmwareParser(get_artifact('demobin.elf'))

        self.assertEqual(parser.get_firmware_id_ascii(), demobin_firmware_id_ascii)


if __name__ == '__main__':
    import unittest
    unittest.main()
