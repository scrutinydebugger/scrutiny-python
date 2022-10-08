#    test_firmware_parser.py
#        Test basic capacities to parse a firmware a generate a valid firmware ID
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import unittest
from scrutiny.core.firmware_parser import FirmwareParser
from test.artifacts import get_artifact


class TestFirmwareParser(unittest.TestCase):
    def test_get_firmwre_id(self):
        with open(get_artifact('demobin_firmwareid')) as f:
            demobin_firmware_id_ascii = f.read()

        parser = FirmwareParser(get_artifact('demobin.elf'))

        self.assertEqual(parser.get_firmware_id_ascii(), demobin_firmware_id_ascii)