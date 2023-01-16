#    typing.py
#        Mypy typing information for API
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

from typing import TypedDict, Optional, List, Dict, Union, Literal, Any
from scrutiny.core.typehints import EmptyDict

import scrutiny.core.firmware_description
import scrutiny.server.device.links.serial_link
import scrutiny.server.device.links.udp_link

WatchableType = Literal['alias', 'var', 'rpv']
# Mapping between app type and API type.
SFDMetadata = scrutiny.core.firmware_description.MetadataType
SerialLinkConfig = scrutiny.server.device.links.serial_link.SerialConfig
UdpLinkConfig = scrutiny.server.device.links.udp_link.UdpConfig
LinkConfig = Union[EmptyDict, UdpLinkConfig, SerialLinkConfig]
LinkType = Literal['none', 'udp', 'serial', 'dummy', 'thread_safe_dummy']
Datatype = Literal[
    'sint8', 'sint16', 'sint32', 'sint64', 'sint128', 'sint256',
    'uint8', 'uint16', 'uint32', 'uint64', 'uint128', 'uint256',
    'float8', 'float16', 'float32', 'float64', 'float128', 'float256',
    'cfloat8', 'cfloat16', 'cfloat32', 'cfloat64', 'cfloat128', 'cfloat256',
    'boolean'
]


class BaseC2SMessage(TypedDict):
    cmd: str
    reqid: int


class BaseS2CMessage(TypedDict):
    cmd: str
    reqid: Optional[int]


class EnumDefinition(TypedDict):
    name: str
    values: Dict[str, int]


class DatastoreEntryDefinitionNoType(TypedDict, total=False):
    id: str
    display_path: str
    datatype: str
    enum: Optional[EnumDefinition]


class WatchableListContent(TypedDict):
    var: List[DatastoreEntryDefinitionNoType]
    alias: List[DatastoreEntryDefinitionNoType]
    rpv: List[DatastoreEntryDefinitionNoType]


class DeviceInfo(TypedDict):
    device_id: str
    display_name: str
    max_tx_data_size: int
    max_rx_data_size: int
    max_bitrate_bps: int
    rx_timeout_us: int
    heartbeat_timeout_us: int
    address_size_bits: int
    protocol_major: int
    protocol_minor: int
    supported_feature_map: Dict[str, bool]
    forbidden_memory_regions: List[Dict[str, int]]
    readonly_memory_regions: List[Dict[str, int]]


class SFDEntry(TypedDict):
    firmware_id: str
    metadata: SFDMetadata


class DeviceCommLinkDef(TypedDict):
    link_type: LinkType
    link_config: LinkConfig


class GetWatchableList_Filter(TypedDict):
    type: WatchableType


class WatchableCount(TypedDict):
    alias: int
    var: int
    rpv: int


class UpdateRecord(TypedDict):
    watchable: str
    value: Any


class C2S:
    class Echo(BaseC2SMessage):
        payload: str

    class GetInstalledSFD(BaseC2SMessage):
        pass

    class GetLoadedSFD(BaseC2SMessage):
        pass

    class GetServerStatus(BaseC2SMessage):
        pass

    class GetWatchableCount(BaseC2SMessage):
        pass

    class GetWatchableList(BaseC2SMessage):
        max_per_response: int
        filter: GetWatchableList_Filter

    class LoadSFD(BaseC2SMessage):
        firmware_id: str

    class SubscribeWatchable(BaseC2SMessage):
        watchables: List[str]

    class UnsubscribeWatchable(BaseC2SMessage):
        watchables: List[str]

    class SetLinkConfig(BaseC2SMessage, DeviceCommLinkDef):
        pass

    class WriteValue(BaseC2SMessage):
        updates: List[UpdateRecord]

    GetPossibleLinkConfig = Dict[Any, Any]  # Todo


class S2C:
    class Empty(BaseS2CMessage):
        pass

    class Echo(BaseS2CMessage):
        payload: str

    class Error(BaseS2CMessage):
        request_cmd: str
        msg: str

    class GetInstalledSFD(BaseS2CMessage):
        sfd_list: Dict[str, SFDMetadata]

    class GetLoadedSFD(BaseS2CMessage):
        firmware_id: Optional[str]

    class InformServerStatus(BaseS2CMessage):
        device_status: str
        device_info: Optional[DeviceInfo]
        loaded_sfd: Optional[SFDEntry]
        device_comm_link: DeviceCommLinkDef   # Dict is Any,Any.  Should be EmptyDict.

    class GetWatchableCount(BaseS2CMessage):
        qty: WatchableCount

    class GetWatchableList(BaseS2CMessage):
        qty: WatchableCount
        content: WatchableListContent
        done: bool

    class SubscribeWatchable(BaseS2CMessage):
        watchables: List[str]

    class UnsubscribeWatchable(BaseS2CMessage):
        watchables: List[str]

    class WatchableUpdate(BaseS2CMessage):
        updates: List[Dict[str, Any]]

    GetPossibleLinkConfig = Dict[Any, Any]  # TODO

    class WriteValue(BaseS2CMessage):
        watchables: List[str]

    class WriteCompletion(BaseS2CMessage):
        watchable: str
        status: Literal['ok', 'failed']
        timestamp: float


C2SMessage = Union[
    C2S.Echo,
    C2S.GetInstalledSFD,
    C2S.GetLoadedSFD,
    C2S.GetServerStatus,
    C2S.GetWatchableCount,
    C2S.GetWatchableList,
    C2S.LoadSFD,
    C2S.SubscribeWatchable,
    C2S.UnsubscribeWatchable,
    C2S.GetPossibleLinkConfig,
    C2S.WriteValue
]

S2CMessage = Union[
    S2C.Empty,
    S2C.Echo,
    S2C.Error,
    S2C.GetInstalledSFD,
    S2C.GetLoadedSFD,
    S2C.InformServerStatus,
    S2C.GetWatchableCount,
    S2C.GetWatchableList,
    S2C.SubscribeWatchable,
    S2C.UnsubscribeWatchable,
    S2C.WatchableUpdate,
    S2C.GetPossibleLinkConfig,
    S2C.WriteValue,
    S2C.WriteCompletion
]
