#    datalogging.py
#        Contains the definitions related to the datalogger that are globals to all modules.
#        Mainly what can be stored to the storage
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import zlib
import struct
from uuid import uuid4
from dataclasses import dataclass
from datetime import datetime
import csv
import logging
from scrutiny.core.firmware_description import MetadataType

from typing import List, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    import _csv

__all__ = [
    'AxisDefinition',
    'DataSeries',
    'DataSeriesWithAxis',
    'DataloggingAcquisition'
]


@dataclass(frozen=True)
class AxisDefinition:
    """Represent an axis"""
    name: str
    """The name of the axis. Used for display"""
    axis_id: int
    """A unique ID used to identify the axis"""


class DataSeries:
    """A data series is a series of measurement represented by a series of 64 bits floating point value """

    name: str
    """The name of the data series. Used for display"""
    logged_element: str
    """The server element that was the source of the data. Path to a variable, alias or RPV (Runtime Published Value)"""
    data: List[float]
    """The data stored as a list of 64 bits float"""

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


@dataclass(frozen=True)
class DataSeriesWithAxis:
    series: DataSeries
    """The dataseries containing the acquisition data"""

    axis: AxisDefinition
    """The Y-Axis to which the dataseries is bound to"""


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

    firmware_name: Optional[str]
    """The firmware name taken from the metadata of the SFD loaded when the acquisition was made. ``None`` if it is not available"""

    def __init__(self,
                 firmware_id: str,
                 reference_id: Optional[str] = None,
                 acq_time: Optional[datetime] = None,
                 name: Optional[str] = None,
                 firmware_name: Optional[str] = None):
        self.reference_id = reference_id if reference_id is not None else self.make_unique_id()
        self.firmware_id = firmware_id
        self.acq_time = datetime.now() if acq_time is None else acq_time
        self.xdata = DataSeries()
        self.name = name
        self.ydata = []
        self.trigger_index = None
        self.firmware_name = firmware_name

    @classmethod
    def make_unique_id(self) -> str:
        return uuid4().hex.replace('-', '')

    def set_xdata(self, xdata: DataSeries) -> None:
        if not isinstance(xdata, DataSeries):
            raise TypeError('xdata must be a Dataseries instance')
        self.xdata = xdata

    def add_data(self, dataseries: DataSeries, axis: AxisDefinition) -> None:
        if not isinstance(dataseries, DataSeries):
            raise TypeError('dataseries must be a Dataseries instance')
        if not isinstance(axis, AxisDefinition):
            raise TypeError('axis must be a AxisDefinition instance')

        for data in self.ydata:
            if data.axis.axis_id == axis.axis_id and data.axis is not axis:
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
        if not isinstance(ds, DataSeries):
            raise TypeError('ds must be a DataSeries instance')

        for a in self.ydata:
            if a.series is ds:
                return a.axis
        raise LookupError("Cannot find axis for given dataseries")

    def set_trigger_index(self, val: Optional[int]) -> None:
        if val is not None:
            if not isinstance(val, int):
                raise ValueError("Trigger index must be an integer")

            if val < 0:
                raise ValueError("Trigger index must be a positive value")

            if val >= len(self.xdata.get_data()):
                raise ValueError("Trigger index cannot be greater than the x-axis data length")

        self.trigger_index = val

    def write_csv(self, writer: '_csv._writer') -> None:
        firmware_name = 'N/A' if self.firmware_name is None else self.firmware_name
        writer.writerow(['Acquisition Name', self.name])
        writer.writerow(['Acquisition ID', self.reference_id])
        writer.writerow(['Acquisition time', self.acq_time.strftime(r"%Y-%m-%d %H:%M:%S")])
        writer.writerow(['Firmware ID', self.firmware_id])
        writer.writerow(['Firmware Name', firmware_name])
        writer.writerow([])

        header_row = [self.xdata.name] + [ydata.series.name for ydata in self.ydata]
        if self.trigger_index is not None:
            header_row.append('Trigger')

        writer.writerow(header_row)
        for ydata in self.ydata:
            if len(self.xdata.data) != len(ydata.series.data):
                logging.error("Data of series %s does not have the same length as the X-Axis" % ydata.series.name)

        for i in range(len(self.xdata.data)):
            trigger_val = []
            if self.trigger_index is not None:
                trigger_val = [0 if i < self.trigger_index else 1]
            writer.writerow([self.xdata.data[i]] + [ydata.series.data[i] for ydata in self.ydata] + trigger_val)

    def to_csv(self, filename: str) -> None:
        """Export a DataloggingAcquisition content to a csv file

        :param filename: The file to write to
        """
        with open(filename, 'w', encoding='utf8', newline='') as f:
            writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            self.write_csv(writer)
