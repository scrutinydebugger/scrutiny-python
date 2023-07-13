import enum
from typing import *
from dataclasses import dataclass
from datetime import datetime

AddressSize = Literal[8, 16, 32, 64, 128]
SerialStopBits = Literal['1', '1.5', '2']
SerialDataBits = Literal[5, 6, 7, 8]
SerialParity = Literal["none", "even", "odd", "mark", "space"]


class ServerState(enum.Enum):
    Disconnected = 0
    Connecting = 1
    Connected = 2
    Error = -1


class DeviceState(enum.Enum):
    Disconnected = 0
    Connecting = 1
    Connected = 2


class WatchableType(enum.Enum):
    NA = 0
    Variable = 1
    RuntimePulishedValue = 2
    Alias = 3


class ValueStatus(enum.Enum):
    Valid = 1
    NeverSet = 2
    ServerGone = 3
    DeviceGone = 4


class DeviceCommState(enum.Enum):
    NA = 0
    Disconnected = 1
    Connecting = 2
    ConnectedReady = 3


class DataloggerState(enum.Enum):
    NA = 0
    Standby = 1
    WaitForTrigger = 2
    Acquiring = 3
    DataReady = 4
    Error = 5


class DeviceLinkType(enum.Enum):
    Dummy = -1
    NA = 0
    UDP = 1
    TCP = 2
    Serial = 3
    # CAN = 4 # Todo
    # SPI = 5 # Todo


@dataclass(frozen=True)
class SupportedFeatureMap:
    memory_write: bool
    datalogging: bool
    user_command: bool
    sixtyfour_bits: bool


@dataclass(frozen=True)
class MemoryRegion:
    start: int
    size: int

    @property
    def end(self) -> int:
        return max(self.start, self.start + self.size - 1)


@dataclass(frozen=True)
class DataloggingInfo:
    state: DataloggerState
    completion_ratio: Optional[float]


@dataclass(frozen=True)
class DeviceInfo:
    device_id: str
    display_name: str
    max_tx_data_size: int
    max_rx_data_size: int
    max_bitrate_bps: int
    rx_timeout_us: int
    heartbeat_timeout: float
    address_size_bits: AddressSize
    protocol_major: int
    protocol_minor: int
    supported_features: SupportedFeatureMap
    forbidden_memory_regions: List[MemoryRegion]
    readonly_memory_regions: List[MemoryRegion]


@dataclass(frozen=True)
class SFDGenerationInfo:
    timestamp: Optional[datetime]
    python_version: Optional[str]
    scrutiny_version: Optional[str]
    system_type: Optional[str]


@dataclass(frozen=True)
class SFDMetadata:
    project_name: Optional[str]
    author: Optional[str]
    version: Optional[str]
    generation_info: Optional[SFDGenerationInfo]


@dataclass(frozen=True)
class SFDInfo:
    firmware_id: str
    metadata: SFDMetadata


@dataclass(frozen=True)
class UDPLinkConfig:
    host: str
    port: int


@dataclass(frozen=True)
class TCPLinkConfig:
    host: str
    port: int


@dataclass(frozen=True)
class SerialLinkConfig:
    port: str
    baudrate: int
    stopbits: SerialStopBits
    databits: SerialDataBits
    parity: SerialParity


SupportedLinkConfig = Union[UDPLinkConfig, TCPLinkConfig, SerialLinkConfig]


@dataclass(frozen=True)
class DeviceLinkInfo:
    type: DeviceLinkType
    config: Optional[SupportedLinkConfig]


@dataclass(frozen=True)
class ServerInfo:
    device_comm_state: DeviceCommState
    device_session_id: Optional[str]
    device: Optional[DeviceInfo]
    datalogging: DataloggingInfo
    sfd: Optional[SFDInfo]
    device_link: DeviceLinkInfo
