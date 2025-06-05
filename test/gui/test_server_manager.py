#    test_server_manager.py
#        Test suite for the ServerManager
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

from scrutiny import sdk
from scrutiny.gui.core.server_manager import ServerManager, ServerConfig, QtBufferedListener
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from test.gui.fake_sdk_client import FakeSDKClient, StubbedWatchableHandle
from test.gui.base_gui_test import ScrutinyBaseGuiTest, EventType
import time
from test import logger
from scrutiny import tools

from scrutiny.tools.typing import *

# These value are not really used as they are given to a fake client
SERVER_MANAGER_CONFIG = ServerConfig('127.0.0.1', 5555)


DUMMY_DATASET_RPV = {
    '/rpv/rpv1000': sdk.WatchableConfiguration(server_id='rpv_111', watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/rpv/rpv1001': sdk.WatchableConfiguration(server_id='rpv_222', watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None)
}

DUMMY_DATASET_ALIAS = {
    '/alias/xxx/alias1': sdk.WatchableConfiguration(server_id='alias_111', watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/alias/alias2': sdk.WatchableConfiguration(server_id='alias_222', watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/alias/alias3': sdk.WatchableConfiguration(server_id='alias_333', watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None)
}

DUMMY_DATASET_VAR = {
    '/var/xxx/var1': sdk.WatchableConfiguration(server_id='var_111', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/xxx/var2': sdk.WatchableConfiguration(server_id='var_222', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/var3': sdk.WatchableConfiguration(server_id='var_333', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/var4': sdk.WatchableConfiguration(server_id='var_444', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None)
}

DUMMY_DEVICE = sdk.DeviceInfo(
    session_id='12345',
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
        self.registry = WatchableRegistry()
        self.server_manager = ServerManager(
            watchable_registry=self.registry,
            client=self.fake_client
        )    # Inject a stub of the SDK.

        self.server_manager.signals.server_connected.connect(lambda: self.declare_event(EventType.SERVER_CONNECTED))
        self.server_manager.signals.server_disconnected.connect(lambda: self.declare_event(EventType.SERVER_DISCONNECTED))
        self.server_manager.signals.device_ready.connect(lambda: self.declare_event(EventType.DEVICE_READY))
        self.server_manager.signals.device_disconnected.connect(lambda: self.declare_event(EventType.DEVICE_DISCONNECTED))
        self.server_manager.signals.datalogging_state_changed.connect(lambda: self.declare_event(EventType.DATALOGGING_STATE_CHANGED))
        self.server_manager.signals.sfd_loaded.connect(lambda: self.declare_event(EventType.SFD_LOADED))
        self.server_manager.signals.sfd_unloaded.connect(lambda: self.declare_event(EventType.SFD_UNLOADED))
        self.server_manager.signals.registry_changed.connect(lambda: self.declare_event(EventType.WATCHABLE_REGISTRY_CHANGED))

        # These 2 events are treated differently because they run in a dedicated thread and event order cannot be guaranteed
        self.device_info_avail_changed_count = 0

        def increase_device_info_change_count():
            self.device_info_avail_changed_count += 1

        self.sfd_info_avail_changed_count = 0

        def increase_sfd_info_change_count():
            self.sfd_info_avail_changed_count += 1

        self.server_manager.signals.device_info_availability_changed.connect(increase_device_info_change_count)
        self.server_manager.signals.loaded_sfd_availability_changed.connect(increase_sfd_info_change_count)

    def tearDown(self) -> None:
        if self.server_manager.is_running():
            self.server_manager.stop()
            self.wait_true_with_events(lambda: not self.server_manager.is_running() and not self.server_manager.is_stopping(), timeout=1)

        if self.server_manager.is_stopping():
            self.wait_true_with_events(lambda: not self.server_manager.is_stopping(), timeout=1)
        super().tearDown()

    def wait_server_state(self, state: sdk.ServerState, timeout: int = 1) -> None:
        self.wait_equal(self.server_manager.get_server_state, state, 1)

    def test_hold_5_sec(self):
        self.assertFalse(self.server_manager.is_running())
        self.assertEqual(self.server_manager.get_server_state(), sdk.ServerState.Disconnected)
        self.server_manager.start(SERVER_MANAGER_CONFIG)
        self.assertTrue(self.server_manager.is_running())

        self.wait_equal_with_events(self.server_manager.is_running, False, 5, no_assert=True)  # Early exit if it fails

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
            self.wait_events([EventType.SERVER_CONNECTED], timeout=2)
            self.assertEqual(self.server_manager.get_server_state(), sdk.ServerState.Connected)

            self.server_manager.stop()
            self.wait_false_with_events(self.server_manager.is_stopping, 2)
            self.wait_events_and_clear([EventType.SERVER_CONNECTED, EventType.SERVER_DISCONNECTED], timeout=2)
            self.assertEqual(self.server_manager.get_server_state(), sdk.ServerState.Disconnected)
            self.wait_false(self.server_manager.is_running, 1)

    def test_event_device_connect_disconnect(self):

        self.assertCountEqual
        self.assertEqual(self.event_list, [])
        self.server_manager.start(SERVER_MANAGER_CONFIG)

        self.wait_events_and_clear([EventType.SERVER_CONNECTED], timeout=2)
        self.fake_client._simulate_receive_status()  # Load default status

        for i in range(5):
            self.assertIsNone(self.server_manager.get_device_info())
            self.fake_client._simulate_device_connect('session_id1')
            self.wait_events_and_clear([EventType.DEVICE_READY], timeout=2)
            self.wait_equal_with_events(lambda: self.device_info_avail_changed_count, 1, timeout=2)

            self.assertIsNotNone(self.server_manager.get_device_info())

            self.fake_client._simulate_device_disconnect()
            self.wait_events_and_clear([EventType.DEVICE_DISCONNECTED], timeout=2)
            self.wait_equal_with_events(lambda: self.device_info_avail_changed_count, 2, timeout=2)
            self.assertIsNone(self.server_manager.get_device_info())
            self.device_info_avail_changed_count = 0

        self.server_manager.stop()
        self.wait_server_state(sdk.ServerState.Disconnected)
        self.assert_events([EventType.SERVER_DISCONNECTED])
        self.assertEqual(self.device_info_avail_changed_count, 0)
        self.assertEqual(self.sfd_info_avail_changed_count, 0)

    def test_event_device_connect_disconnect_with_sfd(self):
        # Connect the device and load the SFD at the same time. It has a special code path
        self.assertEqual(self.event_list, [])
        self.server_manager.start(SERVER_MANAGER_CONFIG)

        self.wait_events_and_clear([EventType.SERVER_CONNECTED], timeout=2)
        self.fake_client._simulate_receive_status()  # Load default status

        for i in range(5):
            self.assertIsNone(self.server_manager.get_device_info())
            self.assertIsNone(self.server_manager.get_loaded_sfd())
            self.fake_client._simulate_device_connect('session_id1')
            self.fake_client._simulate_sfd_loaded('firmware1')
            self.wait_events_and_clear([EventType.DEVICE_READY, EventType.SFD_LOADED], timeout=2)
            self.wait_equal_with_events(lambda: self.device_info_avail_changed_count, 1, timeout=2)
            self.wait_equal_with_events(lambda: self.sfd_info_avail_changed_count, 1, timeout=2)

            self.assertIsNotNone(self.server_manager.get_device_info())
            self.assertIsNotNone(self.server_manager.get_loaded_sfd())

            self.fake_client._simulate_device_disconnect()
            self.fake_client._simulate_sfd_unloaded()
            self.wait_events_and_clear([EventType.DEVICE_DISCONNECTED, EventType.SFD_UNLOADED], timeout=2)
            self.wait_equal_with_events(lambda: self.device_info_avail_changed_count, 2, timeout=2)
            self.wait_equal_with_events(lambda: self.sfd_info_avail_changed_count, 2, timeout=2)
            self.assertIsNone(self.server_manager.get_device_info())
            self.assertIsNone(self.server_manager.get_loaded_sfd())

            self.device_info_avail_changed_count = 0
            self.sfd_info_avail_changed_count = 0

        self.fake_client.server_info = None
        self.server_manager.stop()
        self.wait_server_state(sdk.ServerState.Disconnected)
        self.assert_events([EventType.SERVER_DISCONNECTED])

    def test_event_datalogger_state_changed(self):
        self.assertCountEqual
        self.assertEqual(self.event_list, [])
        self.server_manager.start(SERVER_MANAGER_CONFIG)

        self.wait_events_and_clear([EventType.SERVER_CONNECTED], timeout=2)
        self.fake_client._simulate_receive_status()  # Load default status

        for i in range(5):
            self.fake_client._simulate_datalogger_state_changed(sdk.DataloggingInfo(sdk.DataloggerState.WaitForTrigger, None))
            self.wait_events_and_clear([EventType.DATALOGGING_STATE_CHANGED], timeout=2)

            self.fake_client._simulate_datalogger_state_changed(sdk.DataloggingInfo(sdk.DataloggerState.Acquiring, 0.5))
            self.wait_events_and_clear([EventType.DATALOGGING_STATE_CHANGED], timeout=2)

            self.fake_client._simulate_datalogger_state_changed(sdk.DataloggingInfo(sdk.DataloggerState.Acquiring, 0.75))
            self.wait_events_and_clear([EventType.DATALOGGING_STATE_CHANGED], timeout=2)

        self.server_manager.stop()
        self.wait_server_state(sdk.ServerState.Disconnected)
        self.assert_events([EventType.SERVER_DISCONNECTED])

    def test_disconnect_on_error(self):
        self.server_manager.start(SERVER_MANAGER_CONFIG)

        self.wait_events_and_clear([EventType.SERVER_CONNECTED], timeout=2)
        self.fake_client._simulate_receive_status()

        self.assertEqual(self.fake_client.get_call_count('disconnect'), 0)
        self.fake_client.server_state = sdk.ServerState.Error

        self.wait_events([EventType.SERVER_DISCONNECTED], timeout=1)
        self.assertFalse(self.server_manager.is_running())
        self.assertEqual(self.fake_client.get_call_count('disconnect'), 1)

    def test_auto_reconnect(self):
        self.server_manager.start(SERVER_MANAGER_CONFIG)
        self.server_manager.RECONNECT_DELAY = 0.2

        self.wait_events_and_clear([EventType.SERVER_CONNECTED], timeout=2)
        self.assertEqual(self.fake_client.get_call_count('connect'), 1)

        for i in range(5):
            self.fake_client.disconnect()
            self.wait_events_and_clear([EventType.SERVER_DISCONNECTED, EventType.SERVER_CONNECTED], timeout=self.server_manager.RECONNECT_DELAY + 1)
            self.assertEqual(self.fake_client.get_call_count('connect'), i + 2)

    def test_auto_retry_connect_on_connect_fail(self):
        self.server_manager.RECONNECT_DELAY = 0.2
        RETRY_COUNT = 3
        self.fake_client.force_connect_fail()
        self.server_manager.start(SERVER_MANAGER_CONFIG)
        self.wait_true(lambda: self.fake_client.get_call_count('connect') >= 1, 1)    # Wait for initial attempt

        n = self.fake_client.get_call_count('connect')  # Should read 1
        t1 = time.perf_counter()
        self.wait_true(lambda: self.fake_client.get_call_count('connect') >= n + RETRY_COUNT,
                       (RETRY_COUNT + 1) * self.server_manager.RECONNECT_DELAY + 1)
        total_time = time.perf_counter() - t1

        self.fake_client.force_connect_fail(False)  # Reenable connection
        self.wait_events([EventType.SERVER_CONNECTED], timeout=self.server_manager.RECONNECT_DELAY + 1)

        # Should be n+RETRY_COUNT+1. Could be more depending on scheduling
        self.assertGreater(self.fake_client.get_call_count('connect'), n + RETRY_COUNT)

        self.assertGreaterEqual(total_time, (RETRY_COUNT - 1) * self.server_manager.RECONNECT_DELAY)
        self.assertLessEqual(total_time, (RETRY_COUNT + 1) * self.server_manager.RECONNECT_DELAY)

    def test_event_device_connect_disconnect_with_data_download(self):
        self.assertEqual(self.event_list, [])
        self.server_manager.start(SERVER_MANAGER_CONFIG)

        self.wait_events_and_clear([EventType.SERVER_CONNECTED], timeout=2)
        self.fake_client._simulate_receive_status()

        nb_loop = 5
        for i in range(nb_loop):
            logger.debug(f"loop={i}")
            cancel_request = i % 2 == 1
            self.fake_client._simulate_device_connect('session_id1')

            self.wait_events_and_clear([EventType.DEVICE_READY], timeout=2)
            calls = self.fake_client.get_download_watchable_list_function_calls()
            self.assertEqual(len(calls), 1)
            req = calls[0].request
            self.assertEqual(calls[0].types, [sdk.WatchableType.RuntimePublishedValue])

            if cancel_request:
                req.cancel()
                self.assertFalse(self.registry.has_data(sdk.WatchableType.RuntimePublishedValue))
                self.assertFalse(self.registry.has_data(sdk.WatchableType.Alias))
                self.assertFalse(self.registry.has_data(sdk.WatchableType.Variable))
            else:
                req._add_data({
                    sdk.WatchableType.RuntimePublishedValue: DUMMY_DATASET_RPV
                }, done=True)
                self.fake_client._complete_success_watchable_list_request(req._request_id)
                self.wait_events_and_clear([EventType.WATCHABLE_REGISTRY_CHANGED], timeout=2)
                self.assertTrue(self.registry.has_data(sdk.WatchableType.RuntimePublishedValue))
                self.assertFalse(self.registry.has_data(sdk.WatchableType.Alias))
                self.assertFalse(self.registry.has_data(sdk.WatchableType.Variable))

            self.fake_client._simulate_device_disconnect()

            if cancel_request:
                expected_events = [EventType.DEVICE_DISCONNECTED]
            else:
                expected_events = [EventType.WATCHABLE_REGISTRY_CHANGED, EventType.DEVICE_DISCONNECTED]
            self.wait_events_and_clear(expected_events, timeout=1, msg=f"cancel_request={cancel_request}")

            self.assertFalse(self.registry.has_data(sdk.WatchableType.RuntimePublishedValue))
            self.assertFalse(self.registry.has_data(sdk.WatchableType.Alias))
            self.assertFalse(self.registry.has_data(sdk.WatchableType.Variable))

        self.fake_client.server_info = None
        self.server_manager.stop()
        self.wait_server_state(sdk.ServerState.Disconnected)
        self.assert_events([EventType.SERVER_DISCONNECTED])

    def test_event_device_connect_disconnect_with_sfd_and_data_download(self):
        # Connect the device and load the SFD at the same time. It has a special code path
        self.assertEqual(self.event_list, [])
        self.server_manager.start(SERVER_MANAGER_CONFIG)

        self.wait_events_and_clear([EventType.SERVER_CONNECTED], timeout=2)
        self.fake_client._simulate_receive_status()

        def respond_to_download_requests(cancel_requests):
            calls = self.fake_client.get_download_watchable_list_function_calls()
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0].types, [sdk.WatchableType.RuntimePublishedValue])
            self.assertCountEqual(calls[1].types, [sdk.WatchableType.Alias, sdk.WatchableType.Variable])
            if sdk.WatchableType.RuntimePublishedValue in calls[0].types:
                rpv_call_registry = 0
                alias_var_call_registry = 1
            else:
                rpv_call_registry = 1
                alias_var_call_registry = 0

            self.assertCountEqual(calls[rpv_call_registry].types, [sdk.WatchableType.RuntimePublishedValue])
            self.assertCountEqual(calls[alias_var_call_registry].types, [sdk.WatchableType.Alias, sdk.WatchableType.Variable])

            req_rpv = calls[rpv_call_registry].request
            req_alias_var = calls[alias_var_call_registry].request

            if cancel_requests:
                req_rpv.cancel()
                req_alias_var.cancel()
            else:
                req_rpv._add_data({
                    sdk.WatchableType.RuntimePublishedValue: DUMMY_DATASET_RPV
                }, done=True)
                self.fake_client._complete_success_watchable_list_request(req_rpv._request_id)
                self.wait_events_and_clear([EventType.WATCHABLE_REGISTRY_CHANGED], timeout=2)

                req_alias_var._add_data({
                    sdk.WatchableType.Alias: DUMMY_DATASET_ALIAS
                }, done=False)
                req_alias_var._add_data({
                    sdk.WatchableType.Variable: DUMMY_DATASET_VAR
                }, done=True)
                self.fake_client._complete_success_watchable_list_request(req_alias_var._request_id)
                self.wait_events_and_clear([EventType.WATCHABLE_REGISTRY_CHANGED], timeout=2)

        for i in range(5):
            logger.debug(f"loop={i}")
            cancel_requests = i % 2 == 1
            self.fake_client._simulate_device_connect('session_id1')
            self.fake_client._simulate_sfd_loaded('firmware1')

            self.wait_events_and_clear([EventType.DEVICE_READY, EventType.SFD_LOADED], timeout=2)
            respond_to_download_requests(cancel_requests)

            self.fake_client._simulate_device_disconnect()  # These event may happen in any order
            self.fake_client._simulate_sfd_unloaded()       # These event may happen in any order

            if cancel_requests:
                expected_events = [EventType.DEVICE_DISCONNECTED, EventType.SFD_UNLOADED]
            else:
                expected_events = [EventType.WATCHABLE_REGISTRY_CHANGED, EventType.DEVICE_DISCONNECTED,
                                   EventType.WATCHABLE_REGISTRY_CHANGED, EventType.SFD_UNLOADED, ]

            self.wait_events_and_clear(expected_events, timeout=1, enforce_order=True)

        self.fake_client.server_info = None
        self.server_manager.stop()
        self.wait_server_state(sdk.ServerState.Disconnected)
        self.assert_events([EventType.SERVER_DISCONNECTED])

    def test_device_disconnect_ready_events_on_session_id_change_with_sfd_and_data_download(self):
        self.assertEqual(self.event_list, [])
        self.server_manager.start(SERVER_MANAGER_CONFIG)

        self.wait_events_and_clear([EventType.SERVER_CONNECTED], timeout=2)
        self.fake_client._simulate_receive_status()

        self.fake_client._simulate_sfd_loaded('fimrware_id1')
        self.fake_client._simulate_device_connect('session_id1')
        self.wait_events_and_clear([EventType.SFD_LOADED, EventType.DEVICE_READY], timeout=2)

        def respond_to_download_requests():
            calls = self.fake_client.get_download_watchable_list_function_calls()
            self.assertEqual(len(calls), 2)
            if sdk.WatchableType.RuntimePublishedValue in calls[0].types:
                rpv_call_registry = 0
                alias_var_call_registry = 1
            else:
                rpv_call_registry = 1
                alias_var_call_registry = 0

            self.assertCountEqual(calls[rpv_call_registry].types, [sdk.WatchableType.RuntimePublishedValue])
            self.assertCountEqual(calls[alias_var_call_registry].types, [sdk.WatchableType.Alias, sdk.WatchableType.Variable])

            req_rpv = calls[rpv_call_registry].request
            req_alias_var = calls[alias_var_call_registry].request

            req_rpv._add_data({
                sdk.WatchableType.RuntimePublishedValue: DUMMY_DATASET_RPV
            }, done=True)
            self.fake_client._complete_success_watchable_list_request(req_rpv._request_id)
            self.wait_events_and_clear([EventType.WATCHABLE_REGISTRY_CHANGED], timeout=2)

            req_alias_var._add_data({
                sdk.WatchableType.Alias: DUMMY_DATASET_ALIAS
            }, done=False)
            req_alias_var._add_data({
                sdk.WatchableType.Variable: DUMMY_DATASET_VAR
            }, done=True)
            self.fake_client._complete_success_watchable_list_request(req_alias_var._request_id)
            self.wait_events_and_clear([EventType.WATCHABLE_REGISTRY_CHANGED], timeout=2)

        respond_to_download_requests()

        self.assertTrue(self.registry.has_data(sdk.WatchableType.RuntimePublishedValue))
        self.assertTrue(self.registry.has_data(sdk.WatchableType.Alias))
        self.assertTrue(self.registry.has_data(sdk.WatchableType.Variable))
        # Only the session ID changes.
        # Should trigger a device disconnected + device ready event.
        for i in range(5):
            self.fake_client._simulate_sfd_unloaded()
            self.fake_client._simulate_device_disconnect()

            self.fake_client._simulate_sfd_loaded('firmware_id')
            self.fake_client._simulate_device_connect(f'new_session_id{i}')

            self.wait_events_and_clear([
                EventType.WATCHABLE_REGISTRY_CHANGED,
                EventType.SFD_UNLOADED,
                EventType.WATCHABLE_REGISTRY_CHANGED,
                EventType.DEVICE_DISCONNECTED,
                EventType.SFD_LOADED,
                EventType.DEVICE_READY,
            ], timeout=1)

            respond_to_download_requests()  # Check for download request. Respond and make sure the events are triggered

        self.fake_client._simulate_sfd_unloaded()
        self.fake_client._simulate_device_disconnect()
        self.fake_client.server_info = None
        self.wait_events_and_clear([
            EventType.WATCHABLE_REGISTRY_CHANGED,
            EventType.SFD_UNLOADED,
            EventType.WATCHABLE_REGISTRY_CHANGED,
            EventType.DEVICE_DISCONNECTED], timeout=1)

        self.server_manager.stop()
        self.wait_server_state(sdk.ServerState.Disconnected)
        self.assert_events([EventType.SERVER_DISCONNECTED])

    def test_schedule_client_request(self):

        class DataContainer:
            callback_called: bool
            retval: Any
            error: Optional[Exception]

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
        self.wait_true_with_events(lambda: data.callback_called, 3)

        self.assertEqual(data.retval, "hello")
        self.assertIsNone(data.error)

        def func_fail(client) -> bool:
            time.sleep(0.5)
            raise Exception("potato")

        data.clear()

        self.server_manager.schedule_client_request(func_fail, ui_callback)
        self.wait_true_with_events(lambda: data.callback_called, 3)
        self.assertIsNone(data.retval)
        self.assertIsInstance(data.error, Exception)
        self.assertEqual(str(data.error), "potato")

    def test_availability_change_on_disconnect(self) -> None:
        self.server_manager.start(SERVER_MANAGER_CONFIG)
        self.wait_events_and_clear([EventType.SERVER_CONNECTED], timeout=2)
        self.fake_client._simulate_receive_status()

        self.assertIsNone(self.server_manager.get_device_info())
        self.fake_client._simulate_device_connect("aaa")
        self.wait_equal_with_events(lambda: self.device_info_avail_changed_count, 1, timeout=2)
        self.assertIsNotNone(self.server_manager.get_device_info())

        self.assertIsNone(self.server_manager.get_loaded_sfd())
        self.fake_client._simulate_sfd_loaded("bbb")
        self.wait_equal_with_events(lambda: self.sfd_info_avail_changed_count, 1, timeout=2)
        self.assertIsNotNone(self.server_manager.get_loaded_sfd())

        self.fake_client.disconnect()
        self.wait_equal_with_events(lambda: self.sfd_info_avail_changed_count, 2, timeout=2)
        self.wait_equal_with_events(lambda: self.device_info_avail_changed_count, 2, timeout=2)
        self.assertIsNone(self.server_manager.get_device_info())
        self.assertIsNone(self.server_manager.get_loaded_sfd())

    def test_availability_change_on_stop(self) -> None:
        self.server_manager.start(SERVER_MANAGER_CONFIG)
        self.wait_events_and_clear([EventType.SERVER_CONNECTED], timeout=2)
        self.fake_client._simulate_receive_status()

        self.assertIsNone(self.server_manager.get_device_info())
        self.fake_client._simulate_device_connect("aaa")
        self.wait_equal_with_events(lambda: self.device_info_avail_changed_count, 1, timeout=2)
        self.assertIsNotNone(self.server_manager.get_device_info())

        self.assertIsNone(self.server_manager.get_loaded_sfd())
        self.fake_client._simulate_sfd_loaded("bbb")
        self.wait_equal_with_events(lambda: self.sfd_info_avail_changed_count, 1, timeout=2)
        self.assertIsNotNone(self.server_manager.get_loaded_sfd())

        self.server_manager.stop()
        self.wait_equal_with_events(lambda: self.sfd_info_avail_changed_count, 2, timeout=2)
        self.wait_equal_with_events(lambda: self.device_info_avail_changed_count, 2, timeout=2)
        self.assertIsNone(self.server_manager.get_device_info())
        self.assertIsNone(self.server_manager.get_loaded_sfd())


class TestServerManagerRegistryInteraction(ScrutinyBaseGuiTest):
    # This test suite make sure that WatchableRegistry watch/unwatch calls correctly triggers
    # watch/unwatch request to the server.
    # The registry is independant from the network. It doesn't wait for server confirmation before returning of a watch/unwatch.
    # The server manager should try to register as long as the number of watcher is greater than 0, and unregister when there is 0 watchers asynchronously.
    # No request stacking should happen. while nb_watcher > 0: keep trying to watch. When nb_watch == 0, stop trying watching and/or keep trying to unwatch

    def setUp(self) -> None:
        super().setUp()
        self.registry = WatchableRegistry()
        self.fake_client = FakeSDKClient()
        self.server_manager = ServerManager(
            watchable_registry=self.registry,  # Real registry
            client=self.fake_client
        )
        self.server_manager._unit_test = True
        self.server_manager.start(SERVER_MANAGER_CONFIG)

        ready = tools.MutableBool(False)

        def ready_slot():
            ready.val = True
        self.server_manager.signals.server_connected.connect(ready_slot)
        self.wait_true_with_events(lambda: ready.val, timeout=1)

    def tearDown(self):
        self.server_manager.stop()
        self.wait_true_with_events(lambda: not self.server_manager.is_running() and not self.server_manager.is_stopping(), timeout=1)
        return super().tearDown()

    def get_watch_request(self, timeout: int = 1, assert_single: bool = True):
        self.wait_true(lambda: len(self.fake_client._pending_watch_request) > 0, timeout=timeout)
        request = self.fake_client._pending_watch_request.pop()
        if assert_single:
            self.assertEqual(len(self.fake_client._pending_watch_request), 0)
        return request

    def get_unwatch_request(self, timeout: int = 1, assert_single: bool = True):
        self.wait_true(lambda: len(self.fake_client._pending_unwatch_request) > 0, timeout=timeout)
        request = self.fake_client._pending_unwatch_request.pop()
        if assert_single:
            self.assertEqual(len(self.fake_client._pending_unwatch_request), 0)
        return request

    def asssert_no_watch_request(self, max_wait: int = 1):
        self.wait_true_with_events(lambda: len(self.fake_client._pending_watch_request) > 0, timeout=max_wait, no_assert=True)
        self.assertEqual(len(self.fake_client._pending_watch_request), 0)

    def asssert_no_unwatch_request(self, max_wait: int = 1):
        self.wait_true_with_events(lambda: len(self.fake_client._pending_unwatch_request) > 0, timeout=max_wait, no_assert=True)
        self.assertEqual(len(self.fake_client._pending_unwatch_request), 0)

    def asssert_no_watch_or_unwatch_request(self, max_wait: int = 1):
        func = lambda: len(self.fake_client._pending_unwatch_request) > 0 or len(self.fake_client._pending_watch_request) > 0
        self.wait_true_with_events(func, timeout=max_wait, no_assert=True)
        self.assertFalse(func())

    def test_no_request_stacking(self):
        # Make sure that we don't queue useless register/unregister/register/unregister sequence if the UI is faster than the network
        self.registry._add_watchable('a/b/c', sdk.WatchableConfiguration(
            datatype=sdk.EmbeddedDataType.float32,
            enum=None,
            server_id='abc',
            watchable_type=sdk.WatchableType.Variable
        ))
        watcher1 = 'watcher1'
        watcher2 = 'watcher2'
        watcher3 = 'watcher3'
        self.registry.register_watcher(watcher1, lambda *x, **y: None, lambda *x, **y: None)
        self.registry.register_watcher(watcher2, lambda *x, **y: None, lambda *x, **y: None)
        self.registry.register_watcher(watcher3, lambda *x, **y: None, lambda *x, **y: None)

        ui_callback_count = self.server_manager._qt_watch_unwatch_ui_callback_call_count

        # Start a new series of watch unwatch.
        self.registry.watch(watcher1, sdk.WatchableType.Variable, 'a/b/c')
        self.registry.unwatch(watcher1, sdk.WatchableType.Variable, 'a/b/c')
        self.registry.watch(watcher1, sdk.WatchableType.Variable, 'a/b/c')
        self.registry.unwatch(watcher1, sdk.WatchableType.Variable, 'a/b/c')
        self.registry.watch(watcher1, sdk.WatchableType.Variable, 'a/b/c')
        self.registry.unwatch(watcher1, sdk.WatchableType.Variable, 'a/b/c')

        watch_request = self.get_watch_request(assert_single=True)
        self.asssert_no_watch_or_unwatch_request(max_wait=0.5)
        self.assertEqual(ui_callback_count, self.server_manager._qt_watch_unwatch_ui_callback_call_count)
        watch_request.simulate_failure()
        self.wait_true_with_events(lambda: self.server_manager._qt_watch_unwatch_ui_callback_call_count != ui_callback_count, timeout=1)
        # watch failed. We have no watcher. Should do nothing more
        self.asssert_no_watch_or_unwatch_request(max_wait=0.5)

        # We are back to 0 watcher.
        # Start a new series of watch unwatch.
        ui_callback_count = self.server_manager._qt_watch_unwatch_ui_callback_call_count
        watchable_config = sdk.WatchableConfiguration('xxx', sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None)
        self.registry.watch(watcher1, sdk.WatchableType.Variable, 'a/b/c')
        self.registry.unwatch(watcher1, sdk.WatchableType.Variable, 'a/b/c')
        self.registry.watch(watcher1, sdk.WatchableType.Variable, 'a/b/c')
        self.registry.unwatch(watcher1, sdk.WatchableType.Variable, 'a/b/c')
        self.registry.watch(watcher1, sdk.WatchableType.Variable, 'a/b/c')
        self.registry.unwatch(watcher1, sdk.WatchableType.Variable, 'a/b/c')

        watch_request = self.get_watch_request(assert_single=True)
        self.asssert_no_watch_or_unwatch_request(max_wait=0.5)
        self.assertEqual(ui_callback_count, self.server_manager._qt_watch_unwatch_ui_callback_call_count)
        watch_request.simulate_success(watchable_config)
        self.wait_true_with_events(lambda: self.server_manager._qt_watch_unwatch_ui_callback_call_count != ui_callback_count, timeout=1)
        # We are supposed to have no watcher. Expect an unwatch request

        unwatch_request = self.get_unwatch_request(assert_single=True)
        unwatch_request.simulate_success()
        self.asssert_no_watch_or_unwatch_request(max_wait=0.5)

    def test_no_stacking_with_multiple_watchers(self):
        self.registry._add_watchable('a/b/c', sdk.WatchableConfiguration(
            datatype=sdk.EmbeddedDataType.float32,
            enum=None,
            server_id='abc',
            watchable_type=sdk.WatchableType.Variable
        ))

        watcher1 = 'watcher1'
        watcher2 = 'watcher2'
        watcher3 = 'watcher3'
        self.registry.register_watcher(watcher1, lambda *x, **y: None, lambda *x, **y: None)
        self.registry.register_watcher(watcher2, lambda *x, **y: None, lambda *x, **y: None)
        self.registry.register_watcher(watcher3, lambda *x, **y: None, lambda *x, **y: None)

        # Watch request comes in faster than network. No server request stacking should happen
        self.registry.watch(watcher1, sdk.WatchableType.Variable, 'a/b/c')
        self.registry.watch(watcher2, sdk.WatchableType.Variable, 'a/b/c')
        self.assertEqual(self.registry.node_watcher_count(sdk.WatchableType.Variable, 'a/b/c'), 2)   # Independant of network request status

        call_count = self.server_manager._qt_watch_unwatch_ui_callback_call_count
        request1 = self.get_watch_request(assert_single=True)
        self.asssert_no_watch_request(max_wait=0.5)  # Should have a single watch request for the 2 watches
        request1.simulate_failure()  # Should stay unwatched
        self.wait_true_with_events(lambda: call_count != self.server_manager._qt_watch_unwatch_ui_callback_call_count, timeout=1)

        self.registry.watch(watcher3, sdk.WatchableType.Variable, 'a/b/c')  # Will trigger a retry

        request2 = self.get_watch_request(assert_single=True)
        self.asssert_no_watch_request(max_wait=0.5)
        some_watchable_config = sdk.WatchableConfiguration(
            server_id='aaa', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None)

        call_count = self.server_manager._qt_watch_unwatch_ui_callback_call_count
        request2.simulate_success(some_watchable_config)
        self.wait_true_with_events(lambda: call_count != self.server_manager._qt_watch_unwatch_ui_callback_call_count, timeout=1)

        # We have 3 watchers here.
        self.assertEqual(self.registry.node_watcher_count(sdk.WatchableType.Variable, 'a/b/c'), 3)
        self.registry.unwatch(watcher1, sdk.WatchableType.Variable, 'a/b/c')    # No effect. 2 remaining
        self.registry.unwatch(watcher2, sdk.WatchableType.Variable, 'a/b/c')    # No effect. 1 remaining

        self.registry.unwatch(watcher3, sdk.WatchableType.Variable, 'a/b/c')  # Should trigger a unwatch to the server
        request1 = self.get_unwatch_request(assert_single=True)
        self.asssert_no_unwatch_request(max_wait=0.5)
        call_count = self.server_manager._qt_watch_unwatch_ui_callback_call_count
        request1.simulate_failure()  # Should stay watched
        self.wait_true_with_events(lambda: call_count != self.server_manager._qt_watch_unwatch_ui_callback_call_count, timeout=1)

        # Registry now consider that watcher3 is not listening, but the client is still subscribed
        # The following watch will cause the registry to consider watcher3 as a watcher, but will not trigger a request to the server
        self.registry.watch(watcher3, sdk.WatchableType.Variable, 'a/b/c')
        self.registry.unwatch(watcher3, sdk.WatchableType.Variable, 'a/b/c')
        request3 = self.get_unwatch_request(assert_single=True)
        self.asssert_no_unwatch_request(max_wait=0.5)

        call_count = self.server_manager._qt_watch_unwatch_ui_callback_call_count
        request3.simulate_success()
        self.wait_true_with_events(lambda: call_count != self.server_manager._qt_watch_unwatch_ui_callback_call_count, timeout=1)

        self.asssert_no_unwatch_request(max_wait=0.5)
        self.assertEqual(self.registry.node_watcher_count(sdk.WatchableType.Variable, 'a/b/c'), 0)

    def test_data_reaches_watchers(self):
        # Simulate a value update broadcast by the client.
        # expect a gui watcher that subscribe to the registry to receive the update
        watch1 = StubbedWatchableHandle(
            display_path='/aaa/bbb/ccc',
            datatype=sdk.EmbeddedDataType.float32,
            enum=None,
            server_id='aaa',
            watchable_type=sdk.WatchableType.Variable
        )
        self.registry._add_watchable(watch1.display_path, watch1.configuration)
        all_updates = []

        def callback(watcher, updates):
            for update in updates:
                all_updates.append(update)

        self.registry.register_watcher('hello', callback, lambda *x, **y: None)
        self.registry.watch('hello', watch1.configuration.watchable_type, watch1.display_path)
        watch1.set_value(1234)
        self.server_manager._listener.subscribe(watch1)

        self.server_manager._listener._broadcast_update([watch1])

        self.wait_true_with_events(lambda: len(all_updates) > 0, timeout=1)
        self.assertEqual(len(all_updates), 1)
        self.assertEqual(all_updates[0].value, 1234)


class TestQtListener(ScrutinyBaseGuiTest):

    def setUp(self):
        super().setUp()
        self.listener = QtBufferedListener()
        self.listener.start()

        self.watch1 = StubbedWatchableHandle(
            display_path='/aaa/bbb/ccc',
            datatype=sdk.EmbeddedDataType.float32,
            enum=None,
            server_id='aaa',
            watchable_type=sdk.WatchableType.Variable
        )
        self.watch2 = StubbedWatchableHandle(
            display_path='/aaa/bbb/ddd',
            datatype=sdk.EmbeddedDataType.float32,
            enum=None,
            server_id='bbb',
            watchable_type=sdk.WatchableType.Alias
        )
        self.watch3 = StubbedWatchableHandle(
            display_path='/aaa/bbb/eee',
            datatype=sdk.EmbeddedDataType.float32,
            enum=None,
            server_id='ccc',
            watchable_type=sdk.WatchableType.RuntimePublishedValue
        )

    def tearDown(self):
        self.listener.stop()
        super().tearDown()

    def test_qt_listener(self):
        self.listener.subscribe(self.watch1)
        self.listener.subscribe(self.watch3)

        data_received = []

        class CounterObj:
            def __init__(self):
                self.count = 0
        counter = CounterObj()

        def callback():
            counter.count += 1
            while not self.listener.to_gui_thread_queue.empty():
                for update in self.listener.to_gui_thread_queue.get_nowait():
                    data_received.append(update)

        self.listener.signals.data_received.connect(callback)

        # Simulate what the client does. Date comes in from the network
        self.listener._broadcast_update([self.watch1, self.watch2, self.watch3])

        self.wait_true_with_events(lambda: len(data_received) >= 2, timeout=1)   # Wait for callback to be called through a QT signal
        self.assertEqual(len(data_received), 2)
        self.assertEqual(counter.count, 1)
        self.assertIs(data_received[0].watchable, self.watch1)
        # watch2 was not subscribed
        self.assertIs(data_received[1].watchable, self.watch3)
        data_received.clear()   # All goo, clear the data for enxt test

        self.assertEqual(self.listener.gui_qsize, 0)    # Nothing is buffered internally.
        self.listener._broadcast_update([self.watch1, self.watch2, self.watch3])
        time.sleep(0.5)
        # We have not authorized the listener to emit a new QT signal. So no callback called.
        self.assertGreater(self.listener.gui_qsize, 0)  # Enqueued, waiting for callback to empty it
        self.assertEqual(len(data_received), 0)
        self.assertEqual(counter.count, 1)
        self.listener.ready_for_next_update()

        # Now that we authorized it, a new QT signal will be emitted so that we empty the gui_queue
        self.wait_true_with_events(lambda: len(data_received) >= 2, timeout=1)
        self.assertEqual(len(data_received), 2)
        self.assertEqual(counter.count, 2)
        self.assertIs(data_received[0].watchable, self.watch1)
        # watch2 was not subscribed
        self.assertIs(data_received[1].watchable, self.watch3)
