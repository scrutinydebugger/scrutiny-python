#    typing.py
#        Mypy typing information for the Scrutiny protocol
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

from typing import *

import scrutiny.server.protocol.commands as cmd
from scrutiny.core.codecs import Encodable
from scrutiny.core.basic_types import RuntimePublishedValue
from scrutiny.server.protocol.datalog import DatalogConfiguration, DatalogLocation, LogStatus, RecordInfo


class BlockAddressLength(TypedDict):
    address: int
    length: int


class BlockAddressData(TypedDict):
    address: int
    data: bytes


class BlockAddressDataMasked(TypedDict):
    address: int
    data: bytes
    write_mask: Optional[bytes]


class RPVWriteRequest(TypedDict):
    id: int
    value: Encodable


class RPVIdDataPair(TypedDict):
    id: int
    data: Encodable


class RPVIdSizePair(TypedDict):
    id: int
    size: int


class Request:
    class Empty(TypedDict):
        pass

    class GetInfo:
        class GetSpecialMemoryRegionLocation(TypedDict):
            region_type: cmd.GetInfo.MemoryRangeType
            region_index: int

        class GetRuntimePublishedValuesDefinition(TypedDict):
            start: int
            count: int

    class MemoryControl:
        class Read(TypedDict):
            blocks_to_read: List[BlockAddressLength]

        class Write(TypedDict):
            blocks_to_write: List[BlockAddressData]

        class WriteMasked(TypedDict):
            blocks_to_write: List[BlockAddressDataMasked]

        class ReadRPV(TypedDict):
            rpvs_id: List[int]

        class WriteRPV(TypedDict):
            rpvs: List[RPVWriteRequest]

    class DatalogControl:
        class ReadRecordings(TypedDict):
            record_id: int

        class ConfigureDatalog(TypedDict):
            configuration: DatalogConfiguration

    class CommControl:
        class Discover(TypedDict):
            magic: bytes

        class Connect(TypedDict):
            magic: bytes

        class Heartbeat(TypedDict):
            session_id: int
            challenge: int

        class Disconnect(TypedDict):
            session_id: int


RequestData = Union[
    Request.Empty,
    Request.GetInfo.GetSpecialMemoryRegionLocation,
    Request.GetInfo.GetRuntimePublishedValuesDefinition,

    Request.MemoryControl.Read,
    Request.MemoryControl.Write,
    Request.MemoryControl.ReadRPV,
    Request.MemoryControl.WriteRPV,

    Request.DatalogControl.ReadRecordings,
    Request.DatalogControl.ConfigureDatalog,

    Request.CommControl.Discover,
    Request.CommControl.Connect,
    Request.CommControl.Heartbeat,
    Request.CommControl.Disconnect
]


class Response:
    class Empty(TypedDict):
        pass

    class GetInfo:
        class GetProtocolVersion(TypedDict):
            minor: int
            major: int

        class GetSupportedFeatures(TypedDict):
            memory_write: bool
            datalog_acquire: bool
            user_command: bool

        class GetSoftwareId(TypedDict):
            software_id: bytes

        class GetSpecialMemoryRegionCount(TypedDict):
            nbr_readonly: int
            nbr_forbidden: int

        class GetSpecialMemoryRegionLocation(TypedDict):
            region_type: cmd.GetInfo.MemoryRangeType
            region_index: int
            start: int
            end: int

        class GetRuntimePublishedValuesCount(TypedDict):
            count: int

        class GetRuntimePublishedValuesDefinition(TypedDict):
            rpvs: List[RuntimePublishedValue]

    class MemoryControl:
        class Read(TypedDict):
            read_blocks: List[BlockAddressData]

        class Write(TypedDict):
            written_blocks: List[BlockAddressLength]

        class ReadRPV(TypedDict):
            read_rpv: List[RPVIdDataPair]

        class WriteRPV(TypedDict):
            written_rpv: List[RPVIdSizePair]

    class DatalogControl:
        class GetAvailableTarget(TypedDict):
            targets: List[DatalogLocation]

        class GetBufferSize(TypedDict):
            size: int

        class GetLogStatus(TypedDict):
            status: LogStatus

        class ArmLog(TypedDict):
            record_id: int

        class ConfigureDatalog(TypedDict):
            record_id: int

        class ReadRecordings(TypedDict):
            record_id: int
            data: bytes

        class ListRecordings(TypedDict):
            recordings: List[RecordInfo]

        class GetSamplingRates(TypedDict):
            sampling_rates: List[float]

    class CommControl:
        class Discover(TypedDict):
            protocol_major: int
            protocol_minor: int
            firmware_id: bytes
            display_name: str

        class Heartbeat(TypedDict):
            session_id: int
            challenge_response: int

        class GetParams(TypedDict):
            max_rx_data_size: int
            max_tx_data_size: int
            max_bitrate_bps: int
            heartbeat_timeout_us: int
            rx_timeout_us: int
            address_size_byte: int

        class Connect(TypedDict):
            magic: bytes
            session_id: int


ResponseData = Union[
    Response.Empty,
    Response.GetInfo.GetProtocolVersion,
    Response.GetInfo.GetSupportedFeatures,
    Response.GetInfo.GetSoftwareId,
    Response.GetInfo.GetSpecialMemoryRegionCount,
    Response.GetInfo.GetSpecialMemoryRegionLocation,
    Response.GetInfo.GetRuntimePublishedValuesCount,
    Response.GetInfo.GetRuntimePublishedValuesDefinition,

    Response.MemoryControl.Read,
    Response.MemoryControl.Write,
    Response.MemoryControl.ReadRPV,
    Response.MemoryControl.WriteRPV,

    Response.DatalogControl.GetAvailableTarget,
    Response.DatalogControl.GetBufferSize,
    Response.DatalogControl.GetLogStatus,
    Response.DatalogControl.ArmLog,
    Response.DatalogControl.ConfigureDatalog,
    Response.DatalogControl.ReadRecordings,
    Response.DatalogControl.ListRecordings,
    Response.DatalogControl.GetSamplingRates,

    Response.CommControl.Discover,
    Response.CommControl.Heartbeat,
    Response.CommControl.GetParams,
    Response.CommControl.Connect,
]
