from scrutiny.core.firmware_description import MetadataType

from typing import TypedDict, Optional, List, Any, Dict, Union





class SFDEntry(TypedDict):
    firmware_id:str
    metadata : MetadataType

class DeviceCommLinkDef(TypedDict):
    link_type:str
    config:Dict


class S2C_InformServerStatus(TypedDict):
    cmd:str
    device_status:str
    loaded_sfd:Optional[SFDEntry]
    device_comm_link: DeviceCommLinkDef





APIMessage = Union[S2C_InformServerStatus, Dict[Any, Any]]