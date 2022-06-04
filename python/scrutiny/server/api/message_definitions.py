from scrutiny.core.firmware_description import MetadataType

from typing import TypedDict, Optional, List, Any, Dict, Union


class ApiMsgComp_SFDEntry(TypedDict):
    firmware_id:str
    metadata : MetadataType

class ApiMsgComp_DeviceCommLinkDef(TypedDict):
    link_type:str
    config:Dict


class ApiMsg_S2C_InformServerStatus(TypedDict):
    cmd:str
    device_status:str
    loaded_sfd:Optional[ApiMsgComp_SFDEntry]
    device_comm_link: ApiMsgComp_DeviceCommLinkDef


#Dict[Any, Any] is tmeporary until all typing is complete
APIMessage = Union[ApiMsg_S2C_InformServerStatus, Dict[Any, Any]]  