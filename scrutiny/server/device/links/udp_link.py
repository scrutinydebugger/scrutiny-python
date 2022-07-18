#    udp_link.py
#        Connects the CommHandler to a device through UDP
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import logging
import socket
import threading
import errno
import traceback

from scrutiny.server.tools import Timer
from .abstract_link import AbstractLink, LinkConfig

from typing import Optional, Dict, TypedDict, cast

class UdpConfig(TypedDict):
    host:str
    port:int

class UdpLink(AbstractLink):

    port: int
    host: str
    ip_address: str
    logger: logging.Logger
    sock: Optional[socket.socket]
    bound: bool
    config: UdpConfig
    _initialized:bool

    BUFSIZE: int = 4096

    def __init__(self, config: LinkConfig):
        self.validate_config(config)
        
        self.config = cast(UdpConfig, {
            'host': config['host'],
            'port': int(config['port'])
        })

        self.ip_address = socket.gethostbyname(self.config['host'])

        self.logger = logging.getLogger(self.__class__.__name__)
        self.sock = None
        self.bound = False
        self._initialized = False

    def get_config(self):
        return cast(LinkConfig, self.config)

    def initialize(self) -> None:
        self.logger.debug('Opening UDP Link. Host=%s (%s). Port=%d' % (self.config['host'], self.ip_address, self.config['port']))
        self.init_socket()
        self._initialized = True

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
        self.logger.debug('Closing UDP Link. Host=%s. Port=%d' % (self.config['host'], self.config['port']))

        if self.sock is not None:
            self.sock.close()
        self.sock = None
        self.bound = False
        self._initialized = False

    def operational(self) -> bool:
        # If bound, we are necessarily initialized
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
            if ip_address == self.ip_address and port == self.config['port']:  # Make sure the datagram comes from our target host
                return data
        except socket.error as e:
            err = e
            if e.args[0] == errno.EAGAIN or e.args[0] == errno.EWOULDBLOCK:
                err = None

        if err:
            self.logger.debug('Socket error : ' + str(err))
            if self.sock is not None:
                self.sock.close()

        return None

    def write(self, data: bytes):
        if not self.operational():
            return
        assert self.sock is not None  # for mypy
        try:
            self.sock.sendto(data, (self.config['host'], self.config['port']))
        except:
            self.bound = False

    def initialized(self) -> bool:
        return self._initialized

    def process(self) -> None:
        pass
    
    @staticmethod
    def validate_config(config:LinkConfig) -> None:
        if not isinstance(config, dict):
            raise ValueError('Configuration is not a valid dictionary')

        if 'host' not in config:
            raise ValueError('Missing hostname')
        
        if 'port' not in config:
            raise ValueError('Missing hostname')

        port = -1
        try:
            port = int(config[port])
        except:
            raise ValueError('Port is not a valid integer')
        
        if port <= 0 or port >= 0x10000:
            raise ValueError('Port number must be a valid 16 bits value')


