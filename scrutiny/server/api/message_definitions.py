#    message_definitions.py
#        Static type definition of the API messages
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

from scrutiny.core.firmware_description import MetadataType
from typing import TypedDict, Optional, List, Any, Dict, Union


class ApiMsgComp_DeviceInfo(TypedDict):
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


class ApiMsgComp_SFDEntry(TypedDict):
    firmware_id: str
    metadata: MetadataType


class ApiMsgComp_DeviceCommLinkDef(TypedDict):
    link_type: str
    config: Dict


class ApiMsg_S2C_InformServerStatus(TypedDict):
    cmd: str
    reqid: str
    device_status: str
    device_info: Optional[ApiMsgComp_DeviceInfo]
    loaded_sfd: Optional[ApiMsgComp_SFDEntry]
    device_comm_link: ApiMsgComp_DeviceCommLinkDef


# Dict[Any, Any] is tmeporary until all typing is complete
APIMessage = Union[ApiMsg_S2C_InformServerStatus, Dict[Any, Any]]
