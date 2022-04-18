#    udp_link.py
#        Connects the CommHandler to a device through UDP
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import logging
import socket
import threading
import errno
import traceback

from scrutiny.server.server_tools import Timer


class UdpLink:

    BUFSIZE = 4096

    def __init__(self, parameters):
        if 'port' not in parameters:
            raise ValueError('Missing UDP port')

        if 'host' not in parameters:
            raise ValueError('Missing UDP host')

        self.port = int(parameters['port'])
        self.host = parameters['host']
        self.ip_address = socket.gethostbyname(self.host)

        self.logger = logging.getLogger(self.__class__.__name__)
        self.sock = None
        self.bound = False

    def initialize(self):
        self.logger.debug('Opening UDP Link. Host=%s (%s). Port=%d' % (self.host, self.ip_address, self.port))
        self.init_socket()

    def init_socket(self):
        try:
            if self.sock is not None:
                self.sock.close()

            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind(('0.0.0.0', 0))
            self.sock.setblocking(False)
            (addr, port) = self.sock.getsockname()
            self.logger.debug('Socket bound to address=%s and port=%d' % (addr, port))
            self.bound = True
        except Exception as e:
            self.logger.debug(str(e))
            self.bound = False

    def destroy(self):
        self.logger.debug('Closing UDP Link. Host=%s. Port=%d' % (self.host, self.port))

        if self.sock is not None:
            self.sock.close()
        self.sock = None
        self.bound = False

    def operational(self):
        if self.sock is not None and self.bound == True:
            return True
        return false

    def read(self):
        if not self.operational():
            return

        try:
            err = None
            data, (ip_address, port) = self.sock.recvfrom(self.BUFSIZE)
            if ip_address == self.ip_address and port == self.port:  # Make sure the datagram comes from our target host
                return data
        except socket.error as e:
            err = e
            if e.args[0] == errno.EAGAIN or e.args[0] == errno.EWOULDBLOCK:
                err = None

        if err:
            self.logger.debug('Socket error : ' + str(err))

    def write(self, data):
        if not self.operational():
            return

        self.sock.sendto(data, (self.host, self.port))

    def process(self):
        pass
