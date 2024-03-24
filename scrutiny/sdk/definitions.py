#    definitions.py
#        Global definitions of types, constants, enums used across the Scrutiny SDK
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import enum
from dataclasses import dataclass
from datetime import datetime
from scrutiny.core.basic_types import MemoryRegion
from scrutiny.core import validation
import abc
from binascii import hexlify

from typing import List, Optional, Literal, Union, Dict, get_args, Any

__all__ = [
    'AddressSize',
    'SerialStopBits',
    'SerialDataBits',
    'SerialParity',
    'ServerState',
    'WatchableType',
    'ValueStatus',
    'DeviceCommState',
    'DataloggerState',
    'DeviceLinkType',
    'SupportedFeatureMap',
    'DataloggingInfo',
    'DeviceInfo',
    'SFDGenerationInfo',
    'SFDMetadata',
    'SFDInfo',
    'BaseLinkConfig',
    'UDPLinkConfig',
    'TCPLinkConfig',
    'SerialLinkConfig',
    'SupportedLinkConfig',
    'DeviceLinkInfo',
    'ServerInfo',
    'UserCommandResponse'
]

AddressSize = Literal[8, 16, 32, 64, 128]
SerialStopBits = Literal['1', '1.5', '2']
SerialDataBits = Literal[5, 6, 7, 8]
SerialParity = Literal["none", "even", "odd", "mark", "space"]


class ServerState(enum.Enum):
    """(Enum) The state of the connection between the client and the server"""

    Disconnected = 0
    """Disconnected from the server"""
    Connecting = 1
    """Client is trying to connect, full TCP handshake is in progress"""
    Connected = 2
    """Websocket is open and functional"""
    Error = -1
    """The communication closed after an error"""


class DeviceCommState(enum.Enum):
    """(Enum) The state of the connection with the device"""

    NA = 0
    Disconnected = 1
    """No device connected"""
    Connecting = 2
    """Handshake in progress between the server and the device"""
    ConnectedReady = 3
    """A device is connected and ready to respond to queries."""


class WatchableType(enum.Enum):
    """(Enum) Type of watchable available on the server"""

    NA = 0
    Variable = 1
    """A variable found in the device firmware debug symbols"""
    RuntimePublishedValue = 2
    """A readable/writable element identified by a 16bits ID. Explicitly defined in the device firmware source code"""
    Alias = 3
    """A symbolic link watchable that can refers to a :attr:`Variable` or a :attr:`RuntimePublishedValue`"""


class ValueStatus(enum.Enum):
    """(Enum) Represent the validity status of a watchable value"""

    Valid = 1
    """Value is valid"""

    NeverSet = 2
    """Invalid - Never received a value"""

    ServerGone = 3
    """Invalid - Server is gone and cannot provide updates anymore"""

    DeviceGone = 4
    """Invalid - The device is gone and cannot provide updates anymore"""

    SFDUnloaded = 4
    """Invalid - The Scrutiny Firmware Description file has been unloaded and the value is not available anymore"""

    NotWatched = 5
    """Invalid - The watchable is not being watched"""

    def _get_error(self) -> str:
        error = ""
        if self == ValueStatus.Valid:
            pass
        elif self == ValueStatus.NeverSet:
            error = 'Never set'
        elif self == ValueStatus.ServerGone:
            error = "Server has gone away"
        elif self == ValueStatus.DeviceGone:
            error = "Device has been disconnected"
        elif self == ValueStatus.SFDUnloaded:
            error = "Firmware Description File has been unloaded"
        elif self == ValueStatus.NotWatched:
            error = "Not watched"
        else:
            raise RuntimeError(f"Unknown value status {self}")

        return error


class DataloggerState(enum.Enum):
    """(Enum) The state in which the C++ datalogger inside the device firmware actually is"""

    NA = 0
    """The state is not available"""
    Standby = 1
    """The datalogger is doing nothing"""
    WaitForTrigger = 2
    """The datalogger is logging and actively monitor for the trigger condition to end the acquisition"""
    Acquiring = 3
    """The datalogger is actively logging and the acquisition is ending since the trigger event has been fired"""
    DataReady = 4
    """The datalogger has finished logging and data is ready to be read"""
    Error = 5
    """The datalogger has encountered a problem and is not operational"""


class DeviceLinkType(enum.Enum):
    """(Enum) The type of communication link used between the server and the device"""

    _DummyThreadSafe = -2
    _Dummy = -1
    NA = 0
    UDP = 1
    """UDP/IP socket"""
    TCP = 2
    """TCP/IP Socket"""
    Serial = 3
    """Serial port"""
    # CAN = 4 # Todo
    # SPI = 5 # Todo


@dataclass(frozen=True)
class SupportedFeatureMap:
    """(Immutable struct) Represent the list of features that the connected device supports"""

    memory_write: bool
    """Indicates if the device allows write to memory"""

    datalogging: bool
    """Indicates if the device is able of doing datalogging"""

    user_command: bool
    """Indicates if the device has a callback set for the user command"""

    sixtyfour_bits: bool
    """Indicates if the device supports 64bits element. 64bits RPV and datalogging of 64bits elements (variable or RPV) are not possible if False. 
    Watching 64 bits variables does not depends on the device and is therefore always possible"""


@dataclass(frozen=True)
class DataloggingInfo:
    """(Immutable struct) Information about the datalogger that are volatile"""

    state: DataloggerState
    """The state of the datalogger in the device"""

    completion_ratio: Optional[float]
    """The completion ratio of the actually running acquisition. ``None`` if no acquisition being captured"""


@dataclass(frozen=True)
class DeviceInfo:
    """(Immutable struct) Information about the device connected to the server"""

    device_id: str
    """A unique ID identifying the device and its software (Firmware ID). """

    display_name: str
    """The display name broadcasted by the device"""

    max_tx_data_size: int
    """Maximum payload size that the device can send"""

    max_rx_data_size: int
    """Maximum payload size that the device can receive"""

    max_bitrate_bps: Optional[int]
    """Maximum bitrate between the device and the server. Requested by the device. ``None`` if no throttling is requested"""

    rx_timeout_us: int
    """Amount of time without data being received that the device will wait to restart its reception state machine (new frame)"""

    heartbeat_timeout: float
    """Timeout value without heartbeat message response to consider that the communication is broken"""

    address_size_bits: AddressSize
    """Address size in the device"""

    protocol_major: int
    """Device communication protocol version (major number)"""

    protocol_minor: int
    """Device communication protocol version (minor number)"""

    supported_features: SupportedFeatureMap
    """Features supported by the device"""

    forbidden_memory_regions: List[MemoryRegion]
    """List of memory region that cannot be access"""

    readonly_memory_regions: List[MemoryRegion]
    """List of memory region that are read-only"""


@dataclass(frozen=True)
class SFDGenerationInfo:
    """(Immutable struct) Metadata relative to the generation of the SFD"""

    timestamp: Optional[datetime]
    """Date/time at which the SFD has been created ``None`` if not available"""
    python_version: Optional[str]
    """Python version with which the SFD has been created ``None`` if not available"""
    scrutiny_version: Optional[str]
    """Scrutiny version with which the SFD has been created ``None`` if not available"""
    system_type: Optional[str]
    """Type of system on which the SFD has been created. Value given by Python `platform.system()`. ``None`` if not available"""


@dataclass(frozen=True)
class SFDMetadata:
    """(Immutable struct) All the metadata associated with a Scrutiny Firmware Description"""

    project_name: Optional[str]
    """Name of the project. ``None`` if not available"""
    author: Optional[str]
    """The author of this firmware. ``None`` if not available"""
    version: Optional[str]
    """The version string of this firmware. ``None`` if not available"""
    generation_info: Optional[SFDGenerationInfo]
    """Metadata regarding the creation environment of the SFD file. ``None`` if not available"""


@dataclass(frozen=True)
class SFDInfo:
    """(Immutable struct) Represent a Scrutiny Firmware Description"""

    firmware_id: str
    """Unique firmware hash"""

    metadata: Optional[SFDMetadata]
    """The firmware metadata embedded in the Scrutiny Firmware Description file if available. ``None`` if no metadata has been added to the SFD"""


class BaseLinkConfig(abc.ABC):
    def _to_api_format(self) -> Dict[str, Any]:
        raise NotImplementedError("Abstract class")


@dataclass(frozen=True)
class UDPLinkConfig(BaseLinkConfig):
    """(Immutable struct) The configuration structure for a device link of type :attr:`UDP<scrutiny.sdk.DeviceLinkType.UDP>`"""

    host: str
    """Target device hostname"""
    port: int
    """Device UDP port number"""

    def __post_init__(self) -> None:
        validation.assert_int_range(self.port, 'port', 0, 0xFFFF)

    def _to_api_format(self) -> Dict[str, Any]:
        return {
            'host': self.host,
            'port': self.port
        }


@dataclass(frozen=True)
class TCPLinkConfig(BaseLinkConfig):
    """(Immutable struct)The configuration structure for a device link of type :attr:`TCP<scrutiny.sdk.DeviceLinkType.TCP>`"""

    host: str
    """Target device hostname"""
    port: int
    """Device TCP port number"""

    def __post_init__(self) -> None:
        validation.assert_int_range(self.port, 'port', 0, 0xFFFF)

    def _to_api_format(self) -> Dict[str, Any]:
        return {
            'host': self.host,
            'port': self.port
        }


@dataclass(frozen=True)
class SerialLinkConfig(BaseLinkConfig):
    """(Immutable struct) The configuration structure for a device link of type :attr:`Serial<scrutiny.sdk.DeviceLinkType.Serial>`"""

    port: str
    """Port name on the machine. COMX on Windows. /dev/xxx on posix platforms"""
    baudrate: int
    """Communication speed in baud/sec"""
    stopbits: SerialStopBits = '1'
    """Number of stop bits. 1, 1.5, 2"""
    databits: SerialDataBits = 8
    """Number of data bits. 5, 6, 7, 8"""
    parity: SerialParity = 'none'
    """Serial communication parity bits"""

    def __post_init__(self) -> None:
        validation.assert_type(self.port, 'port', str)
        validation.assert_int_range(self.baudrate, 'baudrate', 1)
        validation.assert_val_in(self.stopbits, 'stopbits', get_args(SerialStopBits))
        validation.assert_val_in(self.databits, 'databits', get_args(SerialDataBits))
        validation.assert_val_in(self.parity, 'databits', get_args(SerialParity))

    def _to_api_format(self) -> Dict[str, Any]:
        return {
            'port': self.port,
            'baudrate': self.baudrate,
            'stopbits': self.stopbits,
            'databits': self.databits,
            'parity': self.parity,
        }


SupportedLinkConfig = Union[UDPLinkConfig, TCPLinkConfig, SerialLinkConfig]


@dataclass(frozen=True)
class DeviceLinkInfo:
    """(Immutable struct) Represent a communication link between the server and a device"""

    type: DeviceLinkType
    """Type of communication channel between the server and the device"""
    config: Optional[SupportedLinkConfig]
    """A channel type specific configuration"""


@dataclass(frozen=True)
class ServerInfo:
    """(Immutable struct) A summary of everything going on on the server side. Status broadcasted by the server to every client."""

    device_comm_state: DeviceCommState
    """Status of the communication between the server and the device"""

    device_session_id: Optional[str]
    """A unique ID created each time a communication with the device is established. ``None`` when no communication with a device."""

    device: Optional[DeviceInfo]
    """Information about the connected device. ``None`` if no device is connected"""

    datalogging: DataloggingInfo
    """Datalogging state"""

    sfd: Optional[SFDInfo]
    """The Scrutiny Firmware Description file actually loaded on the server. ``None`` if none is loaded"""

    device_link: DeviceLinkInfo
    """Communication channel presently used to communicate with the device"""


@dataclass(frozen=True)
class UserCommandResponse:
    """(Immutable struct) Response returned by the device after performing a :meth:`ScrutinyClient.user_command<scrutiny.sdk.client.ScrutinyClient.user_command>`"""

    subfunction: int
    """The subfunction echoed by the device when sending a response"""

    data: bytes
    """The data returned by the device"""

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(subfunction={self.subfunction}, data=b\'{hexlify(self.data).decode()}\')'
