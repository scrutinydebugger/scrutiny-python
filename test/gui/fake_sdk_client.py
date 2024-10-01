__all__ = ['FakeSDKClient']

from scrutiny import sdk
from typing import Optional

default_server_info = sdk.ServerInfo(
    device_comm_state=sdk.DeviceCommState.Disconnected,
    device_session_id=None,
    datalogging=sdk.DataloggingInfo(sdk.DataloggerState.NA, completion_ratio=None),
    sfd=None,
    device=None,
    device_link=sdk.DeviceLinkInfo(type=sdk.DeviceLinkType.UDP, config=dict(host='localhost', prot=1234))
)

class FakeSDKClient:
    server_state:sdk.ServerState
    hostname:Optional[str]
    port:Optional[int]
    server_info:Optional[sdk.ServerInfo]

    def __init__(self):
        self.server_state = sdk.ServerState.Disconnected
        self.server_info = None

    def connect(self, hostname:str, port:int, wait_status:bool=True):
        self.server_state = sdk.ServerState.Connected
        if wait_status:
            self.server_info = default_server_info

    def disconnect(self):
        self.server_state = sdk.ServerState.Disconnected
        self.server_info = None

    def wait_server_status_update(self, timeout=None):
        pass

    def get_server_status(self) -> Optional[sdk.ServerInfo]:
        if self.server_info is None:
            return None
        
        return self.server_info
