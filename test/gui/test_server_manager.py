
from scrutiny import sdk
from scrutiny.gui.server_manager import ServerManager
from test import ScrutinyUnitTest
from test.gui.fake_sdk_client import FakeSDKClient
import time



class TestServerManager(ScrutinyUnitTest):

    def setUp(self) -> None:
        self.server_manager = ServerManager()
        self.server_manager._client = FakeSDKClient()   # Inject a stub of the SDK.
    
    def wait_equal(self, fn, val, timeout, no_assert=False):
        t = time.perf_counter()

        while time.perf_counter() - t < timeout:
            if fn() == val:
                break
            time.sleep(0.01)
        if not no_assert:
            self.assertEqual(fn(), val)
    
    def wait_true(self, fn, timeout, no_assert=False):
        return self.wait_equal(fn, True, timeout, no_assert)

    def wait_true(self, fn, timeout, no_assert=False):
        return self.wait_equal(fn, False, timeout, no_assert)
    

    def test_hold_5_sec(self):
        self.assertFalse(self.server_manager.is_running())
        self.assertEqual(self.server_manager.get_server_state(), sdk.ServerState.Disconnected)
        self.server_manager.start('127.0.0.1', 1234)
        self.assertTrue(self.server_manager.is_running())

        self.wait_equal(self.server_manager.is_running, False, 5, no_assert=True)  # Early exit if it fails
        
        self.assertTrue(self.server_manager.is_running())
        self.assertEqual(self.server_manager.get_server_state(), sdk.ServerState.Connected)
        self.server_manager.stop()
        self.assertFalse(self.server_manager.is_running())
        self.assertEqual(self.server_manager.get_server_state(), sdk.ServerState.Disconnected)

    

    def tearDown(self) -> None:
        self.server_manager.stop()
