#    test_emulated_device.py
#        Some testcases to make sure the emulated device runs correctly
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

from scrutiny.server.device.emulated_device import EmulatedDevice
from scrutiny.server.device.links.dummy_link import DummyLink
from test import ScrutinyUnitTest


class TestEmulatedDevice(ScrutinyUnitTest):
    emulated_device: EmulatedDevice

    def setUp(self):
        self.link = DummyLink()
        self.emulated_device = EmulatedDevice(self.link)
        self.emulated_device.start()

    def test_read_write_memory(self):
        self.emulated_device.write_memory(0x1000, 'hello world'.encode('utf8'))
        data = self.emulated_device.read_memory(0x1000, 11)
        self.assertEqual(data.decode('utf8'), 'hello world')

    def test_write_masked(self):
        self.emulated_device.write_memory(0x1000, bytearray([0x55, 0x55, 0x55, 0x55]))
        self.assertEqual(self.emulated_device.read_memory(0x1000, 4), bytearray([0x55, 0x55, 0x55, 0x55]))
        self.emulated_device.write_memory_masked(0x1000, bytearray([0xFF, 0xFF, 0xAA, 0xAA]), bytearray([0xAA, 0x55, 0xFF, 0x55]))
        self.assertEqual(self.emulated_device.read_memory(0x1000, 4), bytearray([0xFF, 0x55, 0xAA, 0x00]))

        initial_data = bytearray([0, 0])
        data = bytearray([0xA5, 0xA5])
        mask = bytearray([0x0F, 0xF0])
        self.emulated_device.write_memory(0x2000, initial_data)
        self.emulated_device.write_memory_masked(0x2000, data, mask)
        self.assertEqual(self.emulated_device.read_memory(0x2000, 2), bytearray([0x05, 0xA0]))

        initial_data = bytearray([0xFF, 0xFF])
        data = bytearray([0xA5, 0xA5])
        mask = bytearray([0x0F, 0xF0])
        self.emulated_device.write_memory(0x2000, initial_data)
        self.emulated_device.write_memory_masked(0x2000, data, mask)
        self.assertEqual(self.emulated_device.read_memory(0x2000, 2), bytearray([0xF5, 0xAF]))

    def tearDown(self):
        self.emulated_device.stop()
