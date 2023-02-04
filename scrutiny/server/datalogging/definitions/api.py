
from enum import Enum
from dataclasses import dataclass
import zlib
import struct
import time
from uuid import uuid4

from scrutiny.server.device.device_info import ExecLoopType
from scrutiny.server.datastore.datastore_entry import DatastoreEntry
import scrutiny.server.datalogging.definitions.device as device_datalogging
from typing import List, Dict, Optional, Callable, Union

from scrutiny.core.typehints import GenericCallback


class XAxisType(Enum):
    """Represent a type of X-Axis that a user can select"""
    IdealTime = 0,
    MeasuredTime = 1,
    Signal = 2


@dataclass
class SamplingRate:
    """Represent a sampling rate that a use can select"""
    name: str
    frequency: Optional[float]
    rate_type: ExecLoopType
    device_identifier: int


class DataSeries:
    """A data series is a series of measurement represented by a series of 64bit floating point value """
    name: str
    logged_element: str
    data: List[float]

    def __init__(self, data: List[float] = [], name: str = "unnamed", logged_element: str = ""):
        self.name = name
        self.logged_element = logged_element
        self.data = data

    def set_data(self, data: List[float]) -> None:
        self.data = data

    def set_data_binary(self, data: bytes) -> None:
        if not isinstance(data, bytes):
            raise ValueError('Data must be bytes')

        data = zlib.decompress(data)
        if len(data) % 8 != 0:
            raise ValueError('Invalid byte stream')
        nfloat = len(data) // 8
        self.data = list(struct.unpack('>' + 'd' * nfloat, data))

    def get_data(self) -> List[float]:
        return self.data

    def get_data_binary(self) -> bytes:
        data = struct.pack('>' + 'd' * len(self.data), *self.data)
        return zlib.compress(data)


class DataloggingAcquisition:
    """Represent an acquisition of multiple signals"""

    name: Optional[str]
    """A display name associated with the acquisition for easier management"""

    reference_id: str
    """ID used to reference the acquisition in the storage"""

    firmware_id: str
    """Firmware ID of the device on which the acquisition has been taken"""

    timestamp: float
    """Timestamp at which the acquisition has been taken"""

    xaxis: Optional[DataSeries]
    """The series of data that represent to X-Axis"""

    data: List[DataSeries]
    """List of data series acquired"""

    def __init__(self, firmware_id: str, reference_id: Optional[str] = None, timestamp: Optional[float] = None, name: Optional[str] = None):
        self.reference_id = reference_id if reference_id is not None else self.make_unique_id()
        self.firmware_id = firmware_id
        self.timestamp = time.time() if timestamp is None else timestamp
        self.xaxis = None
        self.name = name
        self.data = []

    @classmethod
    def make_unique_id(self) -> str:
        return uuid4().hex.replace('-', '')

    def set_xaxis(self, xaxis: DataSeries) -> None:
        self.xaxis = xaxis

    def add_data(self, dataserie: DataSeries) -> None:
        self.data.append(dataserie)

    def get_data(self) -> List[DataSeries]:
        return self.data


class AcquisitionRequestCompletedCallback(GenericCallback):
    callback: Callable[[bool, Optional[DataloggingAcquisition]], None]


TriggerConditionID = device_datalogging.TriggerConditionID


class TriggerConditionOperandType(Enum):
    LITERAL = 0
    WATCHABLE = 1


@dataclass
class TriggerConditionOperand:
    type: TriggerConditionOperandType
    value: Union[float, int, bool, DatastoreEntry]


@dataclass
class TriggerCondition:
    condition_id: TriggerConditionID
    operands: List[TriggerConditionOperand]


@dataclass
class SignalDefinition:
    name: Optional[str]
    entry: DatastoreEntry


@dataclass
class AcquisitionRequest:
    rate_identifier: int
    decimation: int
    timeout: float
    probe_location: float
    trigger_hold_time: float
    trigger_condition: TriggerCondition  # fixme
    x_axis_type: XAxisType
    x_axis_signal: Optional[SignalDefinition]
    signals: List[SignalDefinition]
    completion_callback: AcquisitionRequestCompletedCallback
