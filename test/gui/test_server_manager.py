#    test_server_manager.py
#        Test suite for the ServerManager
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny import sdk
from scrutiny.gui.core.server_manager import ServerManager, ServerConfig
from scrutiny.gui.core.watchable_index import WatchableIndex
from test.gui.fake_sdk_client import FakeSDKClient, DownloadWatchableListFunctionCall
from test.gui.base_gui_test import ScrutinyBaseGuiTest, EventType
import time

from typing import List, Optional, Any

# These value are not really used as they are given to a fake client
SERVER_MANAGER_CONFIG = ServerConfig('127.0.0.1', 5555)


DUMMY_DATASET_RPV = {
    '/rpv/rpv1000' : sdk.WatchableConfiguration(server_id='rpv_111', watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/rpv/rpv1001' : sdk.WatchableConfiguration(server_id='rpv_222', watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None)
}

DUMMY_DATASET_ALIAS = {
    '/alias/xxx/alias1' : sdk.WatchableConfiguration(server_id='alias_111', watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/alias/alias2' : sdk.WatchableConfiguration(server_id='alias_222', watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/alias/alias3' : sdk.WatchableConfiguration(server_id='alias_333', watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None)
}

DUMMY_DATASET_VAR = {
    '/var/xxx/var1' : sdk.WatchableConfiguration(server_id='var_111', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/xxx/var2' : sdk.WatchableConfiguration(server_id='var_222', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/var3' : sdk.WatchableConfiguration(server_id='var_333', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/var4' : sdk.WatchableConfiguration(server_id='var_444', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None)
}

DUMMY_DEVICE = sdk.DeviceInfo(
    device_id='unittest',
    address_size_bits=32,
    display_name='unit tests',
    forbidden_memory_regions=[],
    readonly_memory_regions=[],
    heartbeat_timeout=5,
    max_bitrate_bps=None,
    max_rx_data_size=128,
    max_tx_data_size=128,
    protocol_major=1,
    protocol_minor=0,
    rx_timeout_us=500,
    supported_features=sdk.SupportedFeatureMap(
        memory_write=True,
        datalogging=True,
        sixtyfour_bits=True,
        user_command=True
    ),
    datalogging_capabilities=sdk.DataloggingCapabilities(
        buffer_size=4096,
        encoding=sdk.DataloggingEncoding.RAW,
        max_nb_signal=32,
        sampling_rates=[sdk.FixedFreqSamplingRate(0, "sr1", 10000.0), sdk.VariableFreqSamplingRate(1, 'sr2')]
    )
)

class TestServerManager(ScrutinyBaseGuiTest):

    def setUp(self) -> None:
        super().setUp()
        self.fake_client = FakeSDKClient()   
        self.server_manager = ServerManager(
            watchable_index=WatchableIndex(),
            client=self.fake_client
            )    # Inject a stub of the SDK.

        self.server_manager.signals.server_connected.connect(lambda : self.declare_event(EventType.SERVER_CONNECTED))
        self.server_manager.signals.server_disconnected.connect(lambda : self.declare_event(EventType.SERVER_DISCONNECTED))
        self.server_manager.signals.device_ready.connect(lambda : self.declare_event(EventType.DEVICE_READY))
        self.server_manager.signals.device_disconnected.connect(lambda : self.declare_event(EventType.DEVICE_DISCONNECTED))
        self.server_manager.signals.datalogging_state_changed.connect(lambda : self.declare_event(EventType.DATALOGGING_STATE_CHANGED))
        self.server_manager.signals.sfd_loaded.connect(lambda : self.declare_event(EventType.SFD_LOADED))
        self.server_manager.signals.sfd_unloaded.connect(lambda : self.declare_event(EventType.SFD_UNLOADED))
        self.server_manager.signals.index_changed.connect(lambda : self.declare_event(EventType.WATCHABLE_INDEX_CHANGED))
    
    def tearDown(self) -> None:
        if self.server_manager.is_running():
            self.server_manager.stop()
        super().tearDown()
    
    def wait_server_state(self, state:sdk.ServerState, timeout:int=1) -> None:
        self.wait_equal(self.server_manager.get_server_state, state, 1)

    def test_hold_5_sec(self):
        self.assertFalse(self.server_manager.is_running())
        self.assertEqual(self.server_manager.get_server_state(), sdk.ServerState.Disconnected)
        self.server_manager.start(SERVER_MANAGER_CONFIG)
        self.assertTrue(self.server_manager.is_running())

        self.wait_equal(self.server_manager.is_running, False, 5, no_assert=True)  # Early exit if it fails
        
        
        self.assertTrue(self.server_manager.is_running())
        self.assertEqual(self.server_manager.get_server_state(), sdk.ServerState.Connected)
        self.server_manager.stop()
        self.assertFalse(self.server_manager.is_running())
        self.wait_false_with_events(self.server_manager.is_stopping, 2)
        self.assertEqual(self.server_manager.get_server_state(), sdk.ServerState.Disconnected)

    def test_events_connect_disconnect(self):
        self.assertEqual(self.event_list, [])
        for i in range(5):
            self.server_manager.start(SERVER_MANAGER_CONFIG)
            self.wait_events([EventType.SERVER_CONNECTED], timeout=1)
            self.assertEqual(self.server_manager.get_server_state(), sdk.ServerState.Connected)
            
            self.server_manager.stop()
            self.wait_false_with_events(self.server_manager.is_stopping, 2)
            self.wait_events_and_clear([EventType.SERVER_CONNECTED, EventType.SERVER_DISCONNECTED], timeout=1)
            self.assertEqual(self.server_manager.get_server_state(), sdk.ServerState.Disconnected)
            self.wait_false(self.server_manager.is_running, 1)

    def test_event_device_connect_disconnect(self):
        self.assertEqual(self.event_list, [])
        self.server_manager.start(SERVER_MANAGER_CONFIG)

        self.wait_events_and_clear([EventType.SERVER_CONNECTED], timeout=1)

        for i in range(5):
            self.fake_client.server_info = sdk.ServerInfo(
                device_comm_state=sdk.DeviceCommState.ConnectedReady,
                device_session_id='session_id1', # This value is used to detect connection change on the device side
                datalogging=sdk.DataloggingInfo(state=sdk.DataloggerState.Standby, completion_ratio=None),
                device_link=sdk.DeviceLinkInfo(type=sdk.DeviceLinkType._Dummy, config={}),
                sfd=None,
                device=DUMMY_DEVICE
            )

            self.wait_events_and_clear([EventType.DEVICE_READY], timeout=1)

            self.fake_client.server_info = sdk.ServerInfo(
                device_comm_state=sdk.DeviceCommState.Disconnected,
                device_session_id=None, # This value is used to detect connection change on the device side
                datalogging=sdk.DataloggingInfo(state=sdk.DataloggerState.NA, completion_ratio=None),
                device_link=sdk.DeviceLinkInfo(type=sdk.DeviceLinkType._Dummy, config={}),
                sfd=None,
                device=None
            )

            self.wait_events_and_clear([EventType.DEVICE_DISCONNECTED], timeout=1)

        self.fake_client.server_info = None
        self.server_manager.stop()
        self.wait_server_state(sdk.ServerState.Disconnected)        
        self.assert_events([EventType.SERVER_DISCONNECTED])
    
    def test_event_device_connect_disconnect_with_sfd(self):
        # Connect the device and load the SFD at the same time. It has a special code path
        self.assertEqual(self.event_list, [])
        self.server_manager.start(SERVER_MANAGER_CONFIG)

        self.wait_events_and_clear([EventType.SERVER_CONNECTED], timeout=1)

        for i in range(5):
            self.fake_client.server_info = sdk.ServerInfo(
                device_comm_state=sdk.DeviceCommState.ConnectedReady,
                device_session_id='session_id1', # This value is used to detect connection change on the device side
                datalogging=sdk.DataloggingInfo(state=sdk.DataloggerState.Standby, completion_ratio=None),
                device_link=sdk.DeviceLinkInfo(type=sdk.DeviceLinkType._Dummy, config={}),
                sfd=sdk.SFDInfo(firmware_id='abcdef', metadata=None),
                device=DUMMY_DEVICE
            )

            self.wait_events_and_clear([EventType.DEVICE_READY, EventType.SFD_LOADED], timeout=1)

            self.fake_client.server_info = sdk.ServerInfo(
                device_comm_state=sdk.DeviceCommState.Disconnected,
                device_session_id=None, # This value is used to detect connection change on the device side
                datalogging=sdk.DataloggingInfo(state=sdk.DataloggerState.NA, completion_ratio=None),
                device_link=sdk.DeviceLinkInfo(type=sdk.DeviceLinkType._Dummy, config={}),
                sfd=None,
                device=None
            )

            self.wait_events_and_clear([EventType.SFD_UNLOADED, EventType.DEVICE_DISCONNECTED], timeout=1)

        self.fake_client.server_info = None
        self.server_manager.stop()
        self.wait_server_state(sdk.ServerState.Disconnected)        
        self.assert_events([EventType.SERVER_DISCONNECTED])

    def test_event_device_connect_disconnect_with_sfd_after_connection(self):
        # Leave some time between device ready and SFD load and vice versa. Will go through a diferent code path than
        # if the SFD is loaded at the same time as the device is ready
        self.assertEqual(self.event_list, [])
        self.server_manager.start(SERVER_MANAGER_CONFIG)

        self.wait_events_and_clear([EventType.SERVER_CONNECTED], timeout=1)

        for i in range(5):
            self.fake_client.server_info = sdk.ServerInfo(
                device_comm_state=sdk.DeviceCommState.ConnectedReady,
                device_session_id='session_id1', # This value is used to detect connection change on the device side
                datalogging=sdk.DataloggingInfo(state=sdk.DataloggerState.Standby, completion_ratio=None),
                device_link=sdk.DeviceLinkInfo(type=sdk.DeviceLinkType._Dummy, config={}),
                sfd=None,
                device=DUMMY_DEVICE
            )

            self.wait_events_and_clear([EventType.DEVICE_READY], timeout=1)

            self.fake_client.server_info = sdk.ServerInfo(
                device_comm_state=sdk.DeviceCommState.ConnectedReady,
                device_session_id='session_id1', # This value is used to detect connection change on the device side
                datalogging=sdk.DataloggingInfo(state=sdk.DataloggerState.Standby, completion_ratio=None),
                device_link=sdk.DeviceLinkInfo(type=sdk.DeviceLinkType._Dummy, config={}),
                sfd=sdk.SFDInfo("abc", metadata=None),
                device=DUMMY_DEVICE
            )

            self.wait_events_and_clear([EventType.SFD_LOADED], timeout=1)

            self.fake_client.server_info = sdk.ServerInfo(
                device_comm_state=sdk.DeviceCommState.ConnectedReady,
                device_session_id='session_id1', # This value is used to detect connection change on the device side
                datalogging=sdk.DataloggingInfo(state=sdk.DataloggerState.Standby, completion_ratio=None),
                device_link=sdk.DeviceLinkInfo(type=sdk.DeviceLinkType._Dummy, config={}),
                sfd=None,
                device=DUMMY_DEVICE
            )

            self.wait_events_and_clear([EventType.SFD_UNLOADED], timeout=1)

            self.fake_client.server_info = sdk.ServerInfo(
                device_comm_state=sdk.DeviceCommState.Disconnected,
                device_session_id=None, # This value is used to detect connection change on the device side
                datalogging=sdk.DataloggingInfo(state=sdk.DataloggerState.NA, completion_ratio=None),
                device_link=sdk.DeviceLinkInfo(type=sdk.DeviceLinkType._Dummy, config={}),
                sfd=None,
                device=None
            )

            self.wait_events_and_clear([EventType.DEVICE_DISCONNECTED], timeout=1)

        self.fake_client.server_info = None
        self.server_manager.stop()
        self.wait_server_state(sdk.ServerState.Disconnected)        
        self.assert_events([EventType.SERVER_DISCONNECTED])

    def test_device_disconnect_ready_events_on_session_id_change(self):
        self.assertEqual(self.event_list, [])
        self.server_manager.start(SERVER_MANAGER_CONFIG)

        self.wait_events_and_clear([EventType.SERVER_CONNECTED], timeout=1)

        self.fake_client.server_info = sdk.ServerInfo(
            device_comm_state=sdk.DeviceCommState.ConnectedReady,
            device_session_id='session_id1', # This value is used to detect connection change on the device side
            datalogging=sdk.DataloggingInfo(state=sdk.DataloggerState.Standby, completion_ratio=None),
            device_link=sdk.DeviceLinkInfo(type=sdk.DeviceLinkType._Dummy, config={}),
            sfd=None,
            device=DUMMY_DEVICE
        )

        self.wait_events_and_clear([EventType.DEVICE_READY], timeout=1)
        
        # The server manager should have initiated a download of RPV, but not Alias/Var
        download_watchable_list_calls = self.fake_client.get_download_watchable_list_function_calls()
        self.assertEqual(len(download_watchable_list_calls), 1)
        self.assertEqual(download_watchable_list_calls[0].types, [sdk.WatchableType.RuntimePublishedValue])   

        # Only the session ID changes. 
        # Should trigger a device disconnected + device ready event.
        prev_req = download_watchable_list_calls[0].request
        for i in range(5):
            self.fake_client.server_info = sdk.ServerInfo(
                device_comm_state=self.fake_client.server_info.device_comm_state,
                device_session_id=f'new_session_id{i}',     # We change that.
                datalogging=self.fake_client.server_info.datalogging,
                device_link=self.fake_client.server_info.device_link,
                sfd=self.fake_client.server_info.sfd,
                device=DUMMY_DEVICE
            )

            # Download request never complete, therefore no watchble_index_changed
            self.wait_events_and_clear([EventType.DEVICE_DISCONNECTED, EventType.DEVICE_READY, ], timeout=1)

            # Previous download should have been interrupted
            self.assertTrue(prev_req.completed)
            self.assertFalse(prev_req.is_success) 

            # The server manager should have initiated a download of RPV, but not Alias/Var
            download_watchable_list_calls = self.fake_client.get_download_watchable_list_function_calls()
            self.assertEqual(len(download_watchable_list_calls), 1)
            self.assertEqual(download_watchable_list_calls[0].types, [sdk.WatchableType.RuntimePublishedValue])

            prev_req = download_watchable_list_calls[0].request

        self.fake_client.server_info = None
        self.wait_events_and_clear([EventType.DEVICE_DISCONNECTED], timeout=1)

        # Previous download should have been interrupted
        self.assertTrue(prev_req.completed)
        self.assertFalse(prev_req.is_success) 

        self.server_manager.stop()
        self.wait_server_state(sdk.ServerState.Disconnected)        
        self.assert_events([EventType.SERVER_DISCONNECTED])
    
    def test_device_disconnect_ready_events_on_session_id_change_with_sfd(self):
        self.assertEqual(self.event_list, [])
        self.server_manager.start(SERVER_MANAGER_CONFIG)

        self.wait_events_and_clear([EventType.SERVER_CONNECTED], timeout=1)

        self.fake_client.server_info = sdk.ServerInfo(
            device_comm_state=sdk.DeviceCommState.ConnectedReady,
            device_session_id='session_id1', # This value is used to detect connection change on the device side
            datalogging=sdk.DataloggingInfo(state=sdk.DataloggerState.Standby, completion_ratio=None),
            device_link=sdk.DeviceLinkInfo(type=sdk.DeviceLinkType._Dummy, config={}),
            sfd=sdk.SFDInfo(firmware_id="abc", metadata=None),
            device=DUMMY_DEVICE
        )

        self.wait_events_and_clear([EventType.DEVICE_READY, EventType.SFD_LOADED], timeout=1)
        
        # The server manager should have initiated a download of RPV, but not Alias/Var

        def check_watchable_call_list(thelist:List[DownloadWatchableListFunctionCall]) -> None:
            self.assertEqual(len(thelist), 2)
            if len(thelist[0].types) == 1:
                self.assertEqual(len(thelist[1].types), 2)

                self.assertIn(sdk.WatchableType.RuntimePublishedValue, thelist[0].types)
                self.assertIn(sdk.WatchableType.Alias, thelist[1].types)
                self.assertIn(sdk.WatchableType.Variable, thelist[1].types)
            elif len(thelist[0].types) == 2:
                self.assertEqual(len(thelist[1].types), 1)

                self.assertIn(sdk.WatchableType.RuntimePublishedValue, thelist[1].types)
                self.assertIn(sdk.WatchableType.Alias, thelist[0].types)
                self.assertIn(sdk.WatchableType.Variable, thelist[0].types)
            else:
                self.fail("Requests are bad")
        
        download_watchable_list_calls = self.fake_client.get_download_watchable_list_function_calls()
        check_watchable_call_list(download_watchable_list_calls)

        # Only the session ID changes. 
        # Should trigger a device disconnected + device ready event.
        prev_reqs = [x.request for x in download_watchable_list_calls]
        for i in range(5):
            self.fake_client.server_info = sdk.ServerInfo(
                device_comm_state=self.fake_client.server_info.device_comm_state,
                device_session_id=f'new_session_id{i}',     # We change that.
                datalogging=self.fake_client.server_info.datalogging,
                device_link=self.fake_client.server_info.device_link,
                sfd=self.fake_client.server_info.sfd,
                device=DUMMY_DEVICE
            )

            self.wait_events_and_clear([EventType.SFD_UNLOADED, EventType.DEVICE_DISCONNECTED, EventType.DEVICE_READY, EventType.SFD_LOADED], timeout=1)

            # Previous download should have been interrupted
            for prev_req in prev_reqs:
                self.assertTrue(prev_req.completed)
                self.assertFalse(prev_req.is_success) 

            # The server manager should have initiated a download of RPV, but not Alias/Var
            download_watchable_list_calls = self.fake_client.get_download_watchable_list_function_calls()
            check_watchable_call_list(download_watchable_list_calls)

            prev_reqs = [x.request for x in download_watchable_list_calls]

        self.fake_client.server_info = None
        self.wait_events_and_clear([EventType.SFD_UNLOADED, EventType.DEVICE_DISCONNECTED], timeout=1)

        # Previous download should have been interrupted
        for prev_req in prev_reqs:
            self.assertTrue(prev_req.completed)
            self.assertFalse(prev_req.is_success) 

        self.server_manager.stop()
        self.wait_server_state(sdk.ServerState.Disconnected)        
        self.assert_events([EventType.SERVER_DISCONNECTED])
    
    def test_event_datalogging_state_changed(self):
        self.assertEqual(self.event_list, [])
        self.server_manager.start(SERVER_MANAGER_CONFIG)

        self.wait_events_and_clear([EventType.SERVER_CONNECTED], timeout=1)

        self.fake_client.server_info = sdk.ServerInfo(
            device_comm_state=sdk.DeviceCommState.ConnectedReady,
            device_session_id='session_id1', # This value is used to detect connection change on the device side
            datalogging=sdk.DataloggingInfo(state=sdk.DataloggerState.Standby, completion_ratio=None),
            device_link=sdk.DeviceLinkInfo(type=sdk.DeviceLinkType._Dummy, config={}),
            sfd=None,
            device=DUMMY_DEVICE
        )

        self.wait_events_and_clear([EventType.DEVICE_READY], timeout=1)

        # Only the session ID changes. 
        # Should trigger a device disconnected + device ready event.
        for i in range(5):
            new_dl_state = sdk.DataloggerState.Standby if self.fake_client.server_info.datalogging.state == sdk.DataloggerState.Acquiring else sdk.DataloggerState.Acquiring
            self.fake_client.server_info = sdk.ServerInfo(
                device_comm_state=self.fake_client.server_info.device_comm_state,
                device_session_id=self.fake_client.server_info.device_session_id,     # We change that.
                datalogging=sdk.DataloggingInfo(state=new_dl_state, completion_ratio=None),
                device_link=self.fake_client.server_info.device_link,
                sfd=self.fake_client.server_info.sfd,
                device=DUMMY_DEVICE
            )
        
            self.wait_events_and_clear([EventType.DATALOGGING_STATE_CHANGED], timeout=1)

        if  self.fake_client.server_info.datalogging.state != sdk.DataloggerState.Acquiring:
            self.fake_client.server_info = sdk.ServerInfo(
                device_comm_state=self.fake_client.server_info.device_comm_state,
                device_session_id=self.fake_client.server_info.device_session_id,     
                datalogging=sdk.DataloggingInfo(state=sdk.DataloggerState.Acquiring, completion_ratio=None),    # We change that.
                device_link=self.fake_client.server_info.device_link,
                sfd=self.fake_client.server_info.sfd,
                device=DUMMY_DEVICE
            )
            self.wait_events_and_clear([EventType.DATALOGGING_STATE_CHANGED], timeout=1)

        for i in range(5):
            new_dl_state = sdk.DataloggerState.Standby if self.fake_client.server_info.datalogging.state == sdk.DataloggerState.Acquiring else sdk.DataloggerState.Acquiring
            self.fake_client.server_info = sdk.ServerInfo(
                device_comm_state=self.fake_client.server_info.device_comm_state,
                device_session_id=self.fake_client.server_info.device_session_id,  
                datalogging=sdk.DataloggingInfo(state=sdk.DataloggerState.Acquiring, completion_ratio=float(i)),    # We change that.  
                device_link=self.fake_client.server_info.device_link,
                sfd=self.fake_client.server_info.sfd,
                device=DUMMY_DEVICE
            )
        
            self.wait_events_and_clear([EventType.DATALOGGING_STATE_CHANGED], timeout=1)

        self.fake_client.server_info = None
        self.wait_events_and_clear([EventType.DEVICE_DISCONNECTED], timeout=1)

        self.server_manager.stop()
        self.wait_server_state(sdk.ServerState.Disconnected)        
        self.assert_events([EventType.SERVER_DISCONNECTED])

    def test_disconnect_on_error(self):
        self.server_manager.start(SERVER_MANAGER_CONFIG)

        self.wait_events_and_clear([EventType.SERVER_CONNECTED], timeout=1)
        self.assertEqual(self.fake_client.get_call_count('disconnect'), 0)
        self.fake_client.server_state = sdk.ServerState.Error

        self.wait_events([EventType.SERVER_DISCONNECTED], timeout=1)
        self.assertFalse(self.server_manager.is_running())
        self.assertEqual(self.fake_client.get_call_count('disconnect'), 1)

    def test_auto_reconnect(self):
        self.server_manager.start(SERVER_MANAGER_CONFIG)
        self.server_manager.RECONNECT_DELAY = 0.2

        self.wait_events_and_clear([EventType.SERVER_CONNECTED], timeout=1)
        self.assertEqual(self.fake_client.get_call_count('connect'), 1)

        for i in range(5):
            self.fake_client.disconnect()
            self.wait_events_and_clear([EventType.SERVER_DISCONNECTED, EventType.SERVER_CONNECTED], timeout=self.server_manager.RECONNECT_DELAY+1)
            self.assertEqual(self.fake_client.get_call_count('connect'), i+2)
    
    def test_auto_retry_connect_on_connect_fail(self):
        RETRY_COUNT = 3
        self.fake_client.force_connect_fail()
        self.server_manager.start(SERVER_MANAGER_CONFIG)
        self.wait_true(lambda: self.fake_client.get_call_count('connect')>=1, 1)    # Wait for initial attempt
        
        n = self.fake_client.get_call_count('connect')  # Should read 1
        t1 = time.perf_counter()
        self.wait_true(lambda: self.fake_client.get_call_count('connect') >= n+RETRY_COUNT, (RETRY_COUNT+1)*self.server_manager.RECONNECT_DELAY+1)
        total_time = time.perf_counter() - t1
        
        self.fake_client.force_connect_fail(False)  # Reenable connection
        self.wait_events([EventType.SERVER_CONNECTED], timeout=self.server_manager.RECONNECT_DELAY+1)
        
        self.assertGreater(self.fake_client.get_call_count('connect'), n+RETRY_COUNT)   # Should be n+RETRY_COUNT+1. Could be more depending on scheduling

        self.assertGreaterEqual(total_time, (RETRY_COUNT-1)*self.server_manager.RECONNECT_DELAY)  
        self.assertLessEqual(total_time, (RETRY_COUNT+1)*self.server_manager.RECONNECT_DELAY)  

    def test_event_device_connect_disconnect_with_data_download(self):
        self.assertEqual(self.event_list, [])
        self.server_manager.start(SERVER_MANAGER_CONFIG)
        windex = self.server_manager._index

        self.wait_events_and_clear([EventType.SERVER_CONNECTED], timeout=1)

        nb_loop = 5
        for i in range(nb_loop):
            cancel_request = i % 2 == 1
            self.fake_client.server_info = sdk.ServerInfo(
                device_comm_state=sdk.DeviceCommState.ConnectedReady,
                device_session_id='session_id1', # This value is used to detect connection change on the device side
                datalogging=sdk.DataloggingInfo(state=sdk.DataloggerState.Standby, completion_ratio=None),
                device_link=sdk.DeviceLinkInfo(type=sdk.DeviceLinkType._Dummy, config={}),
                sfd=None,
                device=DUMMY_DEVICE
            )

            self.wait_events_and_clear([EventType.DEVICE_READY], timeout=1)
            calls = self.fake_client.get_download_watchable_list_function_calls()
            self.assertEqual(len(calls), 1)
            req = calls[0].request
            self.assertEqual(calls[0].types, [sdk.WatchableType.RuntimePublishedValue])
            
            if cancel_request:
                req.cancel()
                self.assertFalse(windex.has_data(sdk.WatchableType.RuntimePublishedValue))
                self.assertFalse(windex.has_data(sdk.WatchableType.Alias))
                self.assertFalse(windex.has_data(sdk.WatchableType.Variable))
            else:
                req._add_data({
                    sdk.WatchableType.RuntimePublishedValue : DUMMY_DATASET_RPV
                }, done=True)
                self.fake_client._complete_success_watchable_list_request(req._request_id)
                self.wait_events_and_clear([EventType.WATCHABLE_INDEX_CHANGED], timeout=1)
                self.assertTrue(windex.has_data(sdk.WatchableType.RuntimePublishedValue))
                self.assertFalse(windex.has_data(sdk.WatchableType.Alias))
                self.assertFalse(windex.has_data(sdk.WatchableType.Variable))

            self.fake_client.server_info = sdk.ServerInfo(
                device_comm_state=sdk.DeviceCommState.Disconnected,
                device_session_id=None, # This value is used to detect connection change on the device side
                datalogging=sdk.DataloggingInfo(state=sdk.DataloggerState.NA, completion_ratio=None),
                device_link=sdk.DeviceLinkInfo(type=sdk.DeviceLinkType._Dummy, config={}),
                sfd=None,
                device=None
            )

            if cancel_request:
                expected_events = [EventType.DEVICE_DISCONNECTED]
            else:
                expected_events = [EventType.WATCHABLE_INDEX_CHANGED, EventType.DEVICE_DISCONNECTED]
            self.wait_events_and_clear(expected_events, timeout=1, msg=f"cancel_request={cancel_request}")

            self.assertFalse(self.server_manager._index.has_data(sdk.WatchableType.RuntimePublishedValue))
            self.assertFalse(self.server_manager._index.has_data(sdk.WatchableType.Alias))
            self.assertFalse(self.server_manager._index.has_data(sdk.WatchableType.Variable))

        self.fake_client.server_info = None 
        self.server_manager.stop()
        self.wait_server_state(sdk.ServerState.Disconnected)        
        self.assert_events([EventType.SERVER_DISCONNECTED])

    def test_event_device_connect_disconnect_with_sfd_and_data_download(self):
        # Connect the device and load the SFD at the same time. It has a special code path
        self.assertEqual(self.event_list, [])
        self.server_manager.start(SERVER_MANAGER_CONFIG)

        self.wait_events_and_clear([EventType.SERVER_CONNECTED], timeout=1)

        def respond_to_download_requests(cancel_requests):
            calls = self.fake_client.get_download_watchable_list_function_calls()
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0].types, [sdk.WatchableType.RuntimePublishedValue])
            self.assertCountEqual(calls[1].types, [sdk.WatchableType.Alias, sdk.WatchableType.Variable])
            if sdk.WatchableType.RuntimePublishedValue in calls[0].types:
                rpv_call_index = 0 
                alias_var_call_index = 1
            else:
                rpv_call_index = 1 
                alias_var_call_index = 0
            
            self.assertCountEqual(calls[rpv_call_index].types, [sdk.WatchableType.RuntimePublishedValue])
            self.assertCountEqual(calls[alias_var_call_index].types, [sdk.WatchableType.Alias, sdk.WatchableType.Variable])

            req_rpv = calls[rpv_call_index].request
            req_alias_var = calls[alias_var_call_index].request

            if cancel_requests:
                req_rpv.cancel()
                req_alias_var.cancel()
            else:
                req_rpv._add_data({
                    sdk.WatchableType.RuntimePublishedValue : DUMMY_DATASET_RPV
                }, done=True)
                self.fake_client._complete_success_watchable_list_request(req_rpv._request_id)
                self.wait_events_and_clear([EventType.WATCHABLE_INDEX_CHANGED], timeout=1)

                req_alias_var._add_data({
                    sdk.WatchableType.Alias : DUMMY_DATASET_ALIAS
                }, done=False)
                req_alias_var._add_data({
                    sdk.WatchableType.Variable : DUMMY_DATASET_VAR
                }, done=False)
                self.fake_client._complete_success_watchable_list_request(req_alias_var._request_id)
                self.wait_events_and_clear([EventType.WATCHABLE_INDEX_CHANGED], timeout=1)

        for i in range(5):
            cancel_requests = i%2==1
            self.fake_client.server_info = sdk.ServerInfo(
                device_comm_state=sdk.DeviceCommState.ConnectedReady,
                device_session_id='session_id1', # This value is used to detect connection change on the device side
                datalogging=sdk.DataloggingInfo(state=sdk.DataloggerState.Standby, completion_ratio=None),
                device_link=sdk.DeviceLinkInfo(type=sdk.DeviceLinkType._Dummy, config={}),
                sfd=sdk.SFDInfo(firmware_id='abcdef', metadata=None),
                device=DUMMY_DEVICE
            )

            self.wait_events_and_clear([EventType.DEVICE_READY, EventType.SFD_LOADED], timeout=1)
            respond_to_download_requests(cancel_requests)


            self.fake_client.server_info = sdk.ServerInfo(
                device_comm_state=sdk.DeviceCommState.Disconnected,
                device_session_id=None, # This value is used to detect connection change on the device side
                datalogging=sdk.DataloggingInfo(state=sdk.DataloggerState.NA, completion_ratio=None),
                device_link=sdk.DeviceLinkInfo(type=sdk.DeviceLinkType._Dummy, config={}),
                sfd=None,
                device=None
            )

            if cancel_requests:
                expected_events = [EventType.SFD_UNLOADED, EventType.DEVICE_DISCONNECTED]
            else:
                expected_events = [EventType.WATCHABLE_INDEX_CHANGED,EventType.SFD_UNLOADED, EventType.DEVICE_DISCONNECTED]

            self.wait_events_and_clear(expected_events, timeout=1)

        self.fake_client.server_info = None
        self.server_manager.stop()
        self.wait_server_state(sdk.ServerState.Disconnected)        
        self.assert_events([EventType.SERVER_DISCONNECTED])


    def test_device_disconnect_ready_events_on_session_id_change_with_sfd_and_data_download(self):
        self.assertEqual(self.event_list, [])
        self.server_manager.start(SERVER_MANAGER_CONFIG)

        self.wait_events_and_clear([EventType.SERVER_CONNECTED], timeout=1)

        self.fake_client.server_info = sdk.ServerInfo(
            device_comm_state=sdk.DeviceCommState.ConnectedReady,
            device_session_id='session_id1', # This value is used to detect connection change on the device side
            datalogging=sdk.DataloggingInfo(state=sdk.DataloggerState.Standby, completion_ratio=None),
            device_link=sdk.DeviceLinkInfo(type=sdk.DeviceLinkType._Dummy, config={}),
            sfd=sdk.SFDInfo(firmware_id="abc", metadata=None),
            device=DUMMY_DEVICE
        )

        self.wait_events_and_clear([EventType.DEVICE_READY, EventType.SFD_LOADED], timeout=1)

        def respond_to_download_requests():
            calls = self.fake_client.get_download_watchable_list_function_calls()
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0].types, [sdk.WatchableType.RuntimePublishedValue])
            self.assertCountEqual(calls[1].types, [sdk.WatchableType.Alias, sdk.WatchableType.Variable])
            if sdk.WatchableType.RuntimePublishedValue in calls[0].types:
                rpv_call_index = 0 
                alias_var_call_index = 1
            else:
                rpv_call_index = 1 
                alias_var_call_index = 0
            
            self.assertCountEqual(calls[rpv_call_index].types, [sdk.WatchableType.RuntimePublishedValue])
            self.assertCountEqual(calls[alias_var_call_index].types, [sdk.WatchableType.Alias, sdk.WatchableType.Variable])

            req_rpv = calls[rpv_call_index].request
            req_alias_var = calls[alias_var_call_index].request

            req_rpv._add_data({
                sdk.WatchableType.RuntimePublishedValue : DUMMY_DATASET_RPV
            }, done=True)
            self.fake_client._complete_success_watchable_list_request(req_rpv._request_id)
            self.wait_events_and_clear([EventType.WATCHABLE_INDEX_CHANGED], timeout=1)

            req_alias_var._add_data({
                sdk.WatchableType.Alias : DUMMY_DATASET_ALIAS
            }, done=False)
            req_alias_var._add_data({
                sdk.WatchableType.Variable : DUMMY_DATASET_VAR
            }, done=False)
            self.fake_client._complete_success_watchable_list_request(req_alias_var._request_id)
            self.wait_events_and_clear([EventType.WATCHABLE_INDEX_CHANGED], timeout=1)

        respond_to_download_requests()

        self.assertTrue(self.server_manager._index.has_data(sdk.WatchableType.RuntimePublishedValue))
        self.assertTrue(self.server_manager._index.has_data(sdk.WatchableType.Alias))
        self.assertTrue(self.server_manager._index.has_data(sdk.WatchableType.Variable))
        # Only the session ID changes. 
        # Should trigger a device disconnected + device ready event.
        for i in range(5):
            self.fake_client.server_info = sdk.ServerInfo(
                device_comm_state=self.fake_client.server_info.device_comm_state,
                device_session_id=f'new_session_id{i}',     # We change that.
                datalogging=self.fake_client.server_info.datalogging,
                device_link=self.fake_client.server_info.device_link,
                sfd=self.fake_client.server_info.sfd,
                device=DUMMY_DEVICE
            )

            self.wait_events_and_clear([
                EventType.WATCHABLE_INDEX_CHANGED, 
                EventType.SFD_UNLOADED, 
                EventType.DEVICE_DISCONNECTED, 
                EventType.DEVICE_READY, 
                EventType.SFD_LOADED
                ], timeout=1)

            respond_to_download_requests()  # Check for download request. Respond and make sure the events are triggered

        self.fake_client.server_info = None
        self.wait_events_and_clear([
            EventType.WATCHABLE_INDEX_CHANGED, 
            EventType.SFD_UNLOADED, 
            EventType.DEVICE_DISCONNECTED], timeout=1)

        self.server_manager.stop()
        self.wait_server_state(sdk.ServerState.Disconnected)        
        self.assert_events([EventType.SERVER_DISCONNECTED])
    
    def test_schedule_client_request(self):

        class DataContainer:
            callback_called:bool
            retval:Any
            error:Optional[Exception]

            def clear(self):
                self.callback_called = False
                self.retval = None
                self.error = None
            
            def __init__(self):
                self.clear()

        data = DataContainer()
        def ui_callback(retval, error):
            data.callback_called = True
            data.retval = retval
            data.error = error
            
        def func_success(client) -> bool:
            time.sleep(0.5)
            return "hello"

        self.server_manager.schedule_client_request(func_success, ui_callback)
        self.wait_true_with_events(lambda:data.callback_called, 3)

        self.assertEqual(data.retval, "hello")
        self.assertIsNone(data.error)

        def func_fail(client) -> bool:
            time.sleep(0.5)
            raise Exception("potato")
        
        data.clear()

        self.server_manager.schedule_client_request(func_fail, ui_callback)
        self.wait_true_with_events(lambda:data.callback_called, 3)
        self.assertIsNone(data.retval)
        self.assertIsInstance(data.error, Exception)
        self.assertEqual(str(data.error), "potato")
            
