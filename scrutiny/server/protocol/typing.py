#    typing.py
#        Mypy typing information for the Scrutiny protocol
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from typing import TypedDict, Optional, List, Union
import scrutiny.server.protocol.commands as cmd
from scrutiny.core.codecs import Encodable
from scrutiny.core.basic_types import RuntimePublishedValue
import scrutiny.server.datalogging.definitions.device as device_datalogging
from scrutiny.server.device.device_info import ExecLoop


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

        class GetLoopDefinition(TypedDict):
            loop_id: int

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
        class Configure(TypedDict):
            loop_id: int
            config_id: int
            config: device_datalogging.Configuration

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
    Request.GetInfo.GetLoopDefinition,

    Request.MemoryControl.Read,
    Request.MemoryControl.Write,
    Request.MemoryControl.ReadRPV,
    Request.MemoryControl.WriteRPV,

    Request.DatalogControl.Configure,

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
            datalogging: bool
            user_command: bool
            _64bits: bool

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

        class GetLoopCount(TypedDict):
            loop_count: int

        class GetLoopDefinition(TypedDict):
            loop_id: int
            loop: ExecLoop

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

        class GetSetup(TypedDict):
            buffer_size: int
            encoding: device_datalogging.Encoding
            max_signal_count: int

        class GetStatus(TypedDict):
            state: device_datalogging.DataloggerState
            remaining_byte_from_trigger_to_complete: int
            byte_counter_since_trigger: int

        class GetAcquisitionMetadata(TypedDict):
            acquisition_id: int
            config_id: int
            nb_points: int
            datasize: int
            points_after_trigger: int

        class ReadAcquisition(TypedDict):
            finished: bool
            rolling_counter: int
            acquisition_id: int
            data: bytes
            crc: Optional[int]

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
    Response.GetInfo.GetLoopCount,
    Response.GetInfo.GetLoopDefinition,

    Response.MemoryControl.Read,
    Response.MemoryControl.Write,
    Response.MemoryControl.ReadRPV,
    Response.MemoryControl.WriteRPV,

    Response.DatalogControl.GetSetup,
    Response.DatalogControl.GetStatus,
    Response.DatalogControl.GetAcquisitionMetadata,
    Response.DatalogControl.ReadAcquisition,

    Response.CommControl.Discover,
    Response.CommControl.Heartbeat,
    Response.CommControl.GetParams,
    Response.CommControl.Connect,
]
