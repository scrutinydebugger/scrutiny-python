import unittest
from scrutiny.core.firmware_parser import FirmwareParser
from test.artifacts import get_artifact

class TestFirmwareParser(unittest.TestCase):
    def test_get_firmwre_id(self):
        with open(get_artifact('demobin_firmwareid')) as f:
            demobin_firmware_id_ascii = f.read()

        parser = FirmwareParser(get_artifact('demobin.elf'))

        self.assertEqual(parser.get_firmware_id_ascii(), demobin_firmware_id_ascii)
