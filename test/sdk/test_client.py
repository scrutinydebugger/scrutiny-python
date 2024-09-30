#    test_client.py
#        Test suite for the SDK client
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import unittest

from scrutiny.core.basic_types import *
from scrutiny.sdk.watchable_handle import WatchableHandle
import scrutiny.sdk
import scrutiny.sdk.client
from scrutiny.sdk import listeners
import scrutiny.sdk.datalogging
import scrutiny.sdk._api_parser
sdk = scrutiny.sdk
from scrutiny.sdk.client import ScrutinyClient
import scrutiny.server.datalogging.definitions.device as device_datalogging
import scrutiny.server.datalogging.definitions.api as api_datalogging
from scrutiny.core.variable import Variable as core_Variable
from scrutiny.core.alias import Alias as core_Alias
from scrutiny.core.codecs import Codecs
from scrutiny.core.embedded_enum import EmbeddedEnum
from scrutiny.core.sfd_storage import SFDStorage
from scrutiny.core.memory_content import MemoryContent
from scrutiny.server.datalogging.datalogging_storage import DataloggingStorage


from scrutiny.server.api import API
from scrutiny.server.api import APIConfig
import scrutiny.server.datastore.datastore as datastore
from scrutiny.server.api.tcp_client_handler import TCPClientHandler
from scrutiny.server.device.device_handler import DeviceHandler, DeviceStateChangedCallback, RawMemoryReadRequest, RawMemoryWriteRequest, UserCommandCallback
from scrutiny.server.device.submodules.memory_writer import RawMemoryWriteRequestCompletionCallback
from scrutiny.server.device.submodules.memory_reader import RawMemoryReadRequestCompletionCallback

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
from datetime import datetime, timedelta
import signal 

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
    comm_configure_queue: "queue.Queue[Tuple[str, Dict]]"
    write_allowed: bool
    read_allowed: bool
    emulate_datalogging_not_ready: bool
    user_command_requests_queue: "queue.Queue[Tuple[int, bytes]]"

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
        self.ignore_write = False
        self.read_allowed = True
        self.read_memory_queue = queue.Queue()
        self.write_memory_queue = queue.Queue()
        self.comm_configure_queue = queue.Queue()

        self.fake_mem = MemoryContent()
        self.emulate_datalogging_not_ready = False
        self.user_command_requests_queue = queue.Queue()

    def force_all_write_failure(self):
        self.write_allowed = False

    def force_ignore_all_write(self):
        self.ignore_write = True

    def force_all_read_failure(self):
        self.read_allowed = False

    def force_datalogging_not_ready(self):
        self.emulate_datalogging_not_ready = True

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
            if self.ignore_write:
                pass
            elif not self.write_allowed:
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
            if self.ignore_write:
                pass
            elif not self.write_allowed:
                request.set_completed(False, str("Not allowed"))
            else:
                try:
                    data = self.fake_mem.write(request.address, request.data)
                    request.set_completed(True)
                except Exception as e:
                    request.set_completed(False, str(e))
                    logging.error(str(e))
                    logging.debug(traceback.format_exc())

    def read_memory(self, address: int, size: int, callback: Optional[RawMemoryReadRequestCompletionCallback]) -> RawMemoryReadRequest:
        req = RawMemoryReadRequest(
            address=address,
            size=size,
            callback=callback
        )
        self.read_memory_queue.put(req, block=False)
        return req

    def write_memory(self, address: int, data: bytes, callback: Optional[RawMemoryWriteRequestCompletionCallback]) -> RawMemoryWriteRequest:
        req = RawMemoryWriteRequest(
            address=address,
            data=data,
            callback=callback
        )
        self.write_memory_queue.put(req, block=False)
        return req

    def get_datalogging_setup(self) -> Optional[device_datalogging.DataloggingSetup]:
        if self.emulate_datalogging_not_ready:
            return None

        return device_datalogging.DataloggingSetup(
            buffer_size=4096,
            encoding=device_datalogging.Encoding.RAW,
            max_signal_count=32
        )

    def validate_link_config(self, link_type: str, link_config: Dict):
        if link_type == 'udp':
            if link_config['host'] == 'raise':
                raise ValueError("Bad config")

    def configure_comm(self, link_type: str, link_config: Dict = {}) -> None:
        self.comm_configure_queue.put((link_type, link_config))

    def request_user_command(self, subfn: int, data: bytes, callback: UserCommandCallback) -> None:
        self.user_command_requests_queue.put((subfn, data))
        if subfn == 0x10:
            data2 = bytes([x * 10 for x in data])
            callback(True, subfn, data2, None)
        else:
            callback(False, subfn, None, "Unsupported subfunction")


class FakeDataloggingManager:
    datastore: "datastore.Datastore"
    device_handler: FakeDeviceHandler
    acquisition_request_queue: "queue.Queue[Tuple[api_datalogging.AcquisitionRequest, api_datalogging.APIAcquisitionRequestCompletionCallback]]"

    SAMPLING_RATES = [
        api_datalogging.SamplingRate("100Hz", 100, api_datalogging.ExecLoopType.FIXED_FREQ, device_identifier=0),
        api_datalogging.SamplingRate("10KHz", 10000, api_datalogging.ExecLoopType.FIXED_FREQ, device_identifier=1),
        api_datalogging.SamplingRate("Variable", None, api_datalogging.ExecLoopType.VARIABLE_FREQ, device_identifier=2),
    ]

    def __init__(self, datastore, device_handler):
        self.datastore = datastore
        self.device_handler = device_handler
        self.acquisition_request_queue = queue.Queue()

    def get_device_setup(self):
        return self.device_handler.get_datalogging_setup()

    def get_available_sampling_rates(self) -> List[api_datalogging.SamplingRate]:
        rates: List[api_datalogging.SamplingRate] = []

        rates.append(api_datalogging.SamplingRate(
            name="ffloop0",
            rate_type=api_datalogging.ExecLoopType.FIXED_FREQ,
            device_identifier=0,
            frequency=1000
        ))

        rates.append(api_datalogging.SamplingRate(
            name="ffloop1",
            rate_type=api_datalogging.ExecLoopType.FIXED_FREQ,
            device_identifier=1,
            frequency=9999
        ))

        rates.append(api_datalogging.SamplingRate(
            name="vfloop0",
            rate_type=api_datalogging.ExecLoopType.VARIABLE_FREQ,
            device_identifier=2,
            frequency=None
        ))

        return rates

    def is_ready_for_request(self) -> bool:
        return True

    def is_valid_sample_rate_id(self, rate_id: int) -> bool:
        return rate_id in [sr.device_identifier for sr in self.SAMPLING_RATES]

    def get_sampling_rate(self, rate_id: int) -> api_datalogging.SamplingRate:
        candidate: Optional[api_datalogging.SamplingRate] = None
        for sr in self.SAMPLING_RATES:
            if sr.device_identifier == rate_id:
                candidate = sr
                break
        if candidate is None:
            raise ValueError("Cannot find requested sampling rate")
        return candidate

    def request_acquisition(self,
                            request: api_datalogging.AcquisitionRequest,
                            callback: api_datalogging.APIAcquisitionRequestCompletionCallback
                            ) -> None:
        sampling_rate = self.get_sampling_rate(request.rate_identifier)
        if sampling_rate.rate_type == api_datalogging.ExecLoopType.VARIABLE_FREQ and request.x_axis_type == api_datalogging.XAxisType.IdealTime:
            raise ValueError("Cannot use Ideal Time on variable sampling rate")

        if self.device_handler.get_connection_status() != DeviceHandler.ConnectionStatus.CONNECTED_READY:
            raise RuntimeError("No device connected")

        self.acquisition_request_queue.put((request, callback), block=False)


class FakeActiveSFDHandler:
    loaded_callbacks: List[Callable]
    unloaded_callbacks: List[Callable]
    loaded_sfd: Optional[FirmwareDescription]

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
    
    def setUp(self) -> None:
        self.setup_failed = False
        self.func_queue = queue.Queue()
        self.datastore = datastore.Datastore()
        self.fill_datastore()
        self.device_handler = FakeDeviceHandler(self.datastore)
        self.datalogging_manager = FakeDataloggingManager(self.datastore, self.device_handler)
        self.sfd_handler = FakeActiveSFDHandler(device_handler=self.device_handler, datastore=self.datastore)
        api_config: APIConfig = {
            "client_interface_type": 'tcp',
            'client_interface_config': {
                'host': localhost,
                'port': 0
            }
        }
        self.api = API(
            api_config,
            datastore=self.datastore,
            device_handler=self.device_handler,             # type: ignore
            sfd_handler=self.sfd_handler,                   # type: ignore
            datalogging_manager=self.datalogging_manager,   # type: ignore
            enable_debug=False)

        self.api.handle_unexpected_errors = False
        self.server_exit_requested = threading.Event()
        self.server_started = threading.Event()
        self.sync_complete = threading.Event()
        self.require_sync = threading.Event()
        self.rx_rquest_log = []
        self.thread = threading.Thread(target=self.server_thread, daemon=True)
        self.thread.start()
        self.server_started.wait(timeout=1)

        if not self.server_started.is_set():
            raise RuntimeError("Cannot start server")

        port = cast(TCPClientHandler, self.api.client_handler).get_port()
        assert port is not None
        self.client = ScrutinyClient(rx_message_callbacks=[self.log_rx_request])

        try:
            self.client.connect(localhost, port)
        except sdk.exceptions.ScrutinySDKException:
            self.setup_failed = True

    
    def tearDown(self) -> None:
        self.client.disconnect()
        self.server_exit_requested.set()
        self.thread.join()

        if self.setup_failed:
            self.fail("Failed to setup the test")

    def log_rx_request(self, client, o):
        self.rx_rquest_log.append(o)


    def fill_datastore(self):
        rpv1000 = datastore.DatastoreRPVEntry('/rpv/x1000', RuntimePublishedValue(0x1000, EmbeddedDataType.float32))
        var1 = datastore.DatastoreVariableEntry('/a/b/var1', 
            core_Variable('var1', 
                vartype=EmbeddedDataType.uint32,
                path_segments=['a', 'b'], 
                location=0x1234, 
                endianness=Endianness.Little
            )
        )

        var2 = datastore.DatastoreVariableEntry('/a/b/var2', 
            core_Variable('var2', 
                vartype=EmbeddedDataType.boolean,
                path_segments=['a', 'b'], 
                location=0x4568, 
                endianness=Endianness.Little,
            )
        )

        var3_enum= EmbeddedEnum('var3_enum', vals={
            'aaa' : 1, 
            'bbb' : 2,
            'ccc' : 3
        })
        var3 = datastore.DatastoreVariableEntry('/a/b/var3', 
            core_Variable('var3', 
                vartype=EmbeddedDataType.uint8,
                path_segments=['a', 'b'], 
                location=0xAAAA, 
                endianness=Endianness.Little,
                enum=var3_enum
            )
        )

        alias_var1 = datastore.DatastoreAliasEntry(
            aliasdef=core_Alias('/a/b/alias_var1', var1.display_path, var1.get_type()), 
            refentry=var1
        )

        alias_rpv1000 = datastore.DatastoreAliasEntry(
            aliasdef=core_Alias('/a/b/alias_rpv1000', rpv1000.display_path, rpv1000.get_type()), 
            refentry=rpv1000
        )
        
        self.datastore.add_entry(rpv1000)
        self.datastore.add_entry(var1)
        self.datastore.add_entry(var2)
        self.datastore.add_entry(var3)
        self.datastore.add_entry(alias_var1)
        self.datastore.add_entry(alias_rpv1000)

    def wait_for_server(self, n=2, timeout=2):
        time.sleep(0)
        for i in range(n):
            self.sync_complete.clear()
            self.require_sync.set()
            self.sync_complete.wait(timeout=timeout)
            self.assertFalse(self.require_sync.is_set())

    def wait_true(self, func, timeout:float=2, error_str:Optional[str]=None):
        success = False
        t = time.perf_counter()
        while time.perf_counter() - t < timeout:
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
        self.assertEqual(self.client.server_state, sdk.ServerState.Connected)

    def test_read_basic_properties(self):
        self.assertEqual(self.client.hostname, '127.0.0.1')
        self.assertIsInstance(self.client.port, int)
        self.assertIsInstance(self.client.name, str)

    def test_get_status(self):
        # Make sure we can read the status of the server correctly
        self.client.wait_server_status_update()
        self.assertEqual(self.client.server_state, sdk.ServerState.Connected)
        server_info = self.client.get_server_status()
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
        self.assertIsNot(self.client.get_server_status(), server_info)   # Make sure we have a new object with a new reference.

    def test_request_mechanism(self):
        class Obj:
            pass

        o = Obj()
        o.state = None
        o.response = None

        def callback_ok(state, response):
            o.state = state
            o.response = response

        def callback_fail(state, response):
            raise ValueError("I failed!")

        future = self.client._send({'cmd': 'echo', 'payload': 'foo', 'reqid': 1}, callback_ok)
        future.wait()
        self.assertEqual(future.state, sdk.client.CallbackState.OK)
        self.assertEqual(o.state, sdk.client.CallbackState.OK)
        self.assertIsNotNone(o.response)
        self.assertEqual(future.error_str, '')

        future = self.client._send({'cmd': 'echo', 'payload': 'foo', 'reqid': 2}, callback_fail)
        future.wait()
        self.assertEqual(future.state, sdk.client.CallbackState.CallbackError)
        self.assertNotEqual(future.error_str, '')
        self.assertIsNotNone(future.error)

        future = self.client._send({'cmd': 'bad_cmd', 'reqid': 3}, callback_ok, timeout=2)
        future.wait()
        self.assertEqual(future.state, sdk.client.CallbackState.ServerError)
        self.assertEqual(o.state, sdk.client.CallbackState.ServerError)
        self.assertIsNotNone(future.error)
        self.assertNotEqual(future.error_str, '')

        def disable_api():
            self.api.client_handler.force_silent = True

        self.execute_in_server_thread(disable_api)
        future = self.client._send({'cmd': 'echo', 'payload': 'foo', 'reqid': 4}, callback_ok, timeout=2)
        self.assertEqual(future.state, sdk.client.CallbackState.Pending)
        future.wait()
        self.assertEqual(future.state, sdk.client.CallbackState.TimedOut)
        self.assertEqual(o.state, sdk.client.CallbackState.TimedOut)
        self.assertNotEqual(future.error_str, '')

        future = self.client._send({'cmd': 'echo', 'payload': 'foo', 'reqid': 5}, callback_ok, timeout=10)
        self.assertEqual(future.state, sdk.client.CallbackState.Pending)
        self.client.disconnect()
        future.wait()
        self.assertEqual(future.state, sdk.client.CallbackState.Cancelled)
        self.assertNotEqual(future.error_str, '')

    def test_wait_device_ready(self):
        self.device_handler.set_connection_status(DeviceHandler.ConnectionStatus.DISCONNECTED)
        def is_disconnected(client:ScrutinyClient):
            server_info = client.get_server_status()
            return server_info.device_comm_state == sdk.DeviceCommState.Disconnected
        
        self.wait_true(partial(is_disconnected, self.client))
        self.assertEqual(self.client.get_server_status().device_comm_state, sdk.DeviceCommState.Disconnected)

        timeout = 3*ScrutinyClient._UPDATE_SERVER_STATUS_INTERVAL
        t1 = time.perf_counter()
        with self.assertRaises(sdk.exceptions.TimeoutException):
            self.client.wait_device_ready(timeout=timeout)
        t2 = time.perf_counter()
        self.assertGreater(t2-t1, timeout)

        def set_ready(device_handler:FakeDeviceHandler):
            device_handler.set_connection_status(DeviceHandler.ConnectionStatus.CONNECTED_READY)
        self.execute_in_server_thread(partial(set_ready, self.device_handler), wait=True, delay=0.1)
        t1 = time.perf_counter()
        self.client.wait_device_ready(timeout=timeout)
        t2 = time.perf_counter()
        self.assertLessEqual(t2-t1, timeout)
        self.assertEqual(self.client.get_server_status().device_comm_state, sdk.DeviceCommState.ConnectedReady)


    
    def test_fetch_watchable_info(self):
        # Make sure we can correctly read the information about a watchables
        rpv1000 = self.client.watch('/rpv/x1000')
        var1 = self.client.watch('/a/b/var1')
        var2 = self.client.watch('/a/b/var2')
        var3 = self.client.watch('/a/b/var3')
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
        self.assertEqual(var1.has_enum(), False)

        self.assertEqual(var2.type, sdk.WatchableType.Variable)
        self.assertEqual(var2.display_path, '/a/b/var2')
        self.assertEqual(var2.name, 'var2')
        self.assertEqual(var2.datatype, sdk.EmbeddedDataType.boolean)
        self.assertEqual(var2.has_enum(), False)

        self.assertTrue(var3.has_enum())
        enum_var3 = var3.get_enum()
        self.assertEqual(enum_var3.name, 'var3_enum')
        self.assertEqual(len(enum_var3.vals), 3)
        self.assertEqual(enum_var3.vals['aaa'], 1)
        self.assertEqual(enum_var3.vals['bbb'], 2)
        self.assertEqual(enum_var3.vals['ccc'], 3)
        self.assertEqual(var3.parse_enum_val('aaa'), 1)
        self.assertEqual(var3.parse_enum_val('bbb'), 2)
        self.assertEqual(var3.parse_enum_val('ccc'), 3)

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

        # Test with wait_update
        for i in range(10):
            val = float(i) + 0.5
            self.execute_in_server_thread(partial(self.set_entry_val, '/rpv/x1000', val), wait=False, delay=0.02)
            rpv1000.wait_update(2)
            self.assertEqual(rpv1000.value, val)

        # Test with wait_value
        for i in range(10):
            val = float(i) + 0.5
            self.execute_in_server_thread(partial(self.set_entry_val, '/rpv/x1000', val), wait=False, delay=0.02)
            rpv1000.wait_value(val, 2)
            self.assertEqual(rpv1000.value, val)
    
    def test_read_single_val_enum(self):
        # Make sure we can read the value of a single watchable
        var2 = self.client.watch('/a/b/var2')
        self.assertFalse(var2.has_enum())

        with self.assertRaises(sdk.exceptions.InvalidValueError):
            x = var2.value_enum

        var3 = self.client.watch('/a/b/var3')
        self.assertTrue(var3.has_enum())

        expected_enum_val = {
            1: 'aaa',
            2: 'bbb',
            3: 'ccc',
        }

        # Test with wait_update
        for i in range(4):
            val = int(i+1)
            self.execute_in_server_thread(partial(self.set_entry_val, '/a/b/var3', val), wait=False, delay=0.02)
            var3.wait_update(2)
            self.assertEqual(var3.value, val)
            if val < 4:
                self.assertEqual(var3.value_enum, expected_enum_val[val])
            else:
                with self.assertRaises(sdk.exceptions.InvalidValueError):
                    x = var3.value_enum

        # Test with wait_value
        for i in range(3):
            val = int(i+1)
            self.execute_in_server_thread(partial(self.set_entry_val, '/a/b/var3', val), wait=False, delay=0.02)
            var3.wait_value(expected_enum_val[val], 2)
            if val < 4:
                self.assertEqual(var3.value_enum, expected_enum_val[val])
            else:
                with self.assertRaises(sdk.exceptions.InvalidValueError):
                     x = var3.value_enum
                    

    def test_read_multiple_val(self) -> None:

        class TestListener(listeners.BaseListener):
            def receive(self, updates:List[listeners.ValueUpdate])->None:
                pass

        # Make sure we can read multiple watchables of different types
        rpv1000 = self.client.watch('/rpv/x1000')
        var1 = self.client.watch('/a/b/var1')
        var2 = self.client.watch('/a/b/var2')
        alias_var1 = self.client.watch('/a/b/alias_var1')
        alias_rpv1000 = self.client.watch('/a/b/alias_rpv1000')
        
        listener1 = TestListener(name="listener1")
        listener2 = TestListener(name="listener2")
        listener1.subscribe([rpv1000,var1,var2,alias_var1,alias_rpv1000])
        listener2.subscribe([rpv1000,var2,alias_rpv1000])
        self.client.register_listener(listener1)
        self.client.register_listener(listener2)

        def update_all(vals: Tuple[float, int, bool]):
            self.datastore.get_entry_by_display_path(rpv1000.display_path).set_value(vals[0])
            self.datastore.get_entry_by_display_path(var1.display_path).set_value(vals[1])
            self.datastore.get_entry_by_display_path(var2.display_path).set_value(vals[2])

        count = 10
        with listener1.start():
            with listener2.start():
                for i in range(count):
                    vals = (float(i) + 0.5, i * 100, i % 2 == 0)
                    self.execute_in_server_thread(partial(update_all, vals), wait=False, delay=0.02)
                    self.client.wait_new_value_for_all()
                    self.assertEqual(rpv1000.value, vals[0])
                    self.assertEqual(var1.value, vals[1])
                    self.assertEqual(var2.value, vals[2])
                    self.assertEqual(alias_var1.value, vals[1])
                    self.assertEqual(alias_rpv1000.value, vals[0])
        
        self.assertGreaterEqual(listener1.update_count, count)
        self.assertGreaterEqual(listener2.update_count, count)
        self.assertGreaterEqual(listener1.update_count, listener2.update_count)
        self.assertEqual(listener1.drop_count, 0)
        self.assertEqual(listener2.drop_count, 0)

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
        var1.wait_update(previous_counter=counter, timeout=2)
        self.assertEqual(var1.value, 0x789456)

    def test_write_single_val_enum(self):
        # Make sure we can write a single watchable
        var2 = self.client.watch('/a/b/var2')
        var3 = self.client.watch('/a/b/var3')
        self.assertFalse(var2.has_enum())
        
        with self.assertRaises(sdk.exceptions.ScrutinySDKException):
            var2.value = 'bbb'   # No enum 

        self.assertTrue(var3.has_enum())
        counter = var3.update_counter
        var3.value_enum = 'ccc'
        self.assertEqual(var3.value, 3)
        self.assertEqual(len(self.device_handler.write_logs), 1)
        self.assertIsInstance(self.device_handler.write_logs[0], WriteMemoryLog)
        assert isinstance(self.device_handler.write_logs[0], WriteMemoryLog)

        self.assertEqual(self.device_handler.write_logs[0].address, 0xAAAA)
        self.assertEqual(self.device_handler.write_logs[0].data, bytes(bytearray([3])))
        self.assertIsNone(self.device_handler.write_logs[0].mask)
        var3.wait_update(previous_counter=counter, timeout=2)
        self.assertEqual(var3.value, 3)

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
            var1.wait_update(previous_counter=counter_var1, timeout=2)
            index += 1

        if do_var2:
            self.assertIsInstance(self.device_handler.write_logs[index], WriteMemoryLog)
            assert isinstance(self.device_handler.write_logs[index], WriteMemoryLog)
            self.assertEqual(self.device_handler.write_logs[index].address, 0x4568)
            self.assertEqual(self.device_handler.write_logs[index].data, bytes(bytearray([1])))  # little endian
            self.assertIsNone(self.device_handler.write_logs[index].mask)
            var2.wait_update(previous_counter=counter_var2, timeout=2)
            index += 1

        if do_rpv1000:
            self.assertIsInstance(self.device_handler.write_logs[index], WriteRPVLog)
            assert isinstance(self.device_handler.write_logs[index], WriteRPVLog)
            self.assertEqual(self.device_handler.write_logs[index].rpv_id, 0x1000)
            self.assertEqual(self.device_handler.write_logs[index].data, struct.pack('>f', 3.1415926))  # RPVs are always big endian
            rpv1000.wait_update(previous_counter=counter_rpv1000, timeout=2)
            index += 1

        # Alias points to var1
        if do_alias_var1:
            self.assertIsInstance(self.device_handler.write_logs[index], WriteMemoryLog)
            assert isinstance(self.device_handler.write_logs[index], WriteMemoryLog)
            self.assertEqual(self.device_handler.write_logs[index].address, 0x1234)
            self.assertEqual(self.device_handler.write_logs[index].data, bytes(bytearray([0x88, 0x77, 0x66, 0x55])))  # little endian
            self.assertIsNone(self.device_handler.write_logs[index].mask)
            alias_var1.wait_update(previous_counter=counter_alias_var1, timeout=2)
            index += 1

        # Alias points to rpv1000
        if do_alias_rpv1000:
            self.assertIsInstance(self.device_handler.write_logs[index], WriteRPVLog)
            assert isinstance(self.device_handler.write_logs[index], WriteRPVLog)
            self.assertEqual(self.device_handler.write_logs[index].rpv_id, 0x1000)
            self.assertEqual(self.device_handler.write_logs[index].data, struct.pack('>f', 1.23456))  # RPVs are always big endian
            alias_rpv1000.wait_update(previous_counter=counter_alias_rpv1000, timeout=2)
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

        self.assertFalse(self.client._is_batch_write_in_progress())

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
        alias_var1.wait_update(previous_counter=alias_var1_counter, timeout=2)

        self.execute_in_server_thread(disconnect_device)
        self.wait_for_server()

        def status_check(commstate):
            return self.client.get_server_status().device_comm_state == commstate

        self.wait_true(partial(status_check, sdk.DeviceCommState.Disconnected))
        time.sleep(0.1)

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
            return self.client.get_server_status().sfd is not None

        def sfd_unloaded_check():
            return self.client.get_server_status().sfd is None

        def unload_sfd():
            self.sfd_handler.unload()

        def reload_sfd():
            self.sfd_handler.load(FirmwareDescription(get_artifact('test_sfd_1.sfd')))

        alias_var1_counter = alias_var1.update_counter
        self.set_value_and_wait_update(rpv1000, 1.234)
        self.set_value_and_wait_update(var1, 0x1234)
        alias_var1.wait_update(previous_counter=alias_var1_counter, timeout=2)

        self.execute_in_server_thread(unload_sfd)
        self.wait_true(sfd_unloaded_check)
        self.client.wait_process()

        rpv1000.value   # RPV still accessible

        with self.assertRaises(sdk.exceptions.InvalidValueError):
            var1.value
        with self.assertRaises(sdk.exceptions.InvalidValueError):
            alias_var1.value

        self.execute_in_server_thread(reload_sfd)
        self.wait_true(sfd_loaded_check)
        self.client.wait_process()

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

    def test_simple_request_response_timeout(self):
        with SFDStorage.use_temp_folder():
            SFDStorage.install(get_artifact('test_sfd_1.sfd'), ignore_exist=True)
            SFDStorage.install(get_artifact('test_sfd_2.sfd'), ignore_exist=True)

            def disable_api():
                self.api.client_handler.force_silent = True  # Hook to force the API to never respond
            self.execute_in_server_thread(disable_api)

            with self.assertRaises(sdk.exceptions.OperationFailure):
                self.client.get_installed_sfds()

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

    def test_write_memory_implicit_failure(self):

        def init_device():
            self.device_handler.force_ignore_all_write()
        self.execute_in_server_thread(init_device)

        with self.assertRaises(sdk.exceptions.OperationFailure):
            data = bytes([random.randint(0, 255) for i in range(50)])
            self.client.write_memory(0x10000, data, timeout=3)

        self.assertEqual(len(self.client._pending_api_batch_writes), 0)  # Check internal state.

    def test_write_memory_explicit_failure(self):

        def init_device():
            self.device_handler.force_all_write_failure()
        self.execute_in_server_thread(init_device)

        with self.assertRaises(sdk.exceptions.OperationFailure):
            data = bytes([random.randint(0, 255) for i in range(600)])
            self.client.write_memory(0x10000, data, timeout=2)

    def test_remove_old_batch_request(self):
        # this is an internal state test, not a functionality test. May break if implementation changes
        rpv1000 = self.client.watch('/rpv/x1000')
        fake_batch_request = scrutiny.sdk.client.PendingAPIBatchWrite(
            {1: sdk.client.WriteRequest(rpv1000, 123)},
            sdk._api_parser.WriteConfirmation('fake_token', 1),
            creation_perf_timestamp=time.perf_counter(),
            timeout=2
        )
        self.client._pending_api_batch_writes['fake_token'] = fake_batch_request
        self.assertEqual(len(self.client._pending_api_batch_writes), 1)
        time.sleep(2)

        def is_cleared():
            return len(self.client._pending_api_batch_writes) == 0

        self.wait_true(is_cleared, 2)
        self.assertEqual(len(self.client._pending_api_batch_writes), 0)

    def test_read_datalogging_capabilities(self):
        capabilities = self.client.get_datalogging_capabilities()

        self.assertEqual(capabilities.buffer_size, 4096)
        self.assertEqual(capabilities.max_nb_signal, 32)
        self.assertEqual(capabilities.encoding, sdk.datalogging.DataloggingEncoding.RAW)
        self.assertEqual(len(capabilities.sampling_rates), 3)

        self.assertIsInstance(capabilities.sampling_rates[0], sdk.datalogging.FixedFreqSamplingRate)
        assert isinstance(capabilities.sampling_rates[0], sdk.datalogging.FixedFreqSamplingRate)
        self.assertEqual(capabilities.sampling_rates[0].identifier, 0)
        self.assertEqual(capabilities.sampling_rates[0].name, 'ffloop0')
        self.assertEqual(capabilities.sampling_rates[0].frequency, 1000)

        self.assertIsInstance(capabilities.sampling_rates[1], sdk.datalogging.FixedFreqSamplingRate)
        assert isinstance(capabilities.sampling_rates[1], sdk.datalogging.FixedFreqSamplingRate)
        self.assertEqual(capabilities.sampling_rates[1].identifier, 1)
        self.assertEqual(capabilities.sampling_rates[1].name, 'ffloop1')
        self.assertEqual(capabilities.sampling_rates[1].frequency, 9999)

        self.assertIsInstance(capabilities.sampling_rates[2], sdk.datalogging.VariableFreqSamplingRate)
        assert isinstance(capabilities.sampling_rates[2], sdk.datalogging.VariableFreqSamplingRate)
        self.assertEqual(capabilities.sampling_rates[2].identifier, 2)
        self.assertEqual(capabilities.sampling_rates[2].name, 'vfloop0')

    def test_read_datalogging_capabilities_not_available(self):
        self.device_handler.force_datalogging_not_ready()

        with self.assertRaises(sdk.exceptions.OperationFailure):
            self.client.get_datalogging_capabilities()

    def test_read_datalogging_acquisition(self):
        with DataloggingStorage.use_temp_storage():
            reference_id = 'foo.bar.baz'
            acq = sdk.datalogging.DataloggingAcquisition(
                firmware_id='foo',
                reference_id=reference_id,
                acq_time=datetime.now(),
                name="test acquisition"
            )
            axis1 = sdk.datalogging.AxisDefinition("Axis1", 0)
            axis2 = sdk.datalogging.AxisDefinition("Axis2", 1)

            xdata = sdk.datalogging.DataSeries([0, 10, 20, 30, 40, 50], "x-axis", "my/xaxis")
            ds1 = sdk.datalogging.DataSeries([-1, -0.5, 0, 0.5, 1], "data1", "path/to/data1")
            ds2 = sdk.datalogging.DataSeries([-10, -5, 0, 5, 10], "data2", "path/to/data2")
            ds3 = sdk.datalogging.DataSeries([0.1, 0.2, 0.3, 0.1, 0.2], "data3", "path/to/data3")
            acq.set_xdata(xdata)
            acq.add_data(ds1, axis1)
            acq.add_data(ds2, axis1)
            acq.add_data(ds3, axis2)
            acq.set_trigger_index(3)

            DataloggingStorage.save(acq)

            acq2 = self.client.read_datalogging_acquisition(reference_id)

            self.assertIsNot(acq, acq2)
            self.assertEqual(acq2.reference_id, acq.reference_id)
            self.assertEqual(acq2.firmware_id, acq.firmware_id)
            self.assertEqual(acq2.name, acq.name)
            self.assertEqual(acq2.firmware_id, acq.firmware_id)
            self.assertEqual(acq2.trigger_index, acq.trigger_index)
            self.assertLessEqual(abs(acq2.acq_time - acq.acq_time), timedelta(seconds=1))

            self.assertEqual(acq2.xdata.name, acq.xdata.name)
            self.assertEqual(acq2.xdata.logged_element, acq.xdata.logged_element)
            self.assertEqual(acq2.xdata.get_data(), acq.xdata.get_data())

            data2 = acq2.get_data()
            data1 = acq.get_data()

            self.assertEqual(len(data2), len(data1))

            data1.sort(key=lambda x: x.series.name)
            data2.sort(key=lambda x: x.series.name)

            for i in range(len(data1)):
                self.assertEqual(data1[i].axis.name, data2[i].axis.name)
                self.assertEqual(data1[i].axis.axis_id, data2[i].axis.axis_id)

                self.assertEqual(data1[i].series.name, data2[i].series.name)
                self.assertEqual(data1[i].series.logged_element, data2[i].series.logged_element)
                self.assertEqual(data1[i].series.get_data(), data2[i].series.get_data())

    def test_request_datalogging_acquisition(self):
        var1 = self.client.watch('/a/b/var1')
        var2 = self.client.watch('/a/b/var2')

        config = sdk.datalogging.DataloggingConfig(sampling_rate=0, decimation=1, timeout=0, name="unittest")
        config.configure_trigger(sdk.datalogging.TriggerCondition.Equal, [var1, 3.14159], position=0.75, hold_time=0)
        config.configure_xaxis(sdk.datalogging.XAxisType.MeasuredTime)
        axis1 = config.add_axis('Axis 1')
        axis2 = config.add_axis('Axis 2')
        config.add_signal(var1, axis1, name="MyVar1")
        config.add_signal(var2, axis1, name="MyVar2")
        config.add_signal('/a/b/alias_rpv1000', axis2, name="MyAliasRPV1000")

        request = self.client.start_datalog(config)
        self.assertFalse(request.completed)
        self.assertFalse(request.is_success)
        self.assertIsNone(request.completion_datetime)

        def check_request_arrived():
            return not self.datalogging_manager.acquisition_request_queue.empty()
        self.wait_true(check_request_arrived)

        server_request, callback = self.datalogging_manager.acquisition_request_queue.get(block=False)

        self.assertEqual(server_request.name, config._name)
        self.assertEqual(server_request.decimation, config._decimation)
        self.assertEqual(server_request.timeout, config._timeout)
        self.assertEqual(server_request.rate_identifier, config._sampling_rate)

        self.assertEqual(server_request.probe_location, config._trigger_position)
        self.assertEqual(server_request.trigger_hold_time, config._trigger_hold_time)
        self.assertEqual(server_request.trigger_condition.condition_id, device_datalogging.TriggerConditionID.Equal)
        self.assertEqual(len(server_request.trigger_condition.operands), 2)
        self.assertEqual(server_request.trigger_condition.operands[0].type, api_datalogging.TriggerConditionOperandType.WATCHABLE)
        self.assertIsInstance(server_request.trigger_condition.operands[0].value, datastore.DatastoreEntry)
        assert isinstance(server_request.trigger_condition.operands[0].value, datastore.DatastoreEntry)
        self.assertEqual(server_request.trigger_condition.operands[0].value.get_display_path(), var1.display_path)
        self.assertEqual(server_request.trigger_condition.operands[1].type, api_datalogging.TriggerConditionOperandType.LITERAL)
        self.assertEqual(server_request.trigger_condition.operands[1].value, 3.14159)

        self.assertEqual(server_request.x_axis_type, api_datalogging.XAxisType.MeasuredTime)
        self.assertCountEqual(server_request.get_yaxis_list(), [api_datalogging.AxisDefinition(
            "Axis 1", 0), api_datalogging.AxisDefinition("Axis 2", 1)])

        expected_signals = []
        expected_signals.append(api_datalogging.SignalDefinitionWithAxis(
            name='MyVar1',
            entry=self.datastore.get_entry_by_display_path(var1.display_path),
            axis=api_datalogging.AxisDefinition(name='Axis 1', axis_id=0))
        )
        expected_signals.append(api_datalogging.SignalDefinitionWithAxis(
            name='MyVar2',
            entry=self.datastore.get_entry_by_display_path(var2.display_path),
            axis=api_datalogging.AxisDefinition(name='Axis 1', axis_id=0))
        )
        expected_signals.append(api_datalogging.SignalDefinitionWithAxis(
            name='MyAliasRPV1000',
            entry=self.datastore.get_entry_by_display_path('/a/b/alias_rpv1000'),
            axis=api_datalogging.AxisDefinition(name='Axis 2', axis_id=1))
        )
        self.assertCountEqual(server_request.signals, expected_signals)
        now = datetime.now()

        def make_acquisition():
            acquisition = sdk.datalogging.DataloggingAcquisition(
                firmware_id='firmware abc',
                reference_id="xyz",
                acq_time=now,
                name=server_request.name)

            axis1 = sdk.datalogging.AxisDefinition(name='Axis 1', axis_id=0)
            axis2 = sdk.datalogging.AxisDefinition(name='Axis 2', axis_id=1)

            ds1 = sdk.datalogging.DataSeries(
                data=[random.random() for x in range(10)],
                name=server_request.signals[0].name,
                logged_element=server_request.signals[0].entry.get_display_path()
            )
            ds2 = sdk.datalogging.DataSeries(
                data=[random.random() for x in range(10)],
                name=server_request.signals[1].name,
                logged_element=server_request.signals[1].entry.get_display_path()
            )
            ds3 = sdk.datalogging.DataSeries(
                data=[random.random() for x in range(10)],
                name=server_request.signals[2].name,
                logged_element=server_request.signals[2].entry.get_display_path()
            )
            acquisition.add_data(ds1, axis1)
            acquisition.add_data(ds2, axis1)
            acquisition.add_data(ds3, axis2)

            acquisition.set_xdata(sdk.datalogging.DataSeries([x for x in range(10)], name="time", logged_element='measured time'))
            acquisition.set_trigger_index(4)
            return acquisition

        with DataloggingStorage.use_temp_storage():
            acquisition = make_acquisition()
            DataloggingStorage.save(acquisition)

            with self.assertRaises(sdk.exceptions.OperationFailure):
                request.fetch_acquisition()

            def complete_acquisition():
                callback(True, "dummy msg", acquisition)
            self.execute_in_server_thread(complete_acquisition)
            request.wait_for_completion(timeout=3)
            self.assertTrue(request.completed)
            self.assertTrue(request.is_success)
            self.assertIsNotNone(request.completion_datetime)
            self.assertEqual(request.acquisition_reference_id, "xyz")
            self.assertEqual(len(self.client._pending_datalogging_requests), 0)  # Check internal state

            acquisition2 = request.fetch_acquisition()

        self.assert_acquisition_valid(acquisition)
        self.assert_acquisition_valid(acquisition2)

        self.assert_acquisition_identical(acquisition, acquisition2)

    def test_request_datalogging_failures(self):
        with self.assertRaises(TypeError):
            self.client.start_datalog("asd")

        var1 = self.client.watch('/a/b/var1')
        config = sdk.datalogging.DataloggingConfig(sampling_rate=0, decimation=1, timeout=0, name="unittest")
        config.configure_trigger(sdk.datalogging.TriggerCondition.Equal, [var1, 3.14159], position=0.75, hold_time=0)
        axis1 = config.add_axis('Axis 1')
        config.add_signal(var1, axis1, name="MyVar1")

        request = self.client.start_datalog(config)

        def check_request_arrived():
            return not self.datalogging_manager.acquisition_request_queue.empty()
        self.wait_true(check_request_arrived)
        server_request, callback = self.datalogging_manager.acquisition_request_queue.get(block=False)
        self.assertIsNotNone(server_request)

        def complete_acquisition():
            callback(False, "An error occurred", None)
        self.execute_in_server_thread(complete_acquisition)
        with self.assertRaises(sdk.exceptions.OperationFailure):
            request.wait_for_completion(timeout=3)

    def test_list_stored_datalogging_acquisitions(self):
        now = datetime.now()

        with DataloggingStorage.use_temp_storage():
            with SFDStorage.use_temp_folder():
                acquisitions = self.client.list_stored_datalogging_acquisitions()
                self.assertEqual(len(acquisitions), 0)

                sfd1_filename = get_artifact('test_sfd_1.sfd')
                sfd2_filename = get_artifact('test_sfd_2.sfd')
                sfd1 = SFDStorage.install(sfd1_filename, ignore_exist=True)
                sfd2 = SFDStorage.install(sfd2_filename, ignore_exist=True)

                acquisition = sdk.datalogging.DataloggingAcquisition(
                    firmware_id=sfd1.get_firmware_id_ascii(),
                    reference_id="refid1",
                    acq_time=now,
                    name="my_acq")
                axis1 = sdk.datalogging.AxisDefinition(name='Axis 1', axis_id=0)
                ds1 = sdk.datalogging.DataSeries(
                    data=[random.random() for x in range(10)],
                    name='ds1_name',
                    logged_element='ds1_element'
                )
                acquisition.add_data(ds1, axis1)
                acquisition.set_xdata(sdk.datalogging.DataSeries([x for x in range(10)], name="time", logged_element='measured time'))
                acquisition.set_trigger_index(4)

                acquisition2 = sdk.datalogging.DataloggingAcquisition(
                    firmware_id=sfd2.get_firmware_id_ascii(),
                    reference_id="refid2",
                    acq_time=now,
                    name="my_acq")
                axis1 = sdk.datalogging.AxisDefinition(name='Axis 1', axis_id=0)
                ds1 = sdk.datalogging.DataSeries(
                    data=[random.random() for x in range(10)],
                    name='ds1_name',
                    logged_element='ds1_element'
                )
                acquisition2.add_data(ds1, axis1)
                acquisition2.set_xdata(sdk.datalogging.DataSeries([x for x in range(10)], name="time", logged_element='measured time'))
                acquisition2.set_trigger_index(4)

                DataloggingStorage.save(acquisition)
                DataloggingStorage.save(acquisition2)

                acquisitions = self.client.list_stored_datalogging_acquisitions()
                self.assertEqual(len(acquisitions), 2)

                expected_data = [
                    dict(firmware_id=sfd1.get_firmware_id_ascii(), reference_id='refid1'),
                    dict(firmware_id=sfd2.get_firmware_id_ascii(), reference_id='refid2')
                ]

                received_data = [dict(firmware_id=x.firmware_id, reference_id=x.reference_id) for x in acquisitions]

                self.assertCountEqual(expected_data, received_data)

    def test_datalog_fails_on_server_disconnect(self):
        var1 = self.client.watch('/a/b/var1')
        var2 = self.client.watch('/a/b/var2')

        config = sdk.datalogging.DataloggingConfig(sampling_rate=0, decimation=1, timeout=0, name="unittest")
        config.configure_trigger(sdk.datalogging.TriggerCondition.Equal, [var1, 3.14159], position=0.75, hold_time=0)
        config.configure_xaxis(sdk.datalogging.XAxisType.MeasuredTime)
        axis1 = config.add_axis('Axis 1')
        axis2 = config.add_axis('Axis 2')
        config.add_signal(var1, axis1, name="MyVar1")
        config.add_signal(var2, axis1, name="MyVar2")
        config.add_signal('/a/b/alias_rpv1000', axis2, name="MyAliasRPV1000")

        request = self.client.start_datalog(config)
        
        self.execute_in_server_thread(self.api.close, wait=False, delay=0.5)

        with self.assertRaises(sdk.exceptions.OperationFailure):
            request.wait_for_completion(3)
        
        self.assertTrue(request.completed)
        self.assertFalse(request.is_success)

    def test_handle_unexpected_disconnect(self):
        rpv1000 = self.client.watch('/rpv/x1000')
        self.set_value_and_wait_update(rpv1000, 10)

        self.assertEqual(self.client.server_state, sdk.ServerState.Connected)
        self.execute_in_server_thread(self.api.close)

        def is_disconnected():
            return self.client.server_state == sdk.ServerState.Disconnected

        self.wait_true(is_disconnected, 5)
        self.assertEqual(self.client.server_state, sdk.ServerState.Disconnected)

        with self.assertRaises(sdk.exceptions.ScrutinySDKException):
            rpv1000.value

    def test_disconnect_on_internal_error(self):
        self.assertEqual(self.client.server_state, sdk.ServerState.Connected)

        def raise_error(*args, **kwargs):
            raise RuntimeError("Internal error")

        def is_disconnected():
            return self.client.server_state == sdk.ServerState.Disconnected

        self.client._rx_message_callbacks.append(raise_error)
        self.client._send({'cmd': 'foo', 'reqid': 123, 'payload': 'aaa'})
        self.wait_true(is_disconnected)

        self.assertEqual(self.client.server_state, sdk.ServerState.Disconnected)

    def test_configure_device_link(self):
        # Serial
        configin = sdk.SerialLinkConfig(
            port='COM123',
            baudrate=115200,
            databits=8,
            stopbits='1',
            parity='none'

        )
        self.client.configure_device_link(sdk.DeviceLinkType.Serial, configin)
        self.assertFalse(self.device_handler.comm_configure_queue.empty())
        link_type, configout = self.device_handler.comm_configure_queue.get(block=False)

        for field in ('port', 'baudrate', 'databits', 'stopbits', 'parity'):
            self.assertIn(field, configout)

        self.assertEqual(link_type, 'serial')
        self.assertEqual(configout['port'], 'COM123')
        self.assertEqual(configout['baudrate'], 115200)
        self.assertEqual(configout['databits'], 8)
        self.assertEqual(configout['stopbits'], '1')
        self.assertEqual(configout['parity'], 'none')

        # TCP
        configin = sdk.TCPLinkConfig(
            host='192.168.1.100',
            port=1234
        )

        self.client.configure_device_link(sdk.DeviceLinkType.TCP, configin)
        self.assertFalse(self.device_handler.comm_configure_queue.empty())
        link_type, configout = self.device_handler.comm_configure_queue.get(block=False)

        for field in ('host', 'port'):
            self.assertIn(field, configout)

        self.assertEqual(link_type, 'tcp')
        self.assertEqual(configout['host'], '192.168.1.100')
        self.assertEqual(configout['port'], 1234)

        # UDP
        configin = sdk.UDPLinkConfig(
            host='192.168.1.101',
            port=4567
        )

        self.client.configure_device_link(sdk.DeviceLinkType.UDP, configin)
        self.assertFalse(self.device_handler.comm_configure_queue.empty())
        link_type, configout = self.device_handler.comm_configure_queue.get(block=False)

        for field in ('host', 'port'):
            self.assertIn(field, configout)

        self.assertEqual(link_type, 'udp')
        self.assertEqual(configout['host'], '192.168.1.101')
        self.assertEqual(configout['port'], 4567)

        with self.assertRaises(sdk.exceptions.OperationFailure):
            configin = sdk.UDPLinkConfig(
                host='raise',   # Special string that will make the DeviceHandler stub throw an exception
                port=4567
            )

            self.client.configure_device_link(sdk.DeviceLinkType.UDP, configin)

        with self.assertRaises(TypeError):
            configin = sdk.UDPLinkConfig(
                host='192.168.1.100',
                port=4567
            )

            self.client.configure_device_link(sdk.DeviceLinkType.Serial, configin)

    def test_user_command(self):
        # Success case
        self.assertTrue(self.device_handler.user_command_requests_queue.empty())
        response = self.client.user_command(0x10, bytes([1, 2, 3, 4, 5]))
        self.assertEqual(response.data, bytes([10, 20, 30, 40, 50]))
        self.assertEqual(response.subfunction, 0x10)
        self.assertFalse(self.device_handler.user_command_requests_queue.empty())
        subfn, data = self.device_handler.user_command_requests_queue.get_nowait()
        self.assertEqual(subfn, 0x10)
        self.assertEqual(data, bytes([1, 2, 3, 4, 5]))

        # Falure case
        self.assertTrue(self.device_handler.user_command_requests_queue.empty())
        with self.assertRaises(sdk.exceptions.OperationFailure):
            self.client.user_command(0x50, bytes([1, 2, 3]))

        self.assertFalse(self.device_handler.user_command_requests_queue.empty())

        subfn, data = self.device_handler.user_command_requests_queue.get_nowait()
        self.assertEqual(subfn, 0x50)
        self.assertEqual(data, bytes([1, 2, 3]))

    def test_get_watchable_count(self):
        count = self.client.get_watchable_count()
        self.assertIsInstance(count, dict)
        self.assertEqual(len(count), 3)
        self.assertIn(sdk.WatchableType.Variable, count)
        self.assertIn(sdk.WatchableType.Alias, count)
        self.assertIn(sdk.WatchableType.RuntimePublishedValue, count)

        self.assertEqual(count[sdk.WatchableType.Variable], 3)
        self.assertEqual(count[sdk.WatchableType.Alias], 2)
        self.assertEqual(count[sdk.WatchableType.RuntimePublishedValue], 1)
    
    def test_download_watchable_list(self):
        req = self.client.download_watchable_list()
        req.wait_for_completion(2)
        
        self.assertTrue(req.completed)
        self.assertTrue(req.is_success)

        watchables = req.get()

        self.assertIn(sdk.WatchableType.Variable, watchables)
        self.assertIn(sdk.WatchableType.Alias, watchables)
        self.assertIn(sdk.WatchableType.RuntimePublishedValue, watchables)

        self.assertEqual(len(watchables[sdk.WatchableType.Variable]), 3)
        self.assertEqual(len(watchables[sdk.WatchableType.Alias]), 2)
        self.assertEqual(len(watchables[sdk.WatchableType.RuntimePublishedValue]), 1)
        
        for path in ["/a/b/var1","/a/b/var2","/a/b/var3"]:
            self.assertIn(path, watchables[sdk.WatchableType.Variable])
            self.assertEqual(watchables[sdk.WatchableType.Variable][path].server_id, self.datastore.get_entry_by_display_path(path).get_id())
        
        for path in ["/a/b/alias_var1","/a/b/alias_rpv1000"]:
            self.assertIn(path, watchables[sdk.WatchableType.Alias])
            self.assertEqual(watchables[sdk.WatchableType.Alias][path].server_id, self.datastore.get_entry_by_display_path(path).get_id())
        
        for path in ["/rpv/x1000"]:
            self.assertIn(path, watchables[sdk.WatchableType.RuntimePublishedValue])
            self.assertEqual(watchables[sdk.WatchableType.RuntimePublishedValue][path].server_id, self.datastore.get_entry_by_display_path(path).get_id())


        nb_response_msg = 0
        for object in self.rx_rquest_log:
            if 'cmd' in object and object['cmd'] == API.Command.Api2Client.GET_WATCHABLE_LIST_RESPONSE:
                nb_response_msg+=1
        self.assertEqual(nb_response_msg, 1)

    def test_download_watchable_list_type_filter(self):
        req = self.client.download_watchable_list(types=[sdk.WatchableType.Alias, sdk.WatchableType.RuntimePublishedValue])
        req.wait_for_completion(2)
        
        self.assertTrue(req.completed)
        self.assertTrue(req.is_success)

        watchables = req.get()

        self.assertIn(sdk.WatchableType.Variable, watchables)
        self.assertIn(sdk.WatchableType.Alias, watchables)
        self.assertIn(sdk.WatchableType.RuntimePublishedValue, watchables)

        self.assertEqual(len(watchables[sdk.WatchableType.Variable]), 0)    #0 isntead of 3
        self.assertEqual(len(watchables[sdk.WatchableType.Alias]), 2)
        self.assertEqual(len(watchables[sdk.WatchableType.RuntimePublishedValue]), 1)
        
        for path in ["/a/b/alias_var1","/a/b/alias_rpv1000"]:
            self.assertIn(path, watchables[sdk.WatchableType.Alias])
            self.assertEqual(watchables[sdk.WatchableType.Alias][path].server_id, self.datastore.get_entry_by_display_path(path).get_id())
        
        for path in ["/rpv/x1000"]:
            self.assertIn(path, watchables[sdk.WatchableType.RuntimePublishedValue])
            self.assertEqual(watchables[sdk.WatchableType.RuntimePublishedValue][path].server_id, self.datastore.get_entry_by_display_path(path).get_id())
    
    def test_download_watchable_list_name_filter(self):
        req = self.client.download_watchable_list(name_patterns=["*alias_var*", "/rpv/*"])
        req.wait_for_completion(2)
        
        self.assertTrue(req.completed)
        self.assertTrue(req.is_success)

        watchables = req.get()

        self.assertIn(sdk.WatchableType.Variable, watchables)
        self.assertIn(sdk.WatchableType.Alias, watchables)
        self.assertIn(sdk.WatchableType.RuntimePublishedValue, watchables)

        self.assertEqual(len(watchables[sdk.WatchableType.Variable]), 0)    # 0 isntead of 3
        self.assertEqual(len(watchables[sdk.WatchableType.Alias]), 1)       # 1 instead of 2
        self.assertEqual(len(watchables[sdk.WatchableType.RuntimePublishedValue]), 1)
        
        for path in ["/a/b/alias_var1"]:
            self.assertIn(path, watchables[sdk.WatchableType.Alias])
            self.assertEqual(watchables[sdk.WatchableType.Alias][path].server_id, self.datastore.get_entry_by_display_path(path).get_id())
        
        for path in ["/rpv/x1000"]:
            self.assertIn(path, watchables[sdk.WatchableType.RuntimePublishedValue])
            self.assertEqual(watchables[sdk.WatchableType.RuntimePublishedValue][path].server_id, self.datastore.get_entry_by_display_path(path).get_id())

    def test_download_watchable_list_multi_chunk(self):
        req = self.client.download_watchable_list(max_per_response=1)
        req.wait_for_completion(2)
        
        self.assertTrue(req.completed)
        self.assertTrue(req.is_success)

        watchables = req.get()

        self.assertIn(sdk.WatchableType.Variable, watchables)
        self.assertIn(sdk.WatchableType.Alias, watchables)
        self.assertIn(sdk.WatchableType.RuntimePublishedValue, watchables)

        self.assertEqual(len(watchables[sdk.WatchableType.Variable]), 3)
        self.assertEqual(len(watchables[sdk.WatchableType.Alias]), 2)
        self.assertEqual(len(watchables[sdk.WatchableType.RuntimePublishedValue]), 1)

        # Make sure the server transmitted 1 watcahble definition per message. We use the client logs to validate
        nb_response_msg = 0
        for object in self.rx_rquest_log:
            if 'cmd' in object and object['cmd'] == API.Command.Api2Client.GET_WATCHABLE_LIST_RESPONSE:
                nb_response_msg+=1
        expected_response_count = len(watchables[sdk.WatchableType.Variable]) + len(watchables[sdk.WatchableType.Alias]) + len(watchables[sdk.WatchableType.RuntimePublishedValue])
        
        self.assertEqual(nb_response_msg, expected_response_count)

    def test_download_watchable_list_fail_on_disconnect(self):
        req = self.client.download_watchable_list()

        self.execute_in_server_thread(self.api.close, wait=False, delay=0.5)

        with self.assertRaises(sdk.exceptions.OperationFailure):
            req.wait_for_completion(3)
        
        self.assertTrue(req.completed)
        self.assertFalse(req.is_success)
        self.assertGreater(len(req.failure_reason), 0)  # Not empty
    
    def test_download_watchable_list_user_cancel(self):
        req = self.client.download_watchable_list()

        req.cancel()
        
        self.assertTrue(req.completed)
        self.assertFalse(req.is_success)
        self.assertGreater(len(req.failure_reason), 0)  # Not empty

if __name__ == '__main__':
    unittest.main()
