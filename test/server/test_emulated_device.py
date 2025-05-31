#    test_emulated_device.py
#        Some testcases to make sure the emulated device runs correctly
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.server.device.emulated_device import EmulatedDevice, DataloggerEmulator
import scrutiny.server.datalogging.definitions.device as device_datalogging
from scrutiny.server.datalogging.datalogging_utilities import extract_signal_from_data
from scrutiny.server.device.links.dummy_link import DummyLink
from scrutiny.core.codecs import Codecs
from scrutiny.core.basic_types import *
from test import ScrutinyUnitTest
from dataclasses import dataclass
import time
import struct

from typing import List


class TestEmulatedDevice(ScrutinyUnitTest):
    emulated_device: EmulatedDevice

    def setUp(self):
        self.link = DummyLink()
        self.emulated_device = EmulatedDevice(self.link)
        self.emulated_device.start()

    def test_read_write_rpv(self):
        self.emulated_device.write_rpv(0x1000, 1.123)
        val = self.emulated_device.read_rpv(0x1000)
        self.assertEqual(val, 1.123)

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


class TestEmulatedDatalogger(ScrutinyUnitTest):
    @dataclass
    class ValuesForTest:
        v100000_f64: float
        v200000_u32: int
        rpv1000: float

    def setUp(self):
        self.link = DummyLink()
        self.emulated_device = EmulatedDevice(self.link)
        self.datalogger = DataloggerEmulator(self.emulated_device, buffer_size=256)
        self.emulated_device.start()
        self.vals = self.ValuesForTest(0, 0, 0)
        self.write_vals()

    def write_vals(self):
        self.emulated_device.write_memory(0x100000, Codecs.get(EmbeddedDataType.float64, Endianness.Little).encode(self.vals.v100000_f64))
        self.emulated_device.write_memory(0x200000, Codecs.get(EmbeddedDataType.uint32, Endianness.Little).encode(self.vals.v200000_u32))
        self.emulated_device.write_rpv(0x1000, self.vals.rpv1000)

    def read_vals(self):
        self.vals.v100000_f64 = Codecs.get(EmbeddedDataType.float64, Endianness.Little).decode(self.emulated_device.read_memory(0x100000))
        self.vals.v200000_u32 = Codecs.get(EmbeddedDataType.uint32, Endianness.Little).decode(self.emulated_device.read_memory(0x200000))
        self.vals.rpv1000 = self.emulated_device.read_rpv(0x1000)

    def test_basics(self):
        config = device_datalogging.Configuration()
        config.decimation = 2
        config.probe_location = 0.5
        config.trigger_hold_time = 0.1
        config.timeout = 2
        config.add_signal(device_datalogging.TimeLoggableSignal())
        config.add_signal(device_datalogging.MemoryLoggableSignal(0x200000, 4))    # uint32
        config.add_signal(device_datalogging.RPVLoggableSignal(rpv_id=0x1000))     # float64
        config.trigger_condition.condition_id = device_datalogging.TriggerConditionID.Equal
        config.trigger_condition.operands.append(device_datalogging.VarOperand(0x100000, EmbeddedDataType.float64))    # float64
        config.trigger_condition.operands.append(device_datalogging.RPVOperand(0x1000))    # float64
        config._trigger_hold_time = 0.1

        # BAsic state check
        self.assertEqual(self.datalogger.state, device_datalogging.DataloggerState.IDLE)
        self.datalogger.configure(config_id=0x1234, config=config)
        self.assertEqual(self.datalogger.state, device_datalogging.DataloggerState.CONFIGURED)
        self.datalogger.arm_trigger()
        self.assertEqual(self.datalogger.state, device_datalogging.DataloggerState.ARMED)
        self.datalogger.disarm_trigger()
        self.assertEqual(self.datalogger.state, device_datalogging.DataloggerState.CONFIGURED)

        # Innit the data and start processing for an aquisition
        self.vals.v100000_f64 = 0
        self.vals.rpv1000 = 0
        self.datalogger.process()
        time.sleep(0.1)
        self.datalogger.process()
        self.assertFalse(self.datalogger.triggered())
        # Will fill the buffer, but nothing triggered
        for i in range(20):
            self.datalogger.process()
            time.sleep(0.001)

        self.assertFalse(self.datalogger.triggered())
        self.datalogger.arm_trigger()
        # Trigger armed, but still not triggered
        for i in range(100):
            self.vals.v100000_f64 += 1.0
            self.vals.v200000_u32 += 1
            self.vals.rpv1000 -= 1.0
            self.write_vals()
            self.datalogger.process()
            time.sleep(0.001)
        self.assertFalse(self.datalogger.triggered())

        # Trigger condition will be true. Will need to stay like that for 100msec to get a trigger
        self.vals.v100000_f64 = 100
        self.vals.rpv1000 = 100

        self.vals.v200000_u32 = 200
        self.write_vals()
        self.datalogger.process()
        time.sleep(0.001)
        self.assertFalse(self.datalogger.triggered())   # False because hold time is not met
        time.sleep(config.trigger_hold_time + 0.05)
        self.datalogger.process()   # Now it will see that the hold time has elapsed and trigger will be considered fulfiled
        time.sleep(0.001)
        self.assertTrue(self.datalogger.triggered())
        self.assertEqual(self.datalogger.state, device_datalogging.DataloggerState.TRIGGERED)

        # Keep processing for a while so we make sure that it stopped at the right moment (depends on probe location)
        for i in range(100):
            self.vals.v100000_f64 += 1.0
            self.vals.v200000_u32 += 1
            self.vals.rpv1000 -= 1.0
            self.write_vals()
            self.datalogger.process()
            time.sleep(0.001)

        self.assertEqual(self.datalogger.state, device_datalogging.DataloggerState.ACQUISITION_COMPLETED)
        acquisition_data = self.datalogger.get_acquisition_data()
        rpv_map = self.emulated_device.get_rpv_definition_map()

        raw_encoding_block_size = 16
        nsamples = self.datalogger.buffer_size // raw_encoding_block_size

        data_inflated = extract_signal_from_data(
            data=acquisition_data,
            config=self.datalogger.config,
            rpv_map=rpv_map,
            encoding=device_datalogging.Encoding.RAW)

        self.assertEqual(len(data_inflated), 3)  # 3 signals
        for i in range(len(data_inflated)):
            self.assertEqual(len(data_inflated[i]), nsamples)

        data_interpreted: List[List[float]] = [[], [], []]
        for j in range(nsamples):
            data_interpreted[0].append(struct.unpack('>L', data_inflated[0][j])[0])  # Time is always BE
            data_interpreted[1].append(struct.unpack('<L', data_inflated[1][j])[0])  # Raw memory content depends on device, Little Endian on emulated
            data_interpreted[2].append(struct.unpack('>d', data_inflated[2][j])[0])  # RPV are always BE

        # We validate the probe location here.  It was at 0.5, should be in the middle.  Might have some rounding problem here... to be fixed whenever it breaks.
        self.assertEqual(data_interpreted[1][nsamples // 2 - 1], 200)   # Trigger Values
        self.assertEqual(data_interpreted[2][nsamples // 2 - 1], 100)

        self.assertGreater(nsamples, 1)
        for j in range(1, nsamples):
            dt = (data_interpreted[0][j] - data_interpreted[0][j - 1]) & 0xFFFFFFFF
            self.assertGreaterEqual(dt, 10000, f"j={j}")  # Delta should always be greater than 1msec because there are sleeps after each process call

            dv1 = data_interpreted[1][j] - data_interpreted[1][j - 1]
            dv2 = data_interpreted[2][j] - data_interpreted[2][j - 1]

            if (data_interpreted[1][j] != 200):  # Avoid the discontinuity
                if data_interpreted[1][j - 1] == 200:
                    self.assertLessEqual(dv1, 1 * config.decimation, "j=%d" % j)
                else:
                    self.assertEqual(dv1, 1 * config.decimation, "j=%d" % j)

            if (data_interpreted[2][j] != 100):  # Avoid the discontinuity
                if data_interpreted[2][j - 1] == 100:
                    self.assertGreaterEqual(dv1, -1 * config.decimation, "j=%d" % j)
                else:
                    self.assertEqual(dv2, -1 * config.decimation, "j=%d" % j)   # RPV 1000 does steps of -1

    def tearDown(self):
        self.emulated_device.stop()


if __name__ == '__main__':
    import unittest
    unittest.main()
