import unittest

from scrutiny.sdk import ServerState
from scrutiny.sdk.client import ScrutinyClient
from scrutiny.tools.synchronous_websocket_server import SynchronousWebsocketServer

import threading
import json
import time
import logging
import queue
import functools

localhost = '127.0.0.1'  # CI does not have ipv6


class TestClient(unittest.TestCase):
    def setUp(self) -> None:

        self.connect_count = 0
        self.disconnect_count = 0
        self.last_connect_ws = None
        self.last_disconnect_ws = None
        self.exit_requested = threading.Event()
        self.server_started = threading.Event()
        self.sync_complete = threading.Event()
        self.require_sync = threading.Event()

        self.thread = threading.Thread(target=self.server_thread)
        self.thread.start()
        self.server_started.wait(timeout=1)

        if not self.server_started.is_set():
            raise RuntimeError("Cannot start server")

    def tearDown(self) -> None:
        self.exit_requested.set()

    def wait_for_server(self, n=2):
        time.sleep(0)
        for i in range(n):
            self.sync_complete.clear()
            self.require_sync.set()
            self.sync_complete.wait()
            self.assertFalse(self.require_sync.is_set())

    def server_thread(self):
        self.server = SynchronousWebsocketServer(connect_callback=self.connect_callback, disconnect_callback=self.disconnect_callback)
        self.port = self.server.start(localhost, 0)
        self.server_started.set()
        while not self.exit_requested.is_set():
            require_sync_before = False
            if self.require_sync.is_set():
                require_sync_before = True
            self.server.process()
            if require_sync_before:
                self.require_sync.clear()
                self.sync_complete.set()
            time.sleep(0.005)
        self.server.stop()

    def connect_callback(self, ws):
        self.connect_count += 1
        self.last_connect_ws = ws

    def disconnect_callback(self, ws):
        self.disconnect_count += 1
        self.last_disconnect_ws = ws

    def test_basics_communication(self):
        # Make sure we can connect/disconnect/send/receive.
        # Test is run twice to make sure we can disconnect and reconnect after

        rxq1 = queue.Queue()
        rxq2 = queue.Queue()

        def put_in_queue(q, client, msg):
            q.put(msg)

        client1 = ScrutinyClient(name="client1", rx_message_callbacks=[functools.partial(put_in_queue, rxq1)])
        client2 = ScrutinyClient(name="client2", rx_message_callbacks=[functools.partial(put_in_queue, rxq2)])

        for i in range(2):
            logging.debug(f"Iteration {i}")
            self.connect_count = 0
            self.disconnect_count = 0

            # Make sure we are disconnected
            self.assertEqual(client1.server_state, ServerState.Disconnected)
            self.assertEqual(client2.server_state, ServerState.Disconnected)

            # Connect client1
            logging.debug("Connecting")
            client1.connect(localhost, self.port)
            self.assertEqual(client1.server_state, ServerState.Connected)
            self.assertEqual(client2.server_state, ServerState.Disconnected)
            self.wait_for_server()
            ws1 = self.last_connect_ws

            # Connect client2
            client2.connect(localhost, self.port)
            self.wait_for_server()
            ws2 = self.last_connect_ws
            self.assertEqual(client1.server_state, ServerState.Connected)
            self.assertEqual(client2.server_state, ServerState.Connected)
            self.wait_for_server()
            self.assertEqual(self.connect_count, 2)
            self.assertEqual(self.disconnect_count, 0)

            # Make sure that we have different server websocket references
            self.assertIsNot(ws1, ws2)

            # Sends from client, read from server
            payload1 = {"foo1": "bar1"}
            payload2 = {"foo2": "bar2"}
            client1._send(payload1)
            client2._send(payload2)
            self.wait_for_server()

            for i in range(2):
                self.assertFalse(self.server.rxqueue.empty())
                ws, data = self.server.rxqueue.get()

                if ws is ws1:
                    self.assertEqual(json.loads(data.decode('utf8')), payload1),
                elif ws is ws2:
                    self.assertEqual(json.loads(data.decode('utf8')), payload2),
                else:
                    self.assertTrue(False)

            # Sends from server, reads from client
            logging.debug("Sending")
            payload1 = {"response_foo1": "response_bar1"}
            payload2 = {"response_foo2": "response_bar2"}
            self.server.txqueue.put((ws1, json.dumps(payload1).encode('utf8')))
            self.server.txqueue.put((ws2, json.dumps(payload2).encode('utf8')))

            timeout = 0.5
            tstart = time.time()
            while rxq1.empty() and time.time() - tstart < timeout:
                time.sleep(0.05)

            tstart = time.time()
            while rxq2.empty() and time.time() - tstart < timeout:
                time.sleep(0.05)

            self.assertFalse(rxq1.empty())
            self.assertFalse(rxq2.empty())
            data1 = rxq1.get()
            data2 = rxq2.get()
            self.assertTrue(rxq1.empty())
            self.assertTrue(rxq2.empty())
            self.assertIsNotNone(data1)
            self.assertIsNotNone(data2)
            self.assertEqual(data1, payload1)
            self.assertEqual(data2, payload2)

            # Disconnect all
            logging.debug("Disconnecting")
            client1.disconnect()
            client2.disconnect()
            self.assertEqual(client1.server_state, ServerState.Disconnected)
            self.assertEqual(client2.server_state, ServerState.Disconnected)
            self.wait_for_server()
            self.assertEqual(self.disconnect_count, 2)
            self.assertEqual(self.disconnect_count, 2)
