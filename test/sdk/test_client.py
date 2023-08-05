#    test_client.py
#        Test suite for the SDK client
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

import unittest

from scrutiny.core.basic_types import *
from scrutiny.sdk.client import ScrutinyClient
import scrutiny.sdk as sdk
from scrutiny.sdk.watchable_handle import WatchableHandle
import scrutiny.server.datalogging.definitions.device as device_datalogging
from scrutiny.core.variable import Variable as core_Variable
from scrutiny.core.alias import Alias as core_Alias
from scrutiny.core.codecs import Codecs
from scrutiny.core.sfd_storage import SFDStorage
from scrutiny.core.memory_content import MemoryContent

from scrutiny.server.api import API
from scrutiny.server.api import APIConfig
import scrutiny.server.datastore.datastore as datastore
from scrutiny.server.api.websocket_client_handler import WebsocketClientHandler
from scrutiny.server.device.device_handler import DeviceHandler, DeviceStateChangedCallback, RawMemoryReadRequest, RawMemoryWriteRequest

from scrutiny.core.firmware_description import FirmwareDescription
from scrutiny.server.device.links.udp_link import UdpLink
from scrutiny.server.device.links.abstract_link import AbstractLink
import scrutiny.server.device.device_info as server_device
from test.artifacts import get_artifact
from test import ScrutinyUnitTest
import random

import threading
import time
import queue
from functools import partial
from uuid import uuid4
from dataclasses import dataclass
import logging
import traceback
import struct
from datetime import datetime

from typing import *

localhost = "127.0.0.1"


def d2f(d):
    return struct.unpack('f', struct.pack('f', d))[0]


@dataclass
class ReadMemoryLog:
    address: int
    size: int


@dataclass
class WriteMemoryLog:
    address: int
    data: bytes
    mask: Optional[bytes]


@dataclass
class WriteRPVLog:
    rpv_id: int
    data: bytes


class FakeDeviceHandler:
    datastore: "datastore.Datastore"
    link_type: Literal['none', 'udp', 'serial']
    link: AbstractLink
    datalogger_state: device_datalogging.DataloggerState
    device_conn_status: DeviceHandler.ConnectionStatus
    comm_session_id: Optional[str]
    datalogging_completion_ratio: Optional[float]
    device_info: server_device.DeviceInfo
    write_logs: List[Union[WriteMemoryLog, WriteRPVLog]]
    read_logs: List[ReadMemoryLog]
    device_state_change_callbacks: List[DeviceStateChangedCallback]
    read_memory_queue: "queue.Queue[RawMemoryReadRequest]"
    write_memory_queue: "queue.Queue[RawMemoryWriteRequest]"
    fake_mem: MemoryContent

    write_allowed: bool
    read_allowed: bool

    def __init__(self, datastore: "datastore.Datastore"):
        self.datastore = datastore
        self.link_type = 'udp'
        self.link = UdpLink(
            {
                'host': "127.0.0.1",
                "port": 5555
            }
        )
        self.datalogger_state = device_datalogging.DataloggerState.IDLE
        self.datalogging_completion_ratio = None
        self.device_conn_status = DeviceHandler.ConnectionStatus.DISCONNECTED
        self.comm_session_id = None
        self.device_state_change_callbacks = []
        self.set_connection_status(DeviceHandler.ConnectionStatus.CONNECTED_READY)
        self.write_logs = []
        self.read_logs = []

        self.device_info = server_device.DeviceInfo()
        self.device_info.device_id = "xyz"
        self.device_info.display_name = "fake device"
        self.device_info.max_tx_data_size = 256
        self.device_info.max_rx_data_size = 128
        self.device_info.max_bitrate_bps = 10000
        self.device_info.rx_timeout_us = 50
        self.device_info.heartbeat_timeout_us = 5000000
        self.device_info.address_size_bits = 32
        self.device_info.protocol_major = 1
        self.device_info.protocol_minor = 0
        self.device_info.supported_feature_map = {
            'memory_write': True,
            'datalogging': True,
            'user_command': True,
            '_64bits': True
        }
        self.device_info.forbidden_memory_regions = [
            MemoryRegion(0x100000, 128),
            MemoryRegion(0x200000, 256)
        ]
        self.device_info.readonly_memory_regions = [
            MemoryRegion(0x300000, 128),
            MemoryRegion(0x400000, 256)
        ]

        self.device_info.runtime_published_values = []    # Required to have a value for API to consider data valid

        self.device_info.loops = [
            server_device.FixedFreqLoop(10000, "10khz loop", support_datalogging=True),
            server_device.FixedFreqLoop(100, "100hz loop", support_datalogging=False),
            server_device.VariableFreqLoop("variable freq loop", support_datalogging=True)
        ]
        self.write_allowed = True
        self.read_allowed = True
        self.read_memory_queue = queue.Queue()
        self.write_memory_queue = queue.Queue()

        self.fake_mem = MemoryContent()

    def force_all_write_failure(self):
        self.write_allowed = False

    def force_all_read_failure(self):
        self.read_allowed = False

    def get_link_type(self):
        return self.link_type

    def get_comm_link(self):
        return self.link

    def get_device_info(self):
        return self.device_info

    def get_datalogger_state(self):
        return self.datalogger_state

    def get_connection_status(self):
        return self.device_conn_status

    def set_connection_status(self, status: DeviceHandler.ConnectionStatus):
        previous_state = self.device_conn_status
        if status == DeviceHandler.ConnectionStatus.CONNECTED_READY:
            if previous_state != DeviceHandler.ConnectionStatus.CONNECTED_READY:
                self.comm_session_id = uuid4().hex
        else:
            self.comm_session_id = None

        must_call_callbacks = self.device_conn_status != status
        self.device_conn_status = status

        if must_call_callbacks:
            for callback in self.device_state_change_callbacks:
                callback(self.device_conn_status)

    def register_device_state_change_callback(self, callback: DeviceStateChangedCallback) -> None:
        self.device_state_change_callbacks.append(callback)

    def get_comm_session_id(self):
        return self.comm_session_id

    def get_datalogging_acquisition_completion_ratio(self):
        return self.datalogging_completion_ratio

    def process(self):
        update_request = self.datastore.pop_target_update_request()
        if update_request is not None:
            if not self.write_allowed:
                update_request.complete(False)
            else:
                try:
                    entry = update_request.entry
                    if isinstance(entry, datastore.DatastoreAliasEntry):
                        entry = entry.resolve()
                    bitsize = None
                    if isinstance(entry, datastore.DatastoreVariableEntry):
                        bitsize = entry.get_bitsize()
                    value = Codecs.make_value_valid(entry.get_data_type(), update_request.value, bitsize=bitsize)

                    data, mask = entry.encode(value)
                    if isinstance(entry, datastore.DatastoreVariableEntry):
                        self.write_logs.append(WriteMemoryLog(address=entry.get_address(), data=data, mask=mask))
                    elif isinstance(entry, datastore.DatastoreRPVEntry):
                        self.write_logs.append(WriteRPVLog(rpv_id=entry.rpv.id, data=data))
                    else:
                        raise NotImplementedError("Should not happen")

                    entry.set_value_from_data(data)
                    update_request.complete(True)
                except Exception as e:
                    update_request.complete(False)
                    logging.error(str(e))
                    logging.debug(traceback.format_exc())

        while not self.read_memory_queue.empty():
            request = self.read_memory_queue.get()
            self.read_logs.append(ReadMemoryLog(request.address, request.size))
            if not self.read_allowed:
                request.set_completed(False, None, str("Not allowed"))
            else:
                try:
                    data = self.fake_mem.read(request.address, request.size)
                    request.set_completed(True, data)
                except Exception as e:
                    request.set_completed(False, None, str(e))
                    logging.error(str(e))
                    logging.debug(traceback.format_exc())

        while not self.write_memory_queue.empty():
            request = self.write_memory_queue.get()
            self.write_logs.append(WriteMemoryLog(request.address, request.data, None))
            if not self.write_allowed:
                request.set_completed(False, str("Not allowed"))
            else:
                try:
                    data = self.fake_mem.write(request.address, request.data)
                    request.set_completed(True)
                except Exception as e:
                    request.set_completed(False, str(e))
                    logging.error(str(e))
                    logging.debug(traceback.format_exc())

    def read_memory(self, address: int, size: int, callback: Optional[RawMemoryReadRequest]):
        req = RawMemoryReadRequest(
            address=address,
            size=size,
            callback=callback
        )
        self.read_memory_queue.put(req, block=False)
        return req

    def write_memory(self, address: int, data: bytes, callback: Optional[RawMemoryWriteRequest]):
        req = RawMemoryWriteRequest(
            address=address,
            data=data,
            callback=callback
        )
        self.write_memory_queue.put(req, block=False)
        return req


class FakeDataloggingManager:
    def __init__(self, *args, **kwargs):
        pass


class FakeActiveSFDHandler:
    loaded_callbacks: List[Callable]
    unloaded_callbacks: List[Callable]
    loaded_sfd: FirmwareDescription

    def __init__(self, *args, **kwargs):
        self.loaded_callbacks = []
        self.unloaded_callbacks = []
        self.loaded_sfd = FirmwareDescription(get_artifact('test_sfd_1.sfd'))

    def register_sfd_loaded_callback(self, callback):
        self.loaded_callbacks.append(callback)

    def register_sfd_unloaded_callback(self, callback):
        self.unloaded_callbacks.append(callback)

    def load(self, sfd: FirmwareDescription) -> None:
        self.loaded_sfd = sfd
        for cb in self.loaded_callbacks:
            cb(sfd)

    def unload(self) -> None:
        self.loaded_sfd = None
        for cb in self.unloaded_callbacks:
            cb()

    def get_loaded_sfd(self) -> Optional[FirmwareDescription]:
        return self.loaded_sfd


class TestClient(ScrutinyUnitTest):
    datastore: "datastore.Datastore"
    device_handler: FakeDeviceHandler
    datalogging_manager: FakeDataloggingManager
    sfd_handler: FakeActiveSFDHandler
    api: API

    func_queue: "queue.Queue[Callable, threading.Event, float]"
    server_exit_requested: threading.Event
    server_started: threading.Event
    sync_complete: threading.Event
    require_sync: threading.Event
    thread: threading.Thread

    def setUp(self):
        self.func_queue = queue.Queue()
        self.datastore = datastore.Datastore()
        self.fill_datastore()
        self.device_handler = FakeDeviceHandler(self.datastore)
        self.datalogging_manager = FakeDataloggingManager(self.datastore, self.device_handler)
        self.sfd_handler = FakeActiveSFDHandler(device_handler=self.device_handler, datastore=self.datastore)
        api_config: APIConfig = {
            "client_interface_type": 'websocket',
            'client_interface_config': {
                'host': localhost,
                'port': 0
            }
        }
        self.api = API(
            api_config,
            datastore=self.datastore,
            device_handler=self.device_handler,
            sfd_handler=self.sfd_handler,
            datalogging_manager=self.datalogging_manager,
            enable_debug=False)

        self.server_exit_requested = threading.Event()
        self.server_started = threading.Event()
        self.sync_complete = threading.Event()
        self.require_sync = threading.Event()
        self.thread = threading.Thread(target=self.server_thread)
        self.thread.start()
        self.server_started.wait(timeout=1)

        if not self.server_started.is_set():
            raise RuntimeError("Cannot start server")

        port = cast(WebsocketClientHandler, self.api.client_handler).get_port()
        self.client = ScrutinyClient()
        self.client.connect(localhost, port)

    def tearDown(self) -> None:
        self.client.disconnect()
        self.server_exit_requested.set()
        self.thread.join()

    def fill_datastore(self):
        rpv1000 = datastore.DatastoreRPVEntry('/rpv/x1000', RuntimePublishedValue(0x1000, EmbeddedDataType.float32))
        var1 = datastore.DatastoreVariableEntry('/a/b/var1', core_Variable('var1', vartype=EmbeddedDataType.uint32,
                                                path_segments=['a', 'b'], location=0x1234, endianness=Endianness.Little))
        var2 = datastore.DatastoreVariableEntry('/a/b/var2', core_Variable('var2', vartype=EmbeddedDataType.boolean,
                                                path_segments=['a', 'b'], location=0x4568, endianness=Endianness.Little))
        alias_var1 = datastore.DatastoreAliasEntry(core_Alias('/a/b/alias_var1', var1.display_path, var1.get_type()), var1)
        alias_rpv1000 = datastore.DatastoreAliasEntry(core_Alias('/a/b/alias_rpv1000', rpv1000.display_path, rpv1000.get_type()), rpv1000)
        self.datastore.add_entry(rpv1000)
        self.datastore.add_entry(var1)
        self.datastore.add_entry(var2)
        self.datastore.add_entry(alias_var1)
        self.datastore.add_entry(alias_rpv1000)

    def wait_for_server(self, n=2, timeout=2):
        time.sleep(0)
        for i in range(n):
            self.sync_complete.clear()
            self.require_sync.set()
            self.sync_complete.wait(timeout=timeout)
            self.assertFalse(self.require_sync.is_set())

    def wait_true(self, func, timeout=2, error_str=None):
        success = False
        t = time.time()
        while time.time() - t < timeout:
            if func():
                success = True
                break
        if not success:
            if error_str is None:
                error_str = f"function did not return true within {timeout} sec"
            raise TimeoutError(error_str)

    def execute_in_server_thread(self, func, timeout=2, wait=True, delay: float = 0):
        completed = threading.Event()
        self.func_queue.put((func, completed, delay), block=False)
        if wait:
            completed.wait(timeout)

    def set_entry_val(self, path, val):
        self.datastore.get_entry_by_display_path(path).set_value(val)

    def set_value_and_wait_update(self, watchable: WatchableHandle, val: Any, timeout=2):
        counter = watchable.update_counter
        self.execute_in_server_thread(partial(self.set_entry_val, watchable.display_path, val))
        watchable.wait_update(previous_counter=counter, timeout=timeout)

    def server_thread(self):
        self.api.start_listening()
        self.server_started.set()

        try:
            while not self.server_exit_requested.is_set():
                require_sync_before = False
                if self.require_sync.is_set():
                    require_sync_before = True

                if not self.func_queue.empty():
                    func: Callable
                    event: threading.Event
                    delay: float
                    func, event, delay = self.func_queue.get()
                    if delay > 0:
                        time.sleep(delay)
                    func()
                    event.set()

                self.device_handler.process()
                self.api.process()

                if require_sync_before:
                    self.require_sync.clear()
                    self.sync_complete.set()
                time.sleep(0.005)
        finally:
            self.api.close()

    def test_hold_5_sec(self):
        # Make sure the testing environment and all stubbed classes are stable.
        time.sleep(5)

    def test_get_status(self):
        # Make sure we can read the status of the server correctly
        self.client.wait_server_status_update()
        self.assertEqual(self.client.server_state, sdk.ServerState.Connected)
        server_info = self.client.server
        self.assertIsNotNone(server_info)
        assert server_info is not None

        self.assertEqual(server_info.device_comm_state, sdk.DeviceCommState.ConnectedReady)
        self.assertEqual(server_info.device_session_id, self.device_handler.get_comm_session_id())
        self.assertIsNotNone(server_info.device_session_id)

        assert server_info is not None
        self.assertIsNotNone(server_info.device)
        self.assertEqual(server_info.device.device_id, "xyz")
        self.assertEqual(server_info.device.display_name, "fake device")
        self.assertEqual(server_info.device.max_tx_data_size, 256)
        self.assertEqual(server_info.device.max_rx_data_size, 128)
        self.assertEqual(server_info.device.max_bitrate_bps, 10000)
        self.assertEqual(server_info.device.rx_timeout_us, 50)
        self.assertEqual(server_info.device.heartbeat_timeout, 5)
        self.assertEqual(server_info.device.address_size_bits, 32)
        self.assertEqual(server_info.device.protocol_major, 1)
        self.assertEqual(server_info.device.protocol_minor, 0)

        self.assertEqual(server_info.device.supported_features.memory_write, True)
        self.assertEqual(server_info.device.supported_features.datalogging, True)
        self.assertEqual(server_info.device.supported_features.sixtyfour_bits, True)
        self.assertEqual(server_info.device.supported_features.user_command, True)

        self.assertEqual(len(server_info.device.forbidden_memory_regions), 2)
        self.assertEqual(server_info.device.forbidden_memory_regions[0].start, 0x100000)
        self.assertEqual(server_info.device.forbidden_memory_regions[0].end, 0x100000 + 128 - 1)
        self.assertEqual(server_info.device.forbidden_memory_regions[0].size, 128)
        self.assertEqual(server_info.device.forbidden_memory_regions[1].start, 0x200000)
        self.assertEqual(server_info.device.forbidden_memory_regions[1].end, 0x200000 + 256 - 1)
        self.assertEqual(server_info.device.forbidden_memory_regions[1].size, 256)

        self.assertEqual(len(server_info.device.readonly_memory_regions), 2)
        self.assertEqual(server_info.device.readonly_memory_regions[0].start, 0x300000)
        self.assertEqual(server_info.device.readonly_memory_regions[0].end, 0x300000 + 128 - 1)
        self.assertEqual(server_info.device.readonly_memory_regions[0].size, 128)
        self.assertEqual(server_info.device.readonly_memory_regions[1].start, 0x400000)
        self.assertEqual(server_info.device.readonly_memory_regions[1].end, 0x400000 + 256 - 1)
        self.assertEqual(server_info.device.readonly_memory_regions[1].size, 256)

        self.assertEqual(server_info.device_link.type, sdk.DeviceLinkType.UDP)
        self.assertIsInstance(server_info.device_link.config, sdk.UDPLinkConfig)
        assert isinstance(server_info.device_link.config, sdk.UDPLinkConfig)
        self.assertEqual(server_info.device_link.config.host, '127.0.0.1')
        self.assertEqual(server_info.device_link.config.port, 5555)

        self.assertIsNone(server_info.datalogging.completion_ratio)
        self.assertEqual(server_info.datalogging.state, sdk.DataloggerState.Standby)

        self.assertIsNotNone(server_info.sfd)
        assert server_info.sfd is not None
        sfd = FirmwareDescription(get_artifact('test_sfd_1.sfd'))
        self.assertEqual(server_info.sfd.firmware_id, sfd.get_firmware_id_ascii())
        self.assertEqual(server_info.sfd.metadata.author, sfd.metadata['author'])
        self.assertEqual(server_info.sfd.metadata.project_name, sfd.metadata['project_name'])
        self.assertEqual(server_info.sfd.metadata.version, sfd.metadata['version'])

        self.assertEqual(server_info.sfd.metadata.generation_info.python_version, sfd.metadata['generation_info']['python_version'])
        self.assertEqual(server_info.sfd.metadata.generation_info.scrutiny_version, sfd.metadata['generation_info']['scrutiny_version'])
        self.assertEqual(server_info.sfd.metadata.generation_info.system_type, sfd.metadata['generation_info']['system_type'])
        self.assertEqual(server_info.sfd.metadata.generation_info.timestamp, datetime.fromtimestamp(sfd.metadata['generation_info']['time']))

        # Make sure the class is readonly.
        with self.assertRaises(Exception):
            server_info.device = None
        with self.assertRaises(Exception):
            server_info.device.display_name = "hello"
        with self.assertRaises(Exception):
            server_info.datalogging = None
        with self.assertRaises(Exception):
            server_info.datalogging.state = None

        self.client.wait_server_status_update()
        self.assertIsNot(self.client.server, server_info)   # Make sure we have a new object with a new reference.

    def test_fetch_watchable_info(self):
        # Make sure we can correctly read the information about a watchables
        rpv1000 = self.client.watch('/rpv/x1000')
        var1 = self.client.watch('/a/b/var1')
        var2 = self.client.watch('/a/b/var2')
        alias_var1 = self.client.watch('/a/b/alias_var1')
        alias_rpv1000 = self.client.watch('/a/b/alias_rpv1000')

        self.assertEqual(rpv1000.type, sdk.WatchableType.RuntimePublishedValue)
        self.assertEqual(rpv1000.display_path, '/rpv/x1000')
        self.assertEqual(rpv1000.name, 'x1000')
        self.assertEqual(rpv1000.datatype, sdk.EmbeddedDataType.float32)

        self.assertEqual(var1.type, sdk.WatchableType.Variable)
        self.assertEqual(var1.display_path, '/a/b/var1')
        self.assertEqual(var1.name, 'var1')
        self.assertEqual(var1.datatype, sdk.EmbeddedDataType.uint32)

        self.assertEqual(var2.type, sdk.WatchableType.Variable)
        self.assertEqual(var2.display_path, '/a/b/var2')
        self.assertEqual(var2.name, 'var2')
        self.assertEqual(var2.datatype, sdk.EmbeddedDataType.boolean)

        self.assertEqual(alias_var1.type, sdk.WatchableType.Alias)
        self.assertEqual(alias_var1.display_path, '/a/b/alias_var1')
        self.assertEqual(alias_var1.name, 'alias_var1')
        self.assertEqual(alias_var1.datatype, sdk.EmbeddedDataType.uint32)

        self.assertEqual(alias_rpv1000.type, sdk.WatchableType.Alias)
        self.assertEqual(alias_rpv1000.display_path, '/a/b/alias_rpv1000')
        self.assertEqual(alias_rpv1000.name, 'alias_rpv1000')
        self.assertEqual(alias_rpv1000.datatype, sdk.EmbeddedDataType.float32)

    def test_watch_non_existent(self):
        # Make sure we can't watch something that doesn't exist
        with self.assertRaises(sdk.exceptions.OperationFailure):
            self.client.watch('/i/do/not/exist')

    def test_cannot_read_without_first_val(self):
        # Make sure we can't read a watchable until a value is set at least once.
        rpv1000 = self.client.watch('/rpv/x1000')
        with self.assertRaises(sdk.exceptions.InvalidValueError):
            x = rpv1000.value   # Value never set

    def test_read_single_val(self):
        # Make sure we can read the value of a single watchable
        rpv1000 = self.client.watch('/rpv/x1000')

        for i in range(10):
            val = float(i) + 0.5
            self.execute_in_server_thread(partial(self.set_entry_val, '/rpv/x1000', val), wait=False, delay=0.02)
            rpv1000.wait_update()
            self.assertEqual(rpv1000.value, val)

    def test_read_multiple_val(self):
        # Make sure we can read multiple watchables of different types
        rpv1000 = self.client.watch('/rpv/x1000')
        var1 = self.client.watch('/a/b/var1')
        var2 = self.client.watch('/a/b/var2')
        alias_var1 = self.client.watch('/a/b/alias_var1')
        alias_rpv1000 = self.client.watch('/a/b/alias_rpv1000')

        def update_all(vals: Tuple[float, int, bool]):
            self.datastore.get_entry_by_display_path(rpv1000.display_path).set_value(vals[0])
            self.datastore.get_entry_by_display_path(var1.display_path).set_value(vals[1])
            self.datastore.get_entry_by_display_path(var2.display_path).set_value(vals[2])

        for i in range(10):
            vals = (float(i) + 0.5, i * 100, i % 2 == 0)
            self.execute_in_server_thread(partial(update_all, vals), wait=False, delay=0.02)
            self.client.wait_new_value_for_all()
            self.assertEqual(rpv1000.value, vals[0])
            self.assertEqual(var1.value, vals[1])
            self.assertEqual(var2.value, vals[2])
            self.assertEqual(alias_var1.value, vals[1])
            self.assertEqual(alias_rpv1000.value, vals[0])

    def test_write_single_val(self):
        # Make sure we can write a single watchable
        var1 = self.client.watch('/a/b/var1')
        counter = var1.update_counter
        var1.value = 0x789456

        self.assertEqual(var1.value, 0x789456)
        self.assertEqual(len(self.device_handler.write_logs), 1)
        self.assertIsInstance(self.device_handler.write_logs[0], WriteMemoryLog)
        assert isinstance(self.device_handler.write_logs[0], WriteMemoryLog)

        self.assertEqual(self.device_handler.write_logs[0].address, 0x1234)
        self.assertEqual(self.device_handler.write_logs[0].data, bytes(bytearray([0x56, 0x94, 0x78, 0x00])))  # little endian
        self.assertIsNone(self.device_handler.write_logs[0].mask)
        var1.wait_update(previous_counter=counter)
        self.assertEqual(var1.value, 0x789456)

    def test_write_multiple_val(self):
        # Make sure it is possible to write multiple watchables of different types all together
        rpv1000 = self.client.watch('/rpv/x1000')
        var1 = self.client.watch('/a/b/var1')
        var2 = self.client.watch('/a/b/var2')
        alias_var1 = self.client.watch('/a/b/alias_var1')
        alias_rpv1000 = self.client.watch('/a/b/alias_rpv1000')

        # Can prune the test for debug
        do_var1 = True
        do_var2 = True
        do_rpv1000 = True
        do_alias_var1 = True
        do_alias_rpv1000 = True

        # Check the counter to validate the update of the watchable after the write.
        counter_var1 = var1.update_counter
        counter_var2 = var2.update_counter
        counter_rpv1000 = rpv1000.update_counter
        counter_alias_var1 = alias_var1.update_counter
        counter_alias_rpv1000 = alias_rpv1000.update_counter

        if do_var1:
            var1.value = 0x11223344
        if do_var2:
            var2.value = True
        if do_rpv1000:
            rpv1000.value = 3.1415926
        if do_alias_var1:
            alias_var1.value = 0x55667788
        if do_alias_rpv1000:
            alias_rpv1000.value = 1.23456

        index = 0
        if do_var1:
            self.assertIsInstance(self.device_handler.write_logs[index], WriteMemoryLog)
            assert isinstance(self.device_handler.write_logs[index], WriteMemoryLog)
            self.assertEqual(self.device_handler.write_logs[index].address, 0x1234)
            self.assertEqual(self.device_handler.write_logs[index].data, bytes(bytearray([0x44, 0x33, 0x22, 0x11])))  # little endian
            self.assertIsNone(self.device_handler.write_logs[index].mask)
            var1.wait_update(previous_counter=counter_var1)
            index += 1

        if do_var2:
            self.assertIsInstance(self.device_handler.write_logs[index], WriteMemoryLog)
            assert isinstance(self.device_handler.write_logs[index], WriteMemoryLog)
            self.assertEqual(self.device_handler.write_logs[index].address, 0x4568)
            self.assertEqual(self.device_handler.write_logs[index].data, bytes(bytearray([1])))  # little endian
            self.assertIsNone(self.device_handler.write_logs[index].mask)
            var2.wait_update(previous_counter=counter_var2)
            index += 1

        if do_rpv1000:
            self.assertIsInstance(self.device_handler.write_logs[index], WriteRPVLog)
            assert isinstance(self.device_handler.write_logs[index], WriteRPVLog)
            self.assertEqual(self.device_handler.write_logs[index].rpv_id, 0x1000)
            self.assertEqual(self.device_handler.write_logs[index].data, struct.pack('>f', 3.1415926))  # RPVs are always big endian
            rpv1000.wait_update(previous_counter=counter_rpv1000)
            index += 1

        # Alias points to var1
        if do_alias_var1:
            self.assertIsInstance(self.device_handler.write_logs[index], WriteMemoryLog)
            assert isinstance(self.device_handler.write_logs[index], WriteMemoryLog)
            self.assertEqual(self.device_handler.write_logs[index].address, 0x1234)
            self.assertEqual(self.device_handler.write_logs[index].data, bytes(bytearray([0x88, 0x77, 0x66, 0x55])))  # little endian
            self.assertIsNone(self.device_handler.write_logs[index].mask)
            alias_var1.wait_update(previous_counter=counter_alias_var1)
            index += 1

        # Alias points to rpv1000
        if do_alias_rpv1000:
            self.assertIsInstance(self.device_handler.write_logs[index], WriteRPVLog)
            assert isinstance(self.device_handler.write_logs[index], WriteRPVLog)
            self.assertEqual(self.device_handler.write_logs[index].rpv_id, 0x1000)
            self.assertEqual(self.device_handler.write_logs[index].data, struct.pack('>f', 1.23456))  # RPVs are always big endian
            alias_rpv1000.wait_update(previous_counter=counter_alias_rpv1000)
            index += 1

    def test_batch_write(self):
        # We make sure we can write multiple watchable without waiting for each completion before sending the next request
        rpv1000 = self.client.watch('/rpv/x1000')
        var1 = self.client.watch('/a/b/var1')

        with self.client.batch_write(timeout=3):
            rpv1000.value = 1.234
            var1.value = 0x11223344  # Write twice the same var in the batch should cause 2 write operations.
            var1.value = 0x55667788
            rpv1000.value = 2.345
            rpv1000.value = 3.456

            time.sleep(0.2)  # Let time for the server thread to process the request if any is sent by error.
            self.assertEqual(len(self.device_handler.write_logs), 0)    # No write until with __exit__ the with block

        index = 0
        self.assertIsInstance(self.device_handler.write_logs[index], WriteRPVLog)
        assert isinstance(self.device_handler.write_logs[index], WriteRPVLog)
        self.assertEqual(self.device_handler.write_logs[index].rpv_id, 0x1000)
        self.assertEqual(self.device_handler.write_logs[index].data, struct.pack('>f', 1.234))  # RPVs are always big endian
        index += 1

        self.assertIsInstance(self.device_handler.write_logs[index], WriteMemoryLog)
        assert isinstance(self.device_handler.write_logs[index], WriteMemoryLog)
        self.assertEqual(self.device_handler.write_logs[index].address, 0x1234)
        self.assertEqual(self.device_handler.write_logs[index].data, bytes(bytearray([0x44, 0x33, 0x22, 0x11])))  # little endian
        self.assertIsNone(self.device_handler.write_logs[index].mask)
        index += 1

        self.assertIsInstance(self.device_handler.write_logs[index], WriteMemoryLog)
        assert isinstance(self.device_handler.write_logs[index], WriteMemoryLog)
        self.assertEqual(self.device_handler.write_logs[index].address, 0x1234)
        self.assertEqual(self.device_handler.write_logs[index].data, bytes(bytearray([0x88, 0x77, 0x66, 0x55])))  # little endian
        self.assertIsNone(self.device_handler.write_logs[index].mask)
        index += 1

        self.assertIsInstance(self.device_handler.write_logs[index], WriteRPVLog)
        assert isinstance(self.device_handler.write_logs[index], WriteRPVLog)
        self.assertEqual(self.device_handler.write_logs[index].rpv_id, 0x1000)
        self.assertEqual(self.device_handler.write_logs[index].data, struct.pack('>f', 2.345))  # RPVs are always big endian
        index += 1

        self.assertIsInstance(self.device_handler.write_logs[index], WriteRPVLog)
        assert isinstance(self.device_handler.write_logs[index], WriteRPVLog)
        self.assertEqual(self.device_handler.write_logs[index].rpv_id, 0x1000)
        self.assertEqual(self.device_handler.write_logs[index].data, struct.pack('>f', 3.456))  # RPVs are always big endian
        index += 1

    def test_invalidate_watchables_on_device_change(self):
        # Make sure ALL watchables are not usable after the device disconnect and reconnect
        rpv1000 = self.client.watch('/rpv/x1000')
        var1 = self.client.watch('/a/b/var1')
        alias_var1 = self.client.watch('/a/b/alias_var1')

        def disconnect_device():
            self.device_handler.set_connection_status(DeviceHandler.ConnectionStatus.DISCONNECTED)

        def reconnect_device():
            self.device_handler.set_connection_status(DeviceHandler.ConnectionStatus.CONNECTED_READY)

        alias_var1_counter = alias_var1.update_counter
        self.set_value_and_wait_update(rpv1000, 1.234)
        self.set_value_and_wait_update(var1, 0x1234)
        alias_var1.wait_update(previous_counter=alias_var1_counter)

        self.execute_in_server_thread(disconnect_device)
        self.wait_for_server()

        def status_check(commstate):
            return self.client.server.device_comm_state == commstate

        self.wait_true(partial(status_check, sdk.DeviceCommState.Disconnected))

        with self.assertRaises(sdk.exceptions.InvalidValueError):
            rpv1000.value
        with self.assertRaises(sdk.exceptions.InvalidValueError):
            var1.value
        with self.assertRaises(sdk.exceptions.InvalidValueError):
            alias_var1.value

        self.execute_in_server_thread(reconnect_device)
        self.wait_for_server()
        time.sleep(0.1)  # Leave time for our thread to receive the message
        self.wait_true(partial(status_check, sdk.DeviceCommState.ConnectedReady))

        with self.assertRaises(sdk.exceptions.InvalidValueError):
            rpv1000.value
        with self.assertRaises(sdk.exceptions.InvalidValueError):
            var1.value
        with self.assertRaises(sdk.exceptions.InvalidValueError):
            alias_var1.value

    def test_invalidate_watchables_on_sfd_unload(self):
        # Make sure watchables coming from the SFD (variables and aliases) are
        # not usable after the SFD is unloaded on the server side
        self.client.wait_server_status_update()

        rpv1000 = self.client.watch('/rpv/x1000')
        var1 = self.client.watch('/a/b/var1')
        alias_var1 = self.client.watch('/a/b/alias_var1')

        def sfd_loaded_check():
            return self.client.server.sfd is not None

        def sfd_unloaded_check():
            return self.client.server.sfd is None

        def unload_sfd():
            self.sfd_handler.unload()

        def reload_sfd():
            self.sfd_handler.load(FirmwareDescription(get_artifact('test_sfd_1.sfd')))

        alias_var1_counter = alias_var1.update_counter
        self.set_value_and_wait_update(rpv1000, 1.234)
        self.set_value_and_wait_update(var1, 0x1234)
        alias_var1.wait_update(previous_counter=alias_var1_counter)

        self.execute_in_server_thread(unload_sfd)
        self.wait_true(sfd_unloaded_check)

        rpv1000.value   # RPV still accessible

        with self.assertRaises(sdk.exceptions.InvalidValueError):
            var1.value
        with self.assertRaises(sdk.exceptions.InvalidValueError):
            alias_var1.value

        self.execute_in_server_thread(reload_sfd)
        self.wait_true(sfd_loaded_check)

        rpv1000.value
        with self.assertRaises(sdk.exceptions.InvalidValueError):
            var1.value
        with self.assertRaises(sdk.exceptions.InvalidValueError):
            alias_var1.value

    def test_report_write_failure(self):
        var1 = self.client.watch('/a/b/var1')

        def force_write_failure(self: "TestClient"):
            self.device_handler.force_all_write_failure()

        self.execute_in_server_thread(partial(force_write_failure, self))
        with self.assertRaises(sdk.exceptions.OperationFailure):
            var1.value = 0x789456

    def test_unsubscribe_on_unwatch(self):
        var1 = self.client.watch('/a/b/var1')
        self.execute_in_server_thread(partial(self.set_entry_val, var1.display_path, 0x13245678))
        time.sleep(0.5)
        self.assertEqual(var1.value, 0x13245678)
        var1.unwatch()
        update_counter = var1.update_counter
        self.execute_in_server_thread(partial(self.set_entry_val, var1.display_path, 0xabcd1234))
        time.sleep(0.5)
        self.assertEqual(update_counter, var1.update_counter)

        with self.assertRaises(sdk.exceptions.InvalidValueError):
            var1.value

    def test_handle_cannot_be_reused_after_unwatch(self):
        var1 = self.client.watch('/a/b/var1')
        self.execute_in_server_thread(partial(self.set_entry_val, var1.display_path, 0x11111111))
        time.sleep(0.5)
        self.assertEqual(var1.value, 0x11111111)
        var1.unwatch()

        var1_2 = self.client.watch(var1.display_path)
        self.execute_in_server_thread(partial(self.set_entry_val, var1.display_path, 0x22222222))
        time.sleep(0.5)
        self.assertEqual(var1_2.value, 0x22222222)

        # Read and write of the unwatched handle are not possible
        with self.assertRaises(sdk.exceptions.InvalidValueError):
            var1.value
        with self.assertRaises(sdk.exceptions.OperationFailure):
            var1.value = 0x33333333

        # But read and write of new handle is possible and working
        var1_2.value = 0x44444444
        self.assertEqual(var1_2.value, 0x44444444)
        self.assertEqual(self.datastore.get_entry_by_display_path(var1_2.display_path).get_value(), 0x44444444)

    def test_get_installed_sfds(self):
        with SFDStorage.use_temp_folder():
            sfd1 = SFDStorage.install(get_artifact('test_sfd_1.sfd'), ignore_exist=True)
            sfd2 = SFDStorage.install(get_artifact('test_sfd_2.sfd'), ignore_exist=True)

            installed = self.client.get_installed_sfds()
            self.assertEqual(len(installed), 2)
            self.assertIn(sfd1.get_firmware_id_ascii(), installed)
            self.assertIn(sfd2.get_firmware_id_ascii(), installed)

            installed1 = installed[sfd1.get_firmware_id_ascii()]
            installed2 = installed[sfd2.get_firmware_id_ascii()]

            self.assertEqual(installed1.firmware_id, sfd1.get_firmware_id_ascii())
            self.assertEqual(installed1.metadata.author, sfd1.get_metadata()['author'])
            self.assertEqual(installed1.metadata.project_name, sfd1.get_metadata()['project_name'])
            self.assertEqual(installed1.metadata.version, sfd1.get_metadata()['version'])
            self.assertEqual(installed1.metadata.generation_info.python_version, sfd1.get_metadata()['generation_info']['python_version'])
            self.assertEqual(installed1.metadata.generation_info.scrutiny_version, sfd1.get_metadata()['generation_info']['scrutiny_version'])
            self.assertEqual(installed1.metadata.generation_info.system_type, sfd1.get_metadata()['generation_info']['system_type'])
            self.assertEqual(installed1.metadata.generation_info.timestamp, datetime.fromtimestamp(sfd1.get_metadata()['generation_info']['time']))

            self.assertEqual(installed2.firmware_id, sfd2.get_firmware_id_ascii())
            self.assertEqual(installed2.metadata.author, sfd2.get_metadata()['author'])
            self.assertEqual(installed2.metadata.project_name, sfd2.get_metadata()['project_name'])
            self.assertEqual(installed2.metadata.version, sfd2.get_metadata()['version'])
            self.assertEqual(installed2.metadata.generation_info.python_version, sfd2.get_metadata()['generation_info']['python_version'])
            self.assertEqual(installed2.metadata.generation_info.scrutiny_version, sfd2.get_metadata()['generation_info']['scrutiny_version'])
            self.assertEqual(installed2.metadata.generation_info.system_type, sfd2.get_metadata()['generation_info']['system_type'])
            self.assertEqual(installed2.metadata.generation_info.timestamp, datetime.fromtimestamp(sfd2.get_metadata()['generation_info']['time']))

    def test_read_memory(self):
        ref_data = bytes([random.randint(0, 255) for i in range(600)])

        def write_mem():
            self.device_handler.fake_mem.write(0x10000, ref_data)
        self.execute_in_server_thread(write_mem)

        data = self.client.read_memory(0x10000, len(ref_data), timeout=2)
        self.assertEqual(data, ref_data)
        self.assertEqual(len(self.client._memory_read_completion_dict), 0)  # Check internal state is clean

        self.assertEqual(len(self.device_handler.read_logs), 1)

    def test_read_memory_failure(self):
        ref_data = bytes([random.randint(0, 255) for i in range(600)])

        def init_device():
            self.device_handler.force_all_read_failure()
        self.execute_in_server_thread(init_device)

        with self.assertRaises(sdk.exceptions.OperationFailure):
            self.client.read_memory(0x10000, len(ref_data), timeout=2)

    def test_write_memory(self):
        data = bytes([random.randint(0, 255) for i in range(600)])

        self.client.write_memory(0x10000, data, timeout=2)
        read_data = self.device_handler.fake_mem.read(0x10000, len(data))
        self.assertEqual(data, read_data)
        self.assertEqual(len(self.client._memory_write_completion_dict), 0)  # Check internal state is clean

        self.assertEqual(len(self.device_handler.write_logs), 1)

    def test_write_memory_failure(self):

        def init_device():
            self.device_handler.force_all_write_failure()
        self.execute_in_server_thread(init_device)

        with self.assertRaises(sdk.exceptions.OperationFailure):
            data = bytes([random.randint(0, 255) for i in range(600)])
            self.client.write_memory(0x10000, data, timeout=2)


if __name__ == '__main__':
    unittest.main()
