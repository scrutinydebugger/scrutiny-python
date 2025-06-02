#    test_serial_link.py
#        Test serial port link. Require an external serial loopback.
#        Make the link object talk with a serial port.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

import unittest
import traceback

from scrutiny.server.device.links.serial_link import SerialLink
from test import logger
import time
import platform
import serial   # type: ignore
from test import ScrutinyUnitTest


class TestSerialLink(ScrutinyUnitTest):
    WINPORTS = ['COM101', 'COM102']
    NIXPORT = ['/tmp/scrutiny-pty0', '/tmp/scrutiny-pty1']

    def setUp(self):
        if platform.system() == "Windows":
            self.PORT = self.WINPORTS
        else:
            self.PORT = self.NIXPORT

        try:
            tempport = serial.Serial(self.PORT[0])
            tempport.close()
        except Exception as e:
            logger.debug(traceback.format_exc())
            raise unittest.SkipTest("Cannot open serial port %s. %s " % (self.PORT[0], str(e)))

        try:
            port = serial.Serial(self.PORT[1])
        except Exception as e:
            logger.debug(traceback.format_exc())
            raise unittest.SkipTest("Cannot open loopback serial port %s. %s " % (self.PORT[1], str(e)))

    def test_read_write(self):
        baudrate = 115200
        parity = serial.PARITY_NONE
        databits = serial.EIGHTBITS
        stopbits = serial.STOPBITS_ONE

        link_config = {
            'portname': self.PORT[0],
            'baudrate': baudrate,
            'stopbits': 1,
            'databits': 8,
            'parity': 'none'
        }

        port = serial.Serial(self.PORT[1], baudrate, timeout=0, parity=parity, bytesize=databits, stopbits=stopbits, xonxoff=False)

        link = SerialLink.make(link_config)
        self.assertFalse(link.initialized())
        link.initialize()
        self.assertTrue(link.initialized())
        self.assertTrue(link.operational())

        payload = 'hello'.encode('ascii')
        link.write(payload)
        time.sleep(0.05)        # Required for port emulation in user space
        data = port.read(5)
        self.assertEqual(data, payload)

        payload = 'potato'.encode('ascii')
        port.write(payload)
        time.sleep(0.05)        # Required for port emulation in user space
        data = link.read()
        self.assertEqual(data, payload)

        self.assertTrue(link.operational())

        link.destroy()

        self.assertFalse(link.initialized())
        self.assertFalse(link.operational())

    def test_detect_broken(self):
        baudrate = 115200
        parity = serial.PARITY_NONE
        databits = serial.EIGHTBITS
        stopbits = serial.STOPBITS_ONE

        link_config = {
            'portname': self.PORT[0],
            'baudrate': baudrate,
            'stopbits': 1,
            'databits': 8,
            'parity': 'none'
        }

        port = serial.Serial(self.PORT[1], baudrate, timeout=0, parity=parity, bytesize=databits, stopbits=stopbits, xonxoff=False)
        link = SerialLink.make(link_config)
        link.initialize()

        payload = 'hello'.encode('ascii')
        link.write(payload)
        time.sleep(0.05)        # Required for port emulation in user space
        data = port.read(5)
        self.assertEqual(data, payload)

        self.assertTrue(link.operational())
        link.port.close()   # destroy internal socket to make it fail.
        self.assertFalse(link.operational())

        link.destroy()


if __name__ == '__main__':
    import unittest
    unittest.main()
