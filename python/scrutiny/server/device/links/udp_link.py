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

from scrutiny.server.tools import Timer
from .abstract_link import AbstractLink, LinkConfig

from typing import Optional, Dict


class UdpLink(AbstractLink):

    port: int
    host: str
    ip_address: str
    logger: logging.Logger
    sock: Optional[socket.socket]
    bound: bool
    config:Dict

    BUFSIZE: int = 4096

    def __init__(self, parameters: LinkConfig):
        if parameters is None:
            raise ValueError('Empty configuration')

        if 'port' not in parameters:
            raise ValueError('Missing UDP port')

        if 'host' not in parameters:
            raise ValueError('Missing UDP host')

        self.port = int(parameters['port'])
        self.host = parameters['host']

        self.config['host'] = parameters['host']
        self.config['port'] = int(parameters['port'])

        self.ip_address = socket.gethostbyname(self.host)

        self.logger = logging.getLogger(self.__class__.__name__)
        self.sock = None
        self.bound = False

    def get_config(self):
        return self.config


    def initialize(self) -> None:
        self.logger.debug('Opening UDP Link. Host=%s (%s). Port=%d' % (self.host, self.ip_address, self.port))
        self.init_socket()

    def init_socket(self) -> None:
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

    def destroy(self) -> None:
        self.logger.debug('Closing UDP Link. Host=%s. Port=%d' % (self.host, self.port))

        if self.sock is not None:
            self.sock.close()
        self.sock = None
        self.bound = False

    def operational(self) -> bool:
        if self.sock is not None and self.bound == True:
            return True
        return False

    def read(self) -> Optional[bytes]:
        if not self.operational():
            return None

        try:
            assert self.sock is not None
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

        return None

    def write(self, data: bytes):
        if not self.operational():
            return
        assert self.sock is not None  # for mypy
        self.sock.sendto(data, (self.host, self.port))

    def process(self) -> None:
        pass
