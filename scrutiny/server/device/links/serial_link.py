#    serial_link.py
#        Represent a Serial Link that can be used to communicate with a device
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import logging

from .abstract_link import AbstractLink, LinkConfig

from typing import Optional, Dict, TypedDict, cast, Union
import serial   # type: ignore
import time


class SerialConfig(TypedDict):
    """
    Config given the the SerialLink object.
    Can be set through the API or config file with JSON format
    """
    portname: str
    baudrate: int
    stopbits: str
    databits: int
    parity: str
    start_delay:float



class SerialLink(AbstractLink):
    """
    Communication channel to talk with a device through a serial link
    Based on pyserial module
    """
    logger: logging.Logger
    config: SerialConfig
    _initialized: bool
    _init_timestamp:float

    port: Optional[serial.Serial]

    STR_TO_PARITY: Dict[str, str] = {
        'none': serial.PARITY_NONE,
        'even': serial.PARITY_EVEN,
        'odd': serial.PARITY_ODD,
        'mark': serial.PARITY_MARK,
        'space': serial.PARITY_SPACE
    }

    STR_TO_STOPBITS: Dict[str, float] = {
        'one': serial.STOPBITS_ONE,
        'one_point_five': serial.STOPBITS_ONE_POINT_FIVE,
        'two': serial.STOPBITS_TWO,
        '1': serial.STOPBITS_ONE,
        '1.5': serial.STOPBITS_ONE_POINT_FIVE,
        '2': serial.STOPBITS_TWO
    }

    INT_TO_DATABITS: Dict[int, int] = {
        5: serial.FIVEBITS,
        6: serial.SIXBITS,
        7: serial.SEVENBITS,
        8: serial.EIGHTBITS,
    }

    @classmethod
    def get_parity(cls, s: str) -> str:
        """ Parse a parity string and convert to pyserial constant"""
        s = str(s)
        s = s.strip().lower()
        if s not in cls.STR_TO_PARITY:
            raise ValueError('Unsupported parity "%s"' % s)
        return cls.STR_TO_PARITY[s]

    @classmethod
    def get_stop_bits(cls, s: Union[str, float, int]) -> float:
        """ Convert a stopbit input (str, or number) into a pyserial constant"""
        s = str(s)
        s = s.strip().lower()
        if s not in cls.STR_TO_STOPBITS:
            raise ValueError('Unsupported stop bit string "%s"' % s)
        return cls.STR_TO_STOPBITS[s]

    @classmethod
    def get_data_bits(cls, s: Union[str, int]) -> int:
        """ Converts a data bist input (str or number) to a pyserial constant"""
        try:
            s = int(s)
        except Exception:
            raise ValueError('databits is not a valid integer')

        if s not in cls.INT_TO_DATABITS:
            raise ValueError('Unsupported number of data bits')

        return cls.INT_TO_DATABITS[s]

    @classmethod
    def make(cls, config: LinkConfig) -> "SerialLink":
        """ Return a serialLink instance from a config object"""
        return cls(config)

    def __init__(self, config: LinkConfig):
        self.port = None
        self.validate_config(config)
        self._initialized = False
        self.logger = logging.getLogger(self.__class__.__name__)
        self._init_timestamp = time.monotonic()

        self.config = cast(SerialConfig, {
            'portname': str(config['portname']),
            'baudrate': int(config['baudrate']),
            'stopbits': str(config.get('stopbits', '1')),
            'databits': int(config.get('databits', 8)),
            'parity': str(config.get('parity', 'none')),
            'start_delay' : float(config.get('start_delay', 0))
        })

    def get_config(self) -> LinkConfig:
        return cast(LinkConfig, self.config)

    def initialize(self) -> None:
        """ Called by the device Handler when initiating communication. Should reset the channel to a working state"""
        portname = str(self.config['portname'])
        baudrate = int(self.config['baudrate'])
        stopbits = self.get_stop_bits(self.config['stopbits'])
        databits = self.get_data_bits(self.config['databits'])
        parity = self.get_parity(self.config['parity'])

        self.port = serial.Serial(
            port=portname, 
            baudrate=baudrate, 
            timeout=0, 
            parity=parity, 
            bytesize=databits, 
            stopbits=stopbits, 
            xonxoff=False, 
            rtscts=True, 
            dsrdtr=False
            )
        self.port.reset_input_buffer()      # Clear pending data
        self.port.reset_output_buffer()     # Clear pending data
        self._initialized = True
        self._init_timestamp = time.monotonic()

    def destroy(self) -> None:
        """ Put the comm channel to a resource-free non-working state"""
        if self.port is not None:
            self.port.close()
        self._initialized = False

    def operational(self) -> bool:
        """ Tells if this comm channel is in proper state to be functional"""
        if self.port is None:
            return False
        return self.port.isOpen() and self.initialized()

    def read(self, timeout:Optional[float] = None) -> Optional[bytes]:
        """ Reads bytes in a blocking fashion from the comm channel. None if no data available after timeout"""
        if not self.operational():
            return None
        
        assert self.port is not None    # For mypy
        self.port.timeout = timeout
        data:bytes = self.port.read(max(self.port.in_waiting, 1))
        n = self.port.in_waiting
        if n > 0:
            data += self.port.read(n)
        return data


    def write(self, data: bytes) -> None:
        """ Write data to the comm channel."""
        if self.operational():
            assert self.port is not None    # For mypy
            try:
                self.port.write(data)
                self.port.flush()
            except Exception as e:
                self.logger.debug("Cannot write data. " + str(e))
                self.port.close()

    def initialized(self) -> bool:
        """ Tells if initialize() has been called"""
        return self._initialized and time.monotonic()-self._init_timestamp > self.config['start_delay']

    def process(self) -> None:
        pass

    @staticmethod
    def validate_config(config: LinkConfig) -> None:
        """Raises an exception if the configuration is not adequate"""
        if not isinstance(config, dict):
            raise ValueError('Configuration is not a valid dictionary')

        requried_fields = ['portname', 'baudrate']

        for field in requried_fields:
            if field not in config:
                raise ValueError('Missing ' + field)

        if not isinstance(config['portname'], str):
            raise ValueError('Port name must be a string')

        baudrate = -1
        try:
            baudrate = int(config['baudrate'])
        except Exception:
            raise ValueError('baudrate is not a valid integer')

        if baudrate <= 0:
            raise ValueError('Baudrate  must be a positive integer greater than 0')

        if 'parity' in config:
            SerialLink.get_parity(config['parity'])       # raise an exception on bad value

        if 'stopbits' in config:
            SerialLink.get_stop_bits(config['stopbits'])   # raise an exception on bad value

        if 'databits' in config:
            SerialLink.get_data_bits(config['databits'])   # raise an exception on bad value
