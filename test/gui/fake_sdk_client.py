#    fake_sdk_client.py
#        Emulate the SDK ScrutinyClient for the purpose of unit testing
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['FakeSDKClient']

from scrutiny import sdk
from scrutiny.sdk.client import WatchableListDownloadRequest, ScrutinyClient
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass
import inspect
import queue

default_server_info = sdk.ServerInfo(
    device_comm_state=sdk.DeviceCommState.Disconnected,
    device_session_id=None,
    datalogging=sdk.DataloggingInfo(sdk.DataloggerState.NA, completion_ratio=None),
    sfd_firmware_id=None,
    device_link=sdk.DeviceLinkInfo(type=sdk.DeviceLinkType.UDP, config=dict(host='localhost', prot=1234), operational=True)
)

@dataclass
class DownloadWatchableListFunctionCall:
    """Class used to track every calls to download_watchable_list"""
    #Inputs
    types:Optional[List[sdk.WatchableType]]
    max_per_response:int
    name_patterns:List[str]

    request:WatchableListDownloadRequest    # Output

class FakeSDKClient:
    server_state:sdk.ServerState
    hostname:Optional[str]
    port:Optional[int]
    server_info:Optional[sdk.ServerInfo]
    _pending_download_requests:Dict[int, DownloadWatchableListFunctionCall]
    _func_call_log:Dict[str, int]
    _force_connect_fail:bool

    _req_id:int
    _event_queue:"queue.Queue[ScrutinyClient.Events._ANY_EVENTS]"
    _enabled_events:int


    def __init__(self):
        self.server_state = sdk.ServerState.Disconnected
        self.server_info = None
        self._req_id=0
        self._pending_download_requests = {}
        self._func_call_log = {}
        self._force_connect_fail = False
        self._enabled_events = 0
        self._event_queue = queue.Queue()
    
    def get_call_count(self, funcname:str) -> int:
        if funcname not in self._func_call_log:
            return 0
        return self._func_call_log[funcname]

    def _log_call(self):
        funcname = inspect.stack()[1][3]
        if funcname not in self._func_call_log:
            self._func_call_log[funcname] = 0
        self._func_call_log[funcname]+=1
    
    def force_connect_fail(self, val:bool = True):
        self._force_connect_fail = val


    def connect(self, hostname:str, port:int, wait_status:bool=True):
        self._log_call()
        if self._force_connect_fail:
            raise sdk.exceptions.ConnectionError("Failed to connect (simulated)")
        self.server_state = sdk.ServerState.Connected
        self.trigger_event(ScrutinyClient.Events.ConnectedEvent(hostname, port))
        self.hostname = hostname
        self.port = port
        if wait_status:
            self.server_info = default_server_info

    def disconnect(self):
        self._log_call()
        was_connected = (self.server_state == sdk.ServerState.Connected)
        self.server_state = sdk.ServerState.Disconnected
        if was_connected:
            self.trigger_event(ScrutinyClient.Events.DisconnectedEvent(self.hostname, self.port))
        self.server_info = None

    def wait_server_status_update(self, timeout=None):
        pass

    def get_latest_server_status(self) -> Optional[sdk.ServerInfo]:
        if self.server_info is None:
            return None
        
        return self.server_info
    

    def download_watchable_list(self, types:Optional[List[sdk.WatchableType]]=None, 
                                max_per_response:int=500,
                                name_patterns:List[str] = [],
                                partial_reception_callback:Optional[Callable[[Dict[sdk.WatchableType, Dict[str, sdk.WatchableConfiguration]], bool], None]] = None
                                ) -> WatchableListDownloadRequest:
        req = WatchableListDownloadRequest(self, self._req_id, new_data_callback=partial_reception_callback)
        
        self._pending_download_requests[self._req_id] = DownloadWatchableListFunctionCall(
            types=types,
            max_per_response=max_per_response,
            name_patterns=name_patterns,
            request=req
        )
        self._req_id+=1
        return req
    
    def _cancel_download_watchable_list_request(self, reqid:int) -> None:
        self._log_call()
        req = None
        try:
            req = self._pending_download_requests[reqid].request
        except KeyError:
            pass

        if req is not None:
            req._mark_complete(success=False, failure_reason="Cancelled")
            try:
                del self._pending_download_requests[reqid]
            except KeyError:
                pass
    
    def _complete_success_watchable_list_request(self, reqid:int) -> None:
        self._log_call()
        req = None
        try:
            req = self._pending_download_requests[reqid].request
        except KeyError:
            pass

        if req is not None:
            req._mark_complete(success=True)
            try:
                del self._pending_download_requests[reqid]
            except KeyError:
                pass
    
    def get_download_watchable_list_function_calls(self) -> List[DownloadWatchableListFunctionCall]:
        """For unit test only. """
        return list(self._pending_download_requests.values())

    def close_socket(self):
        pass

    def listen_events(self, enabled_events:int):
        self._enabled_events = enabled_events

    def trigger_event(self, event:ScrutinyClient.Events._ANY_EVENTS):
        if self._enabled_events & event._filter_flag:
            self._event_queue.put(event)

    def read_event(self, timeout:Optional[float] = None) -> Optional[ScrutinyClient.Events._ANY_EVENTS]:
        try:
            return self._event_queue.get(block=True, timeout=timeout)
        except queue.Empty:
            return None

    def has_event_pending(self) -> bool:
        return not self._event_queue.empty()


    def _simulate_receive_status(self, info:Optional[sdk.ServerInfo] = None):
        if info is None:
            self.server_info = default_server_info
        else:
            self.server_info = info

    def _simulate_device_connect(self, session_id):
        if self.server_state != sdk.ServerState.Connected:
            raise RuntimeError("Cannot simulate device connect if the server is not connected")
        
        assert self.server_info is not None
        
        self.server_info = sdk.ServerInfo(
            datalogging=self.server_info.datalogging,
            device_comm_state=sdk.DeviceCommState.ConnectedReady,
            device_link=sdk.NoneLinkConfig,
            device_session_id=session_id,
            sfd_firmware_id=self.server_info.sfd_firmware_id
        )

        self.trigger_event(ScrutinyClient.Events.DeviceReadyEvent(session_id))

    def _simulate_device_disconnect(self):
        if self.server_state != sdk.ServerState.Connected:
            raise RuntimeError("Cannot simulate device disconnect if the server is not connected")
        
        assert self.server_info is not None
        previous_session_id = self.server_info.device_session_id
        self.server_info = sdk.ServerInfo(
            datalogging=self.server_info.datalogging,
            device_comm_state=sdk.DeviceCommState.Disconnected,
            device_link=sdk.NoneLinkConfig,
            device_session_id=None,
            sfd_firmware_id=self.server_info.sfd_firmware_id
        )
        self.trigger_event(ScrutinyClient.Events.DeviceGoneEvent(previous_session_id))
    
    def _simulate_sfd_loaded(self, firmware_id):
        if self.server_state != sdk.ServerState.Connected:
            raise RuntimeError("Cannot simulate SFD loading if the server is not connected")
        
        assert self.server_info is not None
        self.server_info = sdk.ServerInfo(
            datalogging=self.server_info.datalogging,
            device_comm_state=self.server_info.device_comm_state,
            device_link=self.server_info.device_link,
            device_session_id=self.server_info.device_session_id,
            sfd_firmware_id=self.server_info.sfd_firmware_id
        )

        self.trigger_event(ScrutinyClient.Events.SFDLoadedEvent(firmware_id))

    def _simulate_sfd_unloaded(self):
        if self.server_state != sdk.ServerState.Connected:
            raise RuntimeError("Cannot simulate SFD unloading if the server is not connected")
        
        assert self.server_info is not None
        previous_firmware_id = self.server_info.sfd_firmware_id
        self.server_info = sdk.ServerInfo(
            datalogging=self.server_info.datalogging,
            device_comm_state=self.server_info.device_comm_state,
            device_link=self.server_info.device_link,
            device_session_id=self.server_info.device_session_id,
            sfd_firmware_id=None
        )

        self.trigger_event(ScrutinyClient.Events.SFDUnLoadedEvent(previous_firmware_id))
