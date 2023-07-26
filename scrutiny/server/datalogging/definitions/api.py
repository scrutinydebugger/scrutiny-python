#    api.py
#        Contains the definitions related to the datalogging feature on the API side
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

from enum import Enum
from dataclasses import dataclass
import zlib
import struct
from uuid import uuid4
from datetime import datetime

from scrutiny.server.device.device_info import ExecLoopType
from scrutiny.server.datastore.datastore_entry import DatastoreEntry
import scrutiny.server.datalogging.definitions.device as device_datalogging
from typing import List, Dict, Optional, Callable, Union, Set

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


@dataclass
class AxisDefinition:
    """Represent an axis"""
    name: str
    external_id: int

    def __hash__(self):
        return id(self)


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

    def __len__(self) -> int:
        return len(self.data)


@dataclass
class DataSeriesWithAxis:
    series: DataSeries
    axis: AxisDefinition


class DataloggingAcquisition:
    """Represent an acquisition of multiple signals"""

    name: Optional[str]
    """A display name associated with the acquisition for easier management"""

    reference_id: str
    """ID used to reference the acquisition in the storage"""

    firmware_id: str
    """Firmware ID of the device on which the acquisition has been taken"""

    acq_time: datetime
    """Time at which the acquisition has been taken"""

    xdata: DataSeries
    """The series of data that represent the X-Axis"""

    ydata: List[DataSeriesWithAxis]
    """List of data series acquired"""

    trigger_index: Optional[int]
    """Sample index of the trigger"""

    def __init__(self,
                 firmware_id: str,
                 reference_id: Optional[str] = None,
                 acq_time: Optional[datetime] = None,
                 name: Optional[str] = None):
        self.reference_id = reference_id if reference_id is not None else self.make_unique_id()
        self.firmware_id = firmware_id
        self.acq_time = datetime.now() if acq_time is None else acq_time
        self.xdata = DataSeries()
        self.name = name
        self.ydata = []
        self.trigger_index = None

    @classmethod
    def make_unique_id(self) -> str:
        return uuid4().hex.replace('-', '')

    def set_xdata(self, xdata: DataSeries) -> None:
        self.xdata = xdata

    def add_data(self, dataseries: DataSeries, axis: AxisDefinition) -> None:
        for data in self.ydata:
            if data.axis.external_id == axis.external_id and data.axis is not axis:
                raise ValueError("Two data series are using different Y-Axis with identical external ID.")
        self.ydata.append(DataSeriesWithAxis(series=dataseries, axis=axis))

    def get_data(self) -> List[DataSeriesWithAxis]:
        return self.ydata

    def get_unique_yaxis_list(self) -> List[AxisDefinition]:
        yaxis = set()
        for dataseries in self.ydata:
            yaxis.add(dataseries.axis)

        return list(yaxis)

    def find_axis_for_dataseries(self, ds: DataSeries) -> AxisDefinition:
        for a in self.ydata:
            if a.series is ds:
                return a.axis
        raise LookupError("Cannot find axis for given dataseries")

    def set_trigger_index(self, val: Optional[int]) -> None:
        if val is not None:
            if not isinstance(val, int):
                raise ValueError("trigger index must be an integer")

            if val < 0:
                raise ValueError("trigger index must be a positive value")

            if val >= len(self.xdata.get_data()):
                raise ValueError("Trigger index cannot be further than the x-axis data length")

        self.trigger_index = val


class APIAcquisitionRequestCompletionCallback(GenericCallback):
    callback: Callable[[bool, str, Optional[DataloggingAcquisition]], None]


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
class SignalDefinitionWithAxis(SignalDefinition):
    axis: AxisDefinition


@dataclass
class AcquisitionRequest:
    name: Optional[str]
    rate_identifier: int
    decimation: int
    timeout: float
    probe_location: float
    trigger_hold_time: float
    trigger_condition: TriggerCondition
    x_axis_type: XAxisType
    x_axis_signal: Optional[SignalDefinition]
    signals: List[SignalDefinitionWithAxis]

    def get_yaxis_list(self) -> List[AxisDefinition]:
        axis_set: Set[AxisDefinition] = set()
        for signal in self.signals:
            axis_set.add(signal.axis)
        return list(axis_set)
