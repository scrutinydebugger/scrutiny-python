#    acquisition.py
#        Definitions and helper function to manipulate a datalogging acquisition
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

import time
from uuid import uuid4
import zlib

from scrutiny.server.datalogging import definitions
from scrutiny.core.basic_types import *
from typing import List, Dict, Optional
import struct


class DataSeries:
    """A data series is a series of measurement represented by a series of 64bit floating point value """
    name: str
    logged_element: str
    data: List[float]

    def __init__(self, name: str = "unnamed", logged_element: str = ""):
        self.name = name
        self.logged_element = logged_element
        self.data = []

    def set_data(self, data: List[float]) -> None:
        self.data = data

    def set_data_binary(self, data: bytes) -> None:
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

    def __init__(self, firmware_id: str, reference_id: Optional[str] = None, timestamp: Optional[float] = None):
        self.reference_id = reference_id if reference_id is not None else self.make_unique_id()
        self.firmware_id = firmware_id
        self.timestamp = time.time() if timestamp is None else timestamp
        self.xaxis = None
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


def deinterleave_acquisition_data(data: bytes, config: definitions.Configuration, rpv_map: Dict[int, RuntimePublishedValue], encoding: definitions.Encoding) -> List[List[bytes]]:
    """
    Takes data written in the format [s1[n], s2[n], s3[n], s1[n+1], s2[n+1], s3[n+1], s1[n+2] ...]
    and put it in the format [s1[n], s1[n+1], s1[n+2]],  [s2[n], s2[n+1], s2[n+2]], [s3[n], s3[n+1], s3[n+2]]
    """
    data_out: List[List[bytes]] = []
    signals_def = config.get_signals()
    for i in range(len(signals_def)):
        data_out.append([])

    if encoding == definitions.Encoding.RAW:
        cursor = 0
        while cursor < len(data):
            for i in range(len(signals_def)):
                signaldef = signals_def[i]

                if isinstance(signaldef, definitions.MemoryLoggableSignal):
                    datasize = signaldef.size
                elif isinstance(signaldef, definitions.RPVLoggableSignal):
                    if signaldef.rpv_id not in rpv_map:
                        raise ValueError("RPV 0x%04X not part of given rpv_map" % signaldef.rpv_id)
                    rpv = rpv_map[signaldef.rpv_id]
                    datasize = rpv.datatype.get_size_byte()
                elif isinstance(signaldef, definitions.TimeLoggableSignal):
                    datasize = 4    # Time is always uint32
                else:
                    raise NotImplementedError("Unsupported signal type")
                if len(data) < cursor + datasize:
                    raise ValueError('Not enough data in buffer for signal #%d' % i)
                data_out[i].append(data[cursor:cursor + datasize])
                cursor += datasize
    else:
        raise NotImplementedError('Unsupported encoding %s' % encoding)

    return data_out
