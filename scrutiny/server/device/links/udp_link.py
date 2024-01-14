#    udp_link.py
#        Connects the CommHandler to a device through UDP
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import logging
import socket
import errno

from .abstract_link import AbstractLink, LinkConfig

from typing import Optional, TypedDict, cast


class UdpConfig(TypedDict):
    """
    Config given the the UdpLink object.
    Can be set through the API or config file with JSON format
    """
    host: str
    port: int


class UdpLink(AbstractLink):
    """
    Communication channel to talk with a device through a UDP socket
    Based on socket module
    """

    port: int
    host: str
    ip_address: str     # Resolved hostname
    logger: logging.Logger
    sock: Optional[socket.socket]
    bound: bool
    config: UdpConfig
    _initialized: bool

    BUFSIZE: int = 4096

    @classmethod
    def make(cls, config: LinkConfig) -> "UdpLink":
        return cls(config)

    def __init__(self, config: LinkConfig):
        self.validate_config(config)

        self.config = cast(UdpConfig, {
            'host': config['host'],
            'port': int(config['port'])
        })

        self.ip_address = socket.gethostbyname(self.config['host'])  # get the IP of the device

        self.logger = logging.getLogger(self.__class__.__name__)
        self.sock = None            # the socket
        self.bound = False          # True when address is bound
        self._initialized = False

    def get_config(self) -> LinkConfig:
        return cast(LinkConfig, self.config)

    def initialize(self) -> None:
        """Initialize the communication channel. The channel is expected to be usable after this"""
        self.logger.debug('Opening UDP Link. Host=%s (%s). Port=%d' % (self.config['host'], self.ip_address, self.config['port']))
        self.init_socket()
        self._initialized = True

    def init_socket(self) -> None:
        """ Creates the UDP socket and listen on all interfaces"""
        try:
            if self.sock is not None:
                self.sock.close()

            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind(('0.0.0.0', 0))  # 0.0.0.0 listen on all interface.  Port 0 = takes any available
            self.sock.setblocking(False)
            (addr, port) = self.sock.getsockname()  # Read our own address and port, will tell the receiving port auto attributed
            self.logger.debug('Socket bound to address=%s and port=%d' % (addr, port))
            self.bound = True
        except Exception as e:
            self.logger.debug(str(e))
            self.bound = False

    def destroy(self) -> None:
        """ Close the socket and put the comm channel in a non-functional state"""
        self.logger.debug('Closing UDP Link. Host=%s. Port=%d' % (self.config['host'], self.config['port']))

        if self.sock is not None:
            self.sock.close()
        self.sock = None
        self.bound = False
        self._initialized = False

    def operational(self) -> bool:
        """ Tells the upper layer if we are in a working state (to the best of our knowledge)"""
        if self.sock is not None and self.bound == True:    # If bound, we are necessarily initialized
            return True
        return False

    def read(self) -> Optional[bytes]:
        """ Reads bytes Non-Blocking from the comm channel. None if no data available"""
        if not self.operational():
            return None

        try:
            assert self.sock is not None
            err = None
            data, (ip_address, port) = self.sock.recvfrom(self.BUFSIZE)
            if ip_address == self.ip_address and port == self.config['port']:  # Make sure the datagram comes from our target device
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

    def write(self, data: bytes) -> None:
        """ Write data to the comm channel."""
        if not self.operational():
            return
        assert self.sock is not None  # for mypy
        try:
            self.sock.sendto(data, (self.config['host'], self.config['port']))
        except Exception:
            self.bound = False

    def initialized(self) -> bool:
        return self._initialized

    def process(self) -> None:
        """To be called periodically"""
        pass

    @staticmethod
    def validate_config(config: LinkConfig) -> None:
        """Raises an exception if the configuration is not adequate"""
        if not isinstance(config, dict):
            raise ValueError('Configuration is not a valid dictionary')

        if 'host' not in config:
            raise ValueError('Missing hostname')

        if 'port' not in config:
            raise ValueError('Missing hostname')

        port = -1
        try:
            port = int(config['port'])
        except Exception:
            raise ValueError('Port is not a valid integer')

        if port <= 0 or port >= 0x10000:
            raise ValueError('Port number must be a valid 16 bits value')
