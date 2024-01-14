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


class SerialLink(AbstractLink):
    """
    Communication channel to talk with a device through a serial link
    Based on pyserial module
    """
    logger: logging.Logger
    config: SerialConfig
    _initialized: bool

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

        self.config = cast(SerialConfig, {
            'portname': config['portname'],
            'baudrate': config['baudrate'],
            'stopbits': config['stopbits'] if 'stopbits' in config else "1",
            'databits': config['databits'] if 'databits' in config else 8,
            'parity': config['parity'] if 'parity' in config else 'none',
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

        self.port = serial.Serial(portname, baudrate, timeout=0, parity=parity, bytesize=databits, stopbits=stopbits, xonxoff=False)
        self.port.reset_input_buffer()      # Clear pending data
        self.port.reset_output_buffer()     # Clear pending data
        self._initialized = True

    def destroy(self) -> None:
        """ Put the comm channel to a resource-free non-working state"""
        if self.port is not None:
            self.port.close()
        self._initialized = False

    def operational(self) -> bool:
        """ Tells if this comm channel is in proper state to be functional"""
        if self.port is None:
            return False
        return self.port.isOpen() and self._initialized

    def read(self) -> Optional[bytes]:
        """ Reads bytes Non-Blocking from the comm channel. None if no data available"""
        data: Optional[bytes] = None
        if self.operational():
            assert self.port is not None    # For mypy
            try:
                n = self.port.in_waiting
                if n > 0:
                    data = self.port.read(n)
            except Exception as e:
                self.logger.debug("Cannot read data. " + str(e))
                self.port.close()

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
        return self._initialized

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
