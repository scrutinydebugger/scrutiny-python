#    rtt_link.py
#        Represent a Segger J-Link RTT that can be used to communicate with a device
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import logging

from .abstract_link import AbstractLink, LinkConfig

from typing import Optional, Dict, TypedDict, cast, Union
import pylink   # type: ignore
logging.getLogger("pylink").setLevel(logging.WARNING)

import time


class RttConfig(TypedDict):
    """
    Config given the the RttLink object.
    Can be set through the API or config file with JSON format
    """
    target_device: str
    write_timeout_delay: float
    jlink_interface: str


class RttLink(AbstractLink):
    """
    Communication channel to talk with a device through a J-Link RTT
    Based on pylink module
    """
    logger: logging.Logger
    config: RttConfig
    _initialized: bool

    port: Optional[pylink.JLink]
    
    STR_TO_JLINK_INTERFACE: Dict[str, str] = {
        'jtag' : pylink.enums.JLinkInterfaces.JTAG,
        'swd'  : pylink.enums.JLinkInterfaces.SWD,
        'fine' : pylink.enums.JLinkInterfaces.FINE,
        'icsp' : pylink.enums.JLinkInterfaces.ICSP,
        'spi'  : pylink.enums.JLinkInterfaces.SPI,
        'c2'   : pylink.enums.JLinkInterfaces.C2
    }
    
    @classmethod
    def get_jlink_interface(cls, s: str) -> str:
        " Parse a jlink interface string and convert to JLinkInterfaces constant"
        s = str(s)
        s = s.strip().lower()
        if s not in cls.STR_TO_JLINK_INTERFACE:
            raise ValueError('Unsupported JLinkInterface "%s"' % s)
        return cls.STR_TO_JLINK_INTERFACE[s]
    
    

    @classmethod
    def make(cls, config: LinkConfig) -> "RttLink":
        """ Return a rttLink instance from a config object"""
        return cls(config)

    def __init__(self, config: LinkConfig):
        self.port = None
        self.validate_config(config)
        self._initialized = False
        self.logger = logging.getLogger(self.__class__.__name__)
        

        self.config = cast(RttConfig, {
            'target_device': str(config['target_device']),
            'write_timeout_delay' : float(config.get('write_timeout_delay', 0)),
            'jlink_interface' : str(config.get('jlink_interface','swd'))
        })

    def get_config(self) -> LinkConfig:
        return cast(LinkConfig, self.config)

    def initialize(self) -> None:
        """ Called by the device Handler when initiating communication. Should reset the channel to a working state"""
        target_device = str(self.config['target_device'])
        jlink_interface = self.get_jlink_interface(self.config['jlink_interface'])
        
        self._initialized = False
        self.port = pylink.JLink()

        self.port.open()
        if self.port.opened():
            self.logger.debug("J-Link opened: " + str(self.port.product_name))
        else:
            self.logger.debug("J-Link not opened." )
        self.port.set_tif(jlink_interface)
        self.port.connect(target_device)
        self.port.rtt_start(None)

        if self.port.target_connected():
            self._initialized = True
            self.logger.debug("J-Link connected: " + str(target_device))
        else:
            self.logger.debug("J-Link not connected: " + str(target_device))      

    def destroy(self) -> None:
        """ Put the comm channel to a resource-free non-working state"""
        if self.port is not None:
            if self.port.opened():
                self.port.close()
        self._initialized = False

    def operational(self) -> bool:
        """ Tells if this comm channel is in proper state to be functional"""
        if self.port is None:
            return False
        return self.port.connected() and self.initialized() and self.port.opened() and self.port.target_connected()

    def read(self, timeout:Optional[float] = None) -> Optional[bytes]:
        """ Reads bytes in a blocking fashion from the comm channel. None if no data available after timeout"""
        if not self.operational():
            return None
        
        assert self.port is not None    # For mypy
        data:Optional[bytes] = None
        try:
            bytesArray = self.port.rtt_read(0, 1024)
            data = bytes(bytesArray)
        except Exception:
            self.logger.debug("Cannot read data.")
            self.port.close()
        return data


    def write(self, data: bytes) -> None:
        """ Write data to the comm channel."""
        if self.operational():
            assert self.port is not None    # For mypy
            try:
                total_number_bytes = len(data)
                number_byte_written = 0
                timestamp = time.monotonic()
                timeout = False
                while total_number_bytes > number_byte_written and False == timeout:
                    tmp_number_byte_written = self.port.rtt_write(0, data[number_byte_written:total_number_bytes])
                    number_byte_written = number_byte_written + tmp_number_byte_written
                    if (0 < self.config['write_timeout_delay']) and ((time.monotonic()-timestamp) > self.config['write_timeout_delay']):
                        timeout = True
                        self.logger.error("Write data timeout: " + str((time.monotonic()-timestamp)))
            except Exception as e:
                self.logger.debug("Cannot write data. " + str(e))
                self.port.close()

    def initialized(self) -> bool:
        """ Tells if initialize() has been called"""
        return self._initialized

    def process(self) -> None:
        pass

    @staticmethod
    def validate_config(config: LinkConfig) -> None:
        """Raises an exception if the configuration is not adequate"""
        if not isinstance(config, dict):
            raise ValueError('Configuration is not a valid dictionary')

        requried_fields = ['target_device']

        for field in requried_fields:
            if field not in config:
                raise ValueError('Missing ' + field)

        if not isinstance(config['target_device'], str):
            raise ValueError('Tartget device must be a string')
        
        if 'jlink_interface' in config:
            RttLink.get_jlink_interface(config['jlink_interface'])       # raise an exception on bad value
