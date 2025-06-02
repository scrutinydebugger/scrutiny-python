#    rtt_link.py
#        Represent a Segger J-Link RTT that can be used to communicate with a device
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = [
    'RttConfig',
    'RttLink'
]

import logging
import threading
import queue

import pylink   # type: ignore
logging.getLogger("pylink").setLevel(logging.WARNING)

from scrutiny.server.device.links.abstract_link import AbstractLink, LinkConfig
from scrutiny.tools.typing import *

# Hook for unit tests.
# Allow to change the Jlink class with a stub
class ClassContainer:
    theclass:Type[Any]
    def __init__(self, o:Type[Any]):
        self.theclass = o
    
    def __call__(self) -> Any:
        return self.theclass()
    
JLINK_CLASS = ClassContainer(pylink.JLink)   

def _set_jlink_class(c):  # type:ignore
    JLINK_CLASS.theclass = c

def _get_jlink_class():  # type:ignore
    return JLINK_CLASS.theclass

class RttConfig(TypedDict):
    """
    Config given the the RttLink object.
    Can be set through the API or config file with JSON format
    """
    target_device: str
    jlink_interface: str


class RttLink(AbstractLink):
    """
    Communication channel to talk with a device through a J-Link RTT
    Based on pylink module
    """
    logger: logging.Logger
    config: RttConfig
    _initialized: bool
    _write_queue:"queue.Queue[Optional[bytes]]" # None is used to wake up the thread
    _write_thread:Optional[threading.Thread]
    _request_thread_exit:bool

    port: Optional[pylink.JLink]
    
    STR_TO_JLINK_INTERFACE: Dict[str, int] = {
        'jtag' : pylink.enums.JLinkInterfaces.JTAG,
        'swd'  : pylink.enums.JLinkInterfaces.SWD,
        'fine' : pylink.enums.JLinkInterfaces.FINE,
        'icsp' : pylink.enums.JLinkInterfaces.ICSP,
        'spi'  : pylink.enums.JLinkInterfaces.SPI,
        'c2'   : pylink.enums.JLinkInterfaces.C2
    }
    
    @classmethod
    def get_jlink_interface(cls, s: str) -> int:
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
        self._write_thread = None
        self._write_queue = queue.Queue()
        self._request_thread_exit = False
        

        self.config = cast(RttConfig, {
            'target_device': str(config['target_device']),
            'jlink_interface' : str(config.get('jlink_interface','swd'))
        })

    def get_config(self) -> LinkConfig:
        return cast(LinkConfig, self.config)

    def initialize(self) -> None:
        """ Called by the device Handler when initiating communication. Should reset the channel to a working state"""
        target_device = str(self.config['target_device'])
        jlink_interface = self.get_jlink_interface(self.config['jlink_interface'])
        if self._write_thread is not None:
            raise RuntimeError("Thread already running")
        
        self._initialized = False
        self._write_queue = queue.Queue()   # clear
        self._request_thread_exit = False
        self._write_thread = threading.Thread(target=self._write_thread_func, daemon=True)
        self.port = JLINK_CLASS()

        self.port.open()
        if self.port.opened():
            self.logger.debug("J-Link opened: " + str(self.port.product_name))
        else:
            self.logger.debug("J-Link not opened." )
        self.port.set_tif(jlink_interface)
        self.port.connect(target_device)
        self.port.rtt_start(None)

        if self.port.target_connected():
            self._write_thread.start()

            self._initialized = True
            self.logger.debug("J-Link connected: " + str(target_device))
        else:
            self.logger.debug("J-Link not connected: " + str(target_device))     


    def _write_thread_func(self) -> None:
        assert self.port is not None
        while not self._request_thread_exit:
            data = self._write_queue.get()
            if data is not None:
                while len(data) > 0:
                    written_count = cast(int, self.port.rtt_write(0, data))
                    data = data[written_count:]
            else:
                pass # Other thread wanted to wake us up. Do nothing, we should exit


    def destroy(self) -> None:
        """ Put the comm channel to a resource-free non-working state"""
        if self.port is not None:
            if self.port.opened():
                self.port.close()

        self._request_thread_exit = True
        self._write_queue.put(None) # Will wake the thread
        if self._write_thread is not None:
            if self._write_thread.is_alive():
                self._write_thread.join(2)
        
        self._write_queue = queue.Queue()
        self._write_thread = None

        self._initialized = False

    def operational(self) -> bool:
        """ Tells if this comm channel is in proper state to be functional"""
        if self.port is None:
            return False
        
        return (
            self.port.connected() 
            and self.initialized() 
            and self.port.opened() 
            and self.port.target_connected() 
            and self._write_thread is not None 
            and self._write_thread.is_alive()
        )

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
            assert self.port is not None
            try:
                self._write_queue.put(data)
            except queue.Full:
                self.logger.debug("Write queue is full.")
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
