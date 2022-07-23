#    test_udp_link.py
#        Test UDP link.
#        nMake the link object talk with a socket
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import unittest
import socket as s

from scrutiny.server.device.links.udp_link import UdpLink
import time


class TestUdpLink(unittest.TestCase):
    PORT = 40555

    def test_read_write(self):
        link_config = {
            'host': 'localhost',
            'port': self.PORT
        }
        try:
            sock = s.socket(s.AF_INET, s.SOCK_DGRAM, s.IPPROTO_UDP)
            sock.bind(('localhost', self.PORT))
            sock.setblocking(False)
        except Exception as e:
            raise unittest.SkipTest("Cannot open test socket. " + str(e))

        link = UdpLink.make(link_config)
        self.assertFalse(link.initialized())
        link.initialize()
        self.assertTrue(link.initialized())
        self.assertTrue(link.operational())

        payload = 'hello'.encode('ascii')
        link.write(payload)
        data, remote_addr = sock.recvfrom(1024)
        self.assertEqual(data, payload)

        payload = 'potato'.encode('ascii')
        link.write(payload)
        sock.sendto(payload, remote_addr)
        data = link.read()
        self.assertEqual(data, payload)

        self.assertTrue(link.operational())

        link.destroy()

        self.assertFalse(link.initialized())
        self.assertFalse(link.operational())

    def test_detect_broken(self):
        link_config = {
            'host': 'localhost',
            'port': self.PORT
        }

        try:
            sock = s.socket(s.AF_INET, s.SOCK_DGRAM, s.IPPROTO_UDP)
            sock.bind(('localhost', self.PORT))
            sock.setblocking(False)
        except Exception as e:
            raise unittest.SkipTest("Cannot open test socket. " + str(e))

        link = UdpLink.make(link_config)
        link.initialize()

        payload = 'hello'.encode('ascii')
        link.write(payload)
        data, remote_addr = sock.recvfrom(1024)
        self.assertEqual(data, payload)

        self.assertTrue(link.operational())
        link.sock.close()   # destroy internal socket to make it fail.
        link.write(payload)  # At least one operation is necessary to detect failure
        self.assertFalse(link.operational())

        link.destroy()
