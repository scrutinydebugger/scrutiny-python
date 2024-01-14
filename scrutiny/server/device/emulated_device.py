#    emulated_device.py
#        Emulate a device that is compiled with the C++ lib.
#        For unit testing purpose
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import struct
import threading
import time
import logging
import random
import traceback
import collections
from abc import ABC
from dataclasses import dataclass
from abc import ABC, abstractmethod

from scrutiny.core.codecs import Encodable
import scrutiny.server.protocol.commands as cmd
from scrutiny.server.device.links.dummy_link import DummyLink, ThreadSafeDummyLink
from scrutiny.server.protocol import Protocol, Request, Response, ResponseCode
import scrutiny.server.protocol.typing as protocol_typing
from scrutiny.core.memory_content import MemoryContent
from scrutiny.core.basic_types import RuntimePublishedValue, EmbeddedDataType, MemoryRegion, Endianness
import scrutiny.server.datalogging.definitions.device as device_datalogging
from scrutiny.core.codecs import *
from scrutiny.server.device.device_info import ExecLoop, VariableFreqLoop, FixedFreqLoop
from scrutiny.server.protocol.crc32 import crc32

from typing import List, Dict, Optional, Union, Any, Tuple, TypedDict, cast, Deque, Callable


class NotAllowedException(Exception):
    pass


class RequestLogRecord:
    __slots__ = ('request', 'response')

    request: Request
    response: Optional[Response]

    def __init__(self, request: Request, response: Optional[Response]) -> None:
        self.request = request
        self.response = response


class RPVValuePair(TypedDict):
    definition: RuntimePublishedValue
    value: Encodable


class EmulatedTimebase:
    timestamp_100ns: int
    last_time: float

    def __init__(self) -> None:
        self.timestamp_100ns = int(0)
        self.last_time = time.monotonic()

    def process(self) -> None:
        t = time.monotonic()
        dt = t - self.last_time
        self.timestamp_100ns += int(round(dt * 1e7))
        self.timestamp_100ns = self.timestamp_100ns & 0xFFFFFFFF
        self.last_time = t

    def get_timestamp(self) -> int:
        return self.timestamp_100ns


class DataloggerEmulator:

    @dataclass
    class MemorySample:
        data: bytes

    @dataclass
    class RPVSample:
        data: Encodable
        datatype: EmbeddedDataType

    @dataclass
    class TimeSample:
        data: int

    SampleType = Union["DataloggerEmulator.MemorySample", "DataloggerEmulator.RPVSample", "DataloggerEmulator.TimeSample"]

    class Encoder(ABC):
        byte_counter: int
        entry_counter: int

        @abstractmethod
        def __init__(self, rpv_map: Dict[int, RuntimePublishedValue], buffer: bytearray, buffer_size: int) -> None:
            raise NotImplementedError("Abstract method")

        @abstractmethod
        def configure(self, config: device_datalogging.Configuration) -> None:
            raise NotImplementedError("Abstract method")

        @abstractmethod
        def encode_samples(self, samples: List["DataloggerEmulator.SampleType"]) -> None:
            raise NotImplementedError("Abstract method")

        @abstractmethod
        def get_raw_data(self) -> bytes:
            raise NotImplementedError("Abstract method")

        @abstractmethod
        def get_entry_count(self) -> int:
            raise NotImplementedError("Abstract method")

        def reset_write_counters(self) -> None:
            self.byte_counter = 0
            self.entry_counter = 0

        def get_byte_counter(self) -> int:
            return self.byte_counter

        def get_entry_counter(self) -> int:
            return self.entry_counter

    class RawEncoder(Encoder):
        buffer_size: int
        write_cursor: int
        read_cursor: int
        config: Optional[device_datalogging.Configuration]
        entry_size: int
        rpv_map: Dict[int, RuntimePublishedValue]
        data_deque: Deque[bytearray]

        def __init__(self, rpv_map: Dict[int, RuntimePublishedValue], buffer_size: int):
            self.buffer_size = buffer_size
            self.write_cursor = 0
            self.read_cursor = 0
            self.config = None
            self.entry_size = 0
            self.rpv_map = rpv_map
            self.data_deque = collections.deque(maxlen=0)
            self.reset_write_counters()

        def configure(self, config: device_datalogging.Configuration) -> None:
            self.config = config
            self.entry_size = 0
            for signal in config.get_signals():
                if isinstance(signal, device_datalogging.TimeLoggableSignal):
                    self.entry_size += 4
                elif isinstance(signal, device_datalogging.RPVLoggableSignal):
                    if signal.rpv_id not in self.rpv_map:
                        raise ValueError('RPV ID 0x%04X not in RPV map' % signal.rpv_id)
                    self.entry_size += self.rpv_map[signal.rpv_id].datatype.get_size_byte()
                elif isinstance(signal, device_datalogging.MemoryLoggableSignal):
                    self.entry_size += signal.size
                else:
                    raise NotImplementedError("Unknown signal type")
            max_entry = self.buffer_size // self.entry_size   # integer division
            self.data_deque = collections.deque(maxlen=max_entry)

        def encode_samples(self, samples: List["DataloggerEmulator.SampleType"]) -> None:
            data = bytearray()
            for sample in samples:
                if isinstance(sample, DataloggerEmulator.TimeSample):
                    data += struct.pack('>L', sample.data)
                elif isinstance(sample, DataloggerEmulator.RPVSample):
                    codec = Codecs.get(sample.datatype, Endianness.Big)
                    data += codec.encode(sample.data)
                elif isinstance(sample, DataloggerEmulator.MemorySample):
                    data += sample.data

            if len(data) != self.entry_size:
                raise ValueError("Amount of data to encode doesn't match the given configuration. Size mismatch in block size")

            self.entry_counter += 1
            self.byte_counter += len(data)
            self.data_deque.append(data)

        def get_raw_data(self) -> bytes:
            output_data = bytearray()
            for block in self.data_deque:
                output_data += block
            return bytes(output_data)

        def get_entry_count(self) -> int:
            return len(self.data_deque)

    MAX_SIGNAL_COUNT = 32

    logger: logging.Logger
    buffer_size: int
    config: Optional[device_datalogging.Configuration]
    state: device_datalogging.DataloggerState
    timebase: EmulatedTimebase
    trigger_cmt_last_val: Encodable
    last_trigger_condition_result: bool
    trigger_rising_edge_timestamp: Optional[float]
    trigger_fulfilled_timestamp: float
    encoding: device_datalogging.Encoding
    encoder: "DataloggerEmulator.Encoder"
    config_id: int
    target_byte_count_after_trigger: int
    byte_count_at_trigger: int
    entry_counter_at_trigger: int
    acquisition_id: int
    decimation_counter: int

    def __init__(self, device: "EmulatedDevice", buffer_size: int, encoding: device_datalogging.Encoding = device_datalogging.Encoding.RAW) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.device = device
        self.buffer_size = buffer_size
        self.encoding = encoding
        self.acquisition_id = 0
        self.reset()

    def reset(self) -> None:
        if self.encoding == device_datalogging.Encoding.RAW:
            self.encoder = DataloggerEmulator.RawEncoder(rpv_map=self.device.get_rpv_definition_map(), buffer_size=self.buffer_size)
        else:
            raise NotImplementedError("Unsupported encoding %s" % self.encoding)

        self.config = None
        self.state = device_datalogging.DataloggerState.IDLE
        self.timebase = EmulatedTimebase()
        self.trigger_cmt_last_val = 0
        self.last_trigger_condition_result = False
        self.trigger_rising_edge_timestamp = None
        self.trigger_fulfilled_timestamp = 0
        self.config_id = 0
        self.target_byte_count_after_trigger = 0
        self.byte_count_at_trigger = 0
        self.entry_counter_at_trigger = 0
        self.decimation_counter = 0

    def configure(self, config_id: int, config: device_datalogging.Configuration) -> None:
        self.logger.debug("Being configured. Config ID=%d" % config_id)
        self.reset()
        self.config = config
        self.config_id = config_id
        self.encoder.configure(config)

        self.state = device_datalogging.DataloggerState.CONFIGURED

    def arm_trigger(self) -> None:
        if self.state in [device_datalogging.DataloggerState.CONFIGURED, device_datalogging.DataloggerState.TRIGGERED, device_datalogging.DataloggerState.ACQUISITION_COMPLETED]:
            self.state = device_datalogging.DataloggerState.ARMED
            self.logger.debug("Trigger Armed. Going to ARMED state")

    def disarm_trigger(self) -> None:
        if self.state in [device_datalogging.DataloggerState.ARMED, device_datalogging.DataloggerState.TRIGGERED, device_datalogging.DataloggerState.ACQUISITION_COMPLETED]:
            self.state = device_datalogging.DataloggerState.CONFIGURED
            self.logger.debug("Trigger Disarmed. Going to CONFIGURED state")

    def set_error(self) -> None:
        self.state = device_datalogging.DataloggerState.ERROR
        self.logger.debug("Going to ERROR state")

    def triggered(self) -> bool:
        return self.state in [device_datalogging.DataloggerState.TRIGGERED, device_datalogging.DataloggerState.ACQUISITION_COMPLETED]

    def read_samples(self) -> List[SampleType]:
        if self.config is None:
            raise ValueError('Invalid configuration')

        samples: List["DataloggerEmulator".SampleType] = []
        for signal in self.config.get_signals():
            if isinstance(signal, device_datalogging.MemoryLoggableSignal):
                samples.append(DataloggerEmulator.MemorySample(data=self.device.read_memory(signal.address, signal.size)))
            elif isinstance(signal, device_datalogging.RPVLoggableSignal):
                value = self.device.read_rpv(signal.rpv_id)
                datatype = self.device.get_rpv_definition(signal.rpv_id).datatype
                samples.append(DataloggerEmulator.RPVSample(data=value, datatype=datatype))
            elif isinstance(signal, device_datalogging.TimeLoggableSignal):
                samples.append(DataloggerEmulator.TimeSample(self.timebase.get_timestamp()))
            else:
                raise ValueError('Unknown type of signal')
        return samples

    def fetch_operand(self, operand: device_datalogging.Operand) -> Encodable:
        if isinstance(operand, device_datalogging.LiteralOperand):
            return operand.value

        if isinstance(operand, device_datalogging.RPVOperand):
            return self.device.read_rpv(operand.rpv_id)

        if isinstance(operand, device_datalogging.VarOperand):
            data = self.device.read_memory(operand.address, operand.datatype.get_size_byte())
            codec = Codecs.get(operand.datatype, Endianness.Little)
            return codec.decode(data)

        if isinstance(operand, device_datalogging.VarBitOperand):
            mask = 0
            for i in range(operand.bitoffset, operand.bitoffset + operand.bitsize):
                mask |= (1 << i)
            uint_codec = UIntCodec(operand.datatype.get_size_byte(), Endianness.Little)
            data = self.device.read_memory(operand.address, operand.datatype.get_size_byte())
            codec = Codecs.get(operand.datatype, Endianness.Little)
            v = uint_codec.decode(data)
            v >>= operand.bitoffset
            v &= mask
            if isinstance(codec, SIntCodec) and (v & (1 << (operand.bitsize - 1))) > 0:
                v |= (~mask)

            return codec.decode(uint_codec.encode(v))

        raise ValueError('Unknown operand type')

    def check_trigger(self) -> bool:
        if self.config is None:
            return False

        output = False
        val = self.check_trigger_condition()

        if not self.last_trigger_condition_result and val:
            self.trigger_rising_edge_timestamp = time.monotonic()

        if val:
            assert self.trigger_rising_edge_timestamp is not None
            if time.monotonic() - self.trigger_rising_edge_timestamp > self.config.trigger_hold_time:
                output = True

        self.last_trigger_condition_result = val

        return output

    def check_trigger_condition(self) -> bool:
        if self.config is None:
            return False

        operands = self.config.trigger_condition.operands
        if self.config.trigger_condition.condition_id == device_datalogging.TriggerConditionID.AlwaysTrue:
            return True

        if self.config.trigger_condition.condition_id == device_datalogging.TriggerConditionID.Equal:
            return self.fetch_operand(operands[0]) == self.fetch_operand(operands[1])

        if self.config.trigger_condition.condition_id == device_datalogging.TriggerConditionID.NotEqual:
            return self.fetch_operand(operands[0]) != self.fetch_operand(operands[1])

        if self.config.trigger_condition.condition_id == device_datalogging.TriggerConditionID.GreaterThan:
            return self.fetch_operand(operands[0]) > self.fetch_operand(operands[1])

        if self.config.trigger_condition.condition_id == device_datalogging.TriggerConditionID.GreaterOrEqualThan:
            return self.fetch_operand(operands[0]) >= self.fetch_operand(operands[1])

        if self.config.trigger_condition.condition_id == device_datalogging.TriggerConditionID.LessThan:
            return self.fetch_operand(operands[0]) < self.fetch_operand(operands[1])

        if self.config.trigger_condition.condition_id == device_datalogging.TriggerConditionID.LessOrEqualThan:
            return self.fetch_operand(operands[0]) <= self.fetch_operand(operands[1])

        if self.config.trigger_condition.condition_id == device_datalogging.TriggerConditionID.IsWithin:
            return abs(self.fetch_operand(operands[0]) - self.fetch_operand(operands[1])) <= abs(self.fetch_operand(operands[2]))

        if self.config.trigger_condition.condition_id == device_datalogging.TriggerConditionID.ChangeMoreThan:
            v = self.fetch_operand(operands[0])
            diff = v - self.trigger_cmt_last_val
            delta = self.fetch_operand(operands[1])
            output = False
            if delta >= 0:
                output = diff >= delta
            else:
                output = diff <= delta

            self.trigger_cmt_last_val = v
            return output

        return False

    def process(self) -> None:
        self.timebase.process()

        if self.state in [device_datalogging.DataloggerState.CONFIGURED, device_datalogging.DataloggerState.ARMED, device_datalogging.DataloggerState.TRIGGERED]:
            assert self.config is not None
            if self.decimation_counter == 0:
                self.encoder.encode_samples(self.read_samples())
                self.logger.debug("Encoding a new sample. Internal counter=%d" % self.encoder.entry_counter)
            self.decimation_counter += 1
            if self.decimation_counter >= self.config.decimation:
                self.decimation_counter = 0

        if self.state == device_datalogging.DataloggerState.ARMED:
            assert self.config is not None
            if self.check_trigger():
                self.trigger_fulfilled_timestamp = time.monotonic()
                self.byte_count_at_trigger = self.encoder.get_byte_counter()
                self.entry_counter_at_trigger = self.encoder.get_entry_counter()
                self.target_byte_count_after_trigger = self.byte_count_at_trigger + round((1.0 - self.config.probe_location) * self.buffer_size)
                self.state = device_datalogging.DataloggerState.TRIGGERED
                self.logger.debug("Acquisition triggered. Going to TRIGGERED state. Byte counter=%d, target_byte_count_after_trigger=%d" %
                                  (self.byte_count_at_trigger, self.target_byte_count_after_trigger))

        if self.state == device_datalogging.DataloggerState.TRIGGERED:
            assert self.config is not None
            probe_location_ok = self.encoder.get_byte_counter() >= self.target_byte_count_after_trigger
            timed_out = (self.config.timeout != 0) and ((time.monotonic() - self.trigger_fulfilled_timestamp) >= self.config.timeout)
            if probe_location_ok or timed_out:
                self.logger.debug("Acquisition complete. Going to ACQUISITION_COMPLETED state")
                self.state = device_datalogging.DataloggerState.ACQUISITION_COMPLETED
                self.acquisition_id = (self.acquisition_id + 1) & 0xFFFF

        else:
            pass

    def get_acquisition_data(self) -> bytes:
        return self.encoder.get_raw_data()

    def get_buffer_size(self) -> int:
        return self.buffer_size

    def get_encoding(self) -> device_datalogging.Encoding:
        return self.encoding

    def in_error(self) -> bool:
        return self.state == device_datalogging.DataloggerState.ERROR

    def get_acquisition_id(self) -> int:
        return self.acquisition_id

    def get_config_id(self) -> int:
        return self.config_id

    def get_nb_points(self) -> int:
        return self.encoder.get_entry_count()

    def get_points_after_trigger(self) -> int:
        # The validity of this depends on the datalogger capacity to stop acquiring at the right moment.
        # if it continues acquiring and the encoder discards data, this value becomes invalid
        return self.encoder.get_entry_counter() - self.entry_counter_at_trigger


class EmulatedDevice:
    logger: logging.Logger
    link: Union[DummyLink, ThreadSafeDummyLink]
    firmware_id: bytes
    request_history: List[RequestLogRecord]
    request_history_lock: threading.Lock
    protocol: Protocol
    comm_enabled: bool
    connected: bool
    request_shutdown: bool
    thread_started_event: threading.Event
    thread: Optional[threading.Thread]
    max_rx_data_size: int
    max_tx_data_size: int
    max_bitrate_bps: int
    heartbeat_timeout_us: int
    rx_timeout_us: int
    address_size_bits: int
    supported_features: Dict[str, bool]
    forbidden_regions: List[MemoryRegion]
    readonly_regions: List[MemoryRegion]
    session_id: Optional[int]
    memory: MemoryContent
    memory_lock: threading.Lock
    rpv_lock: threading.Lock
    additional_tasks_lock: threading.Lock
    rpvs: Dict[int, RPVValuePair]
    datalogger: DataloggerEmulator
    display_name: str

    datalogging_read_in_progress: bool
    datalogging_read_cursor: int
    datalogging_read_rolling_counter: int
    loops: List[ExecLoop]

    additional_tasks: List[Callable[[], None]]
    failed_read_request_list: List[Request]
    failed_write_request_list: List[Request]
    ignore_user_command: bool

    def __init__(self, link: Union[DummyLink, ThreadSafeDummyLink]) -> None:
        if not isinstance(link, DummyLink) and not isinstance(link, ThreadSafeDummyLink):
            raise ValueError('EmulatedDevice expects a DummyLink object')
        self.logger = logging.getLogger(self.__class__.__name__)
        self.link = link    # Pre opened link.
        self.firmware_id = bytes(range(16))
        self.request_history = []
        self.protocol = Protocol(1, 0)

        self.comm_enabled = True
        self.connected = False
        self.request_shutdown = False
        self.thread_started_event = threading.Event()
        self.thread = None

        self.max_rx_data_size = 128        # Rx buffer size max. Server should make sure the request won't overflow
        self.max_tx_data_size = 128        # Tx buffer size max. Server should make sure the response won't overflow
        self.max_bitrate_bps = 100000    # Maximum bitrate supported by the device. Will gently ask the server to not go faster than that
        self.heartbeat_timeout_us = 3000000   # Will destroy session if no heartbeat is received at this rate (microseconds)
        self.rx_timeout_us = 50000     # For byte chunk reassembly (microseconds)
        self.address_size_bits = 32
        self.display_name = 'EmulatedDevice'

        self.session_id = None
        self.memory = MemoryContent()
        self.memory_lock = threading.Lock()
        self.rpv_lock = threading.Lock()
        self.additional_tasks_lock = threading.Lock()
        self.request_history_lock = threading.Lock()

        self.additional_tasks = []

        self.supported_features = {
            'memory_write': True,
            'datalogging': True,
            'user_command': True,
            '_64bits': False,
        }

        self.rpvs = {
            0x1000: {'definition': RuntimePublishedValue(id=0x1000, datatype=EmbeddedDataType.float64), 'value': 0.0},
            0x1001: {'definition': RuntimePublishedValue(id=0x1001, datatype=EmbeddedDataType.float32), 'value': 3.1415926},
            0x1002: {'definition': RuntimePublishedValue(id=0x1002, datatype=EmbeddedDataType.uint16), 'value': 0x1234},
            0x1003: {'definition': RuntimePublishedValue(id=0x1003, datatype=EmbeddedDataType.sint8), 'value': -65},
            0x1004: {'definition': RuntimePublishedValue(id=0x1004, datatype=EmbeddedDataType.boolean), 'value': True}
        }

        self.forbidden_regions = []
        self.readonly_regions = []
        self.failed_read_request_list = []
        self.failed_write_request_list = []

        self.protocol.configure_rpvs([self.rpvs[id]['definition'] for id in self.rpvs])

        self.datalogger = DataloggerEmulator(self, 256)

        self.loops = [
            FixedFreqLoop(1000, name='1KHz'),
            FixedFreqLoop(10000, name='10KHz'),
            VariableFreqLoop(name='Variable Freq 1'),
            VariableFreqLoop(name='Idle Loop', support_datalogging=False)
        ]

        self.datalogging_read_in_progress = False
        self.datalogging_read_cursor = 0
        self.datalogging_read_rolling_counter = 0
        self.ignore_user_command = False

    def thread_task(self) -> None:
        self.thread_started_event.set()
        while not self.request_shutdown:
            request = None
            try:
                request = self.read()
            except Exception as e:
                self.logger.error('Error decoding request. %s' % str(e))
                self.logger.debug(traceback.format_exc())

            if request is not None:
                response: Optional[Response] = None
                self.logger.debug('Received a request : %s' % request)
                try:
                    response = self.process_request(request)
                    if response is not None:
                        self.logger.debug('Responding %s' % response)
                        self.send(response)
                except Exception as e:
                    self.logger.error('Exception while processing Request %s. Error is : %s' % (str(request), str(e)))
                    self.logger.debug(traceback.format_exc())

                with self.request_history_lock:
                    self.request_history.append(RequestLogRecord(request=request, response=response))

            if self.is_datalogging_enabled():
                self.datalogger.process()

            # Some tasks may be required by unit tests to be run in this thread
            with self.additional_tasks_lock:
                for task in self.additional_tasks:
                    task()

            time.sleep(0.01)

    def process_request(self, req: Request) -> Optional[Response]:
        response = None
        if req.size() > self.max_rx_data_size:
            self.logger.error("Request doesn't fit buffer. Dropping %s" % req)
            return None  # drop

        data = self.protocol.parse_request(req)  # can throw

        if not self.connected:
            # We only respond to DISCOVER and CONNECT request while not session is active
            must_process = req.command == cmd.CommControl and (
                req.subfn == cmd.CommControl.Subfunction.Discover.value or req.subfn == cmd.CommControl.Subfunction.Connect.value)
            if not must_process:
                self.logger.warning('Received a request while no session was active. %s' % req)
                return None

        if req.command == cmd.CommControl:
            response = self.process_comm_control(req, data)
        elif req.command == cmd.GetInfo:
            response = self.process_get_info(req, data)
        elif req.command == cmd.MemoryControl:
            response = self.process_memory_control(req, data)
        elif req.command == cmd.DatalogControl:
            if self.supported_features['datalogging']:
                response = self.process_datalog_control(req, data)
            else:
                response = Response(req.command, req.subfn, ResponseCode.UnsupportedFeature)
        elif req.command == cmd.DummyCommand:
            response = self.process_dummy_cmd(req, data)
        elif req.command == cmd.UserCommand:
            if self.supported_features['user_command']:
                response = self.process_user_cmd(req, data)
            else:
                response = Response(req.command, req.subfn, ResponseCode.UnsupportedFeature)
        else:
            self.logger.error('Unsupported command : %s' % str(req.command.__name__))

        return response

    # ===== [CommControl] ======
    def process_comm_control(self, req: Request, data: protocol_typing.RequestData) -> Optional[Response]:
        response = None
        subfunction = cmd.CommControl.Subfunction(req.subfn)
        session_id_str = '0x%08X' % self.session_id if self.session_id is not None else 'None'
        if subfunction == cmd.CommControl.Subfunction.Discover:
            data = cast(protocol_typing.Request.CommControl.Discover, data)
            if data['magic'] == cmd.CommControl.DISCOVER_MAGIC:
                response = self.protocol.respond_comm_discover(self.firmware_id, self.display_name)
            else:
                self.logger.error('Received as Discover request with invalid payload')

        elif subfunction == cmd.CommControl.Subfunction.Connect:
            data = cast(protocol_typing.Request.CommControl.Connect, data)
            if data['magic'] == cmd.CommControl.CONNECT_MAGIC:
                if not self.connected:
                    self.initiate_session()
                    assert self.session_id is not None  # for mypy
                    response = self.protocol.respond_comm_connect(self.session_id)
                else:
                    response = Response(cmd.CommControl, subfunction, ResponseCode.Busy)
            else:
                self.logger.error('Received as Connect request with invalid payload')

        elif subfunction == cmd.CommControl.Subfunction.Heartbeat:
            data = cast(protocol_typing.Request.CommControl.Heartbeat, data)
            if data['session_id'] == self.session_id:
                challenge_response = self.protocol.heartbeat_expected_challenge_response(data['challenge'])
                response = self.protocol.respond_comm_heartbeat(self.session_id, challenge_response)
            else:
                self.logger.warning('Received a Heartbeat request for session ID 0x%08X, but my active session ID is %s' %
                                    (data['session_id'], session_id_str))
                response = Response(cmd.CommControl, subfunction, ResponseCode.InvalidRequest)

        elif subfunction == cmd.CommControl.Subfunction.Disconnect:
            data = cast(protocol_typing.Request.CommControl.Disconnect, data)
            if data['session_id'] == self.session_id:
                self.destroy_session()
                response = self.protocol.respond_comm_disconnect()
            else:
                self.logger.warning('Received a Disconnect request for session ID 0x%08X, but my active session ID is %s' %
                                    (data['session_id'], session_id_str))
                response = Response(cmd.CommControl, subfunction, ResponseCode.InvalidRequest)

        elif subfunction == cmd.CommControl.Subfunction.GetParams:
            response = self.protocol.respond_comm_get_params(
                max_rx_data_size=self.max_rx_data_size,
                max_tx_data_size=self.max_tx_data_size,
                max_bitrate_bps=self.max_bitrate_bps,
                heartbeat_timeout_us=self.heartbeat_timeout_us,
                rx_timeout_us=self.rx_timeout_us,
                address_size_byte=int(self.address_size_bits / 8)
            )

        else:
            self.logger.error('Unsupported subfunction %s for command : %s' % (subfunction, req.command.__name__))

        return response

    # ===== [GetInfo] ======
    def process_get_info(self, req: Request, data: protocol_typing.RequestData) -> Optional[Response]:
        response = None
        subfunction = cmd.GetInfo.Subfunction(req.subfn)
        if subfunction == cmd.GetInfo.Subfunction.GetProtocolVersion:
            response = self.protocol.respond_protocol_version(self.protocol.version_major, self.protocol.version_minor)

        elif subfunction == cmd.GetInfo.Subfunction.GetSupportedFeatures:
            response = self.protocol.respond_supported_features(**self.supported_features)

        elif subfunction == cmd.GetInfo.Subfunction.GetSpecialMemoryRegionCount:
            response = self.protocol.respond_special_memory_region_count(len(self.readonly_regions), len(self.forbidden_regions))

        elif subfunction == cmd.GetInfo.Subfunction.GetSpecialMemoryRegionLocation:
            data = cast(protocol_typing.Request.GetInfo.GetSpecialMemoryRegionLocation, data)
            if data['region_type'] == cmd.GetInfo.MemoryRangeType.ReadOnly:
                region_list = self.readonly_regions
            elif data['region_type'] == cmd.GetInfo.MemoryRangeType.Forbidden:
                region_list = self.forbidden_regions
            else:
                return Response(req.command, subfunction, ResponseCode.InvalidRequest)

            if data['region_index'] >= len(region_list):
                return Response(req.command, subfunction, ResponseCode.Overflow)

            region = region_list[data['region_index']]
            response = self.protocol.respond_special_memory_region_location(data['region_type'], data['region_index'], region.start, region.end)

        elif subfunction == cmd.GetInfo.Subfunction.GetRuntimePublishedValuesCount:
            response = self.protocol.respond_get_rpv_count(count=len(self.rpvs))

        elif subfunction == cmd.GetInfo.Subfunction.GetRuntimePublishedValuesDefinition:
            data = cast(protocol_typing.Request.GetInfo.GetRuntimePublishedValuesDefinition, data)
            if data['start'] > len(self.rpvs):
                return Response(req.command, subfunction, ResponseCode.FailureToProceed)

            if data['start'] + data['count'] > len(self.rpvs):
                return Response(req.command, subfunction, ResponseCode.FailureToProceed)

            all_rpvs = self.get_rpvs()
            all_rpvs.sort(key=lambda x: x.id)
            selected_rpvs = all_rpvs[data['start']:data['start'] + data['count']]
            response = self.protocol.respond_get_rpv_definition(selected_rpvs)

        elif subfunction == cmd.GetInfo.Subfunction.GetLoopCount:
            response = self.protocol.respond_get_loop_count(len(self.loops))

        elif subfunction == cmd.GetInfo.Subfunction.GetLoopDefinition:
            data = cast(protocol_typing.Request.GetInfo.GetLoopDefinition, data)
            if data['loop_id'] < 0 or data['loop_id'] >= len(self.loops):
                response = Response(req.command, req.subfn, ResponseCode.FailureToProceed)
            else:
                response = self.protocol.respond_get_loop_definition(data['loop_id'], self.loops[data['loop_id']])
        else:
            self.logger.error('Unsupported subfunction "%s" for command : "%s"' % (subfunction, req.command.__name__))

        return response

# ===== [MemoryControl] ======

    def process_memory_control(self, req: Request, data: protocol_typing.RequestData) -> Optional[Response]:
        response = None
        subfunction = cmd.MemoryControl.Subfunction(req.subfn)
        if subfunction == cmd.MemoryControl.Subfunction.Read:
            data = cast(protocol_typing.Request.MemoryControl.Read, data)
            response_blocks_read = []
            try:
                for block_to_read in data['blocks_to_read']:
                    memdata = self.read_memory(block_to_read['address'], block_to_read['length'])
                    response_blocks_read.append((block_to_read['address'], memdata))
                response = self.protocol.respond_read_memory_blocks(response_blocks_read)
            except Exception as e:
                self.failed_read_request_list.append(req)
                self.logger.warning("Failed to read memory: %s" % e)
                self.logger.debug(traceback.format_exc())
                response = Response(req.command, subfunction, ResponseCode.FailureToProceed)

        elif subfunction == cmd.MemoryControl.Subfunction.Write:
            data = cast(protocol_typing.Request.MemoryControl.Write, data)
            response_blocks_write = []
            try:
                for block_to_write in data['blocks_to_write']:
                    self.write_memory(block_to_write['address'], block_to_write['data'])
                    response_blocks_write.append((block_to_write['address'], len(block_to_write['data'])))

                response = self.protocol.respond_write_memory_blocks(response_blocks_write)
            except Exception as e:
                self.failed_write_request_list.append(req)
                self.logger.warning("Failed to write memory: %s" % e)
                self.logger.debug(traceback.format_exc())
                response = Response(req.command, subfunction, ResponseCode.FailureToProceed)

        elif subfunction == cmd.MemoryControl.Subfunction.WriteMasked:
            data = cast(protocol_typing.Request.MemoryControl.WriteMasked, data)
            response_blocks_write = []
            try:
                for block_to_write in data['blocks_to_write']:
                    assert block_to_write['write_mask'] is not None
                    self.write_memory_masked(block_to_write['address'], block_to_write['data'], block_to_write['write_mask'])
                    response_blocks_write.append((block_to_write['address'], len(block_to_write['data'])))

                response = self.protocol.respond_write_memory_blocks_masked(response_blocks_write)
            except Exception as e:
                self.failed_write_request_list.append(req)
                self.logger.warning("Failed to write memory: %s" % e)
                self.logger.debug(traceback.format_exc())
                response = Response(req.command, subfunction, ResponseCode.FailureToProceed)

        elif subfunction == cmd.MemoryControl.Subfunction.ReadRPV:
            data = cast(protocol_typing.Request.MemoryControl.ReadRPV, data)
            read_response_data: List[Tuple[int, Any]] = []
            for rpv_id in data['rpvs_id']:
                value = self.read_rpv(rpv_id)
                read_response_data.append((rpv_id, value))

            response = self.protocol.respond_read_runtime_published_values(read_response_data)

        elif subfunction == cmd.MemoryControl.Subfunction.WriteRPV:
            data = cast(protocol_typing.Request.MemoryControl.WriteRPV, data)
            write_response_data: List[int] = []
            for id_data_pair in data['rpvs']:
                rpv_id = id_data_pair['id']
                value = id_data_pair['value']
                self.write_rpv(rpv_id, value)
                write_response_data.append(rpv_id)

            response = self.protocol.respond_write_runtime_published_values(write_response_data)

        else:
            self.logger.error('Unsupported subfunction "%s" for command : "%s"' % (subfunction, req.command.__name__))

        return response

    def process_datalog_control(self, req: Request, data: protocol_typing.RequestData) -> Optional[Response]:
        response = None
        subfunction = cmd.DatalogControl.Subfunction(req.subfn)
        if subfunction == cmd.DatalogControl.Subfunction.GetSetup:
            response = self.protocol.respond_datalogging_get_setup(
                buffer_size=self.datalogger.get_buffer_size(),
                encoding=self.datalogger.get_encoding(),
                max_signal_count=self.datalogger.MAX_SIGNAL_COUNT)
        elif subfunction == cmd.DatalogControl.Subfunction.ConfigureDatalog:
            self.datalogging_read_in_progress = False
            data = cast(protocol_typing.Request.DatalogControl.Configure, data)
            if data['loop_id'] < 0 or data['loop_id'] >= len(self.loops):
                response = Response(req.command, req.subfn, code=ResponseCode.FailureToProceed)
            else:
                self.datalogger.configure(data['config_id'], data['config'])
                if self.datalogger.in_error():
                    response = Response(req.command, req.subfn, code=ResponseCode.InvalidRequest)
                else:
                    response = self.protocol.respond_datalogging_configure()
        elif subfunction == cmd.DatalogControl.Subfunction.ResetDatalogger:
            self.datalogger.reset()
            response = self.protocol.respond_datalogging_reset_datalogger()
        elif subfunction == cmd.DatalogControl.Subfunction.ArmTrigger:
            self.datalogging_read_in_progress = False
            self.datalogger.arm_trigger()
            response = self.protocol.respond_datalogging_arm_trigger()
        elif subfunction == cmd.DatalogControl.Subfunction.DisarmTrigger:
            self.datalogger.disarm_trigger()
            response = self.protocol.respond_datalogging_disarm_trigger()
        elif subfunction == cmd.DatalogControl.Subfunction.GetAcquisitionMetadata:
            if self.datalogger.state != device_datalogging.DataloggerState.ACQUISITION_COMPLETED:
                response = Response(req.command, req.subfn, ResponseCode.FailureToProceed)
            else:
                response = self.protocol.respond_datalogging_get_acquisition_metadata(
                    acquisition_id=self.datalogger.get_acquisition_id(),
                    config_id=self.datalogger.get_config_id(),
                    nb_points=self.datalogger.get_nb_points(),
                    datasize=len(self.datalogger.get_acquisition_data()),
                    points_after_trigger=self.datalogger.get_points_after_trigger()
                )
        elif subfunction == cmd.DatalogControl.Subfunction.GetStatus:

            if self.datalogger.state == device_datalogging.DataloggerState.TRIGGERED:
                # Only valid in triggered state. This is where we start counting bytes.
                byte_counter = self.datalogger.encoder.get_byte_counter()
                remaining_bytes = self.datalogger.target_byte_count_after_trigger
            else:
                # 0/0 will mean no completion percentage available
                byte_counter = 0
                remaining_bytes = 0

            response = self.protocol.respond_datalogging_get_status(
                state=self.datalogger.state,
                byte_counter_since_trigger=byte_counter,
                remaining_byte_from_trigger_to_complete=remaining_bytes
            )

        elif subfunction == cmd.DatalogControl.Subfunction.ReadAcquisition:
            if self.datalogger.state != device_datalogging.DataloggerState.ACQUISITION_COMPLETED:
                response = Response(req.command, req.subfn, ResponseCode.FailureToProceed)
            else:
                acquired_data = self.datalogger.get_acquisition_data()

                if not self.datalogging_read_in_progress:
                    self.datalogging_read_in_progress = True
                    self.datalogging_read_cursor = 0
                    self.datalogging_read_rolling_counter = 0

                remaining_data = acquired_data[self.datalogging_read_cursor:]
                if self.protocol.datalogging_read_acquisition_is_last_response(len(remaining_data), self.max_tx_data_size):
                    crc = crc32(acquired_data)
                    finished = True
                else:
                    crc = None
                    finished = False

                datalen = self.protocol.datalogging_read_acquisition_max_data_size(len(remaining_data), self.max_tx_data_size)
                datalen = min(len(remaining_data), datalen)

                self.logger.debug("ReadAcquisition. Read Cursor=%d. Finished=%s. Acquired Data Len=%d. Remaining datalen=%d.  Sending %d bytes. " %
                                  (self.datalogging_read_cursor, finished, len(acquired_data), len(remaining_data), datalen))

                response = self.protocol.respond_datalogging_read_acquisition(
                    finished=finished,
                    rolling_counter=self.datalogging_read_rolling_counter,
                    acquisition_id=self.datalogger.get_acquisition_id(),
                    data=remaining_data[:datalen],
                    crc=crc
                )

                self.datalogging_read_rolling_counter = (self.datalogging_read_rolling_counter + 1) & 0xFF
                self.datalogging_read_cursor += datalen

                if finished:
                    self.datalogging_read_in_progress = False
        else:
            self.logger.error('Unsupported subfunction "%s" for command : "%s"' % (subfunction, req.command.__name__))

        return response

    def process_dummy_cmd(self, req: Request, data: protocol_typing.RequestData) -> Optional[Response]:
        return Response(cmd.DummyCommand, subfn=req.subfn, code=ResponseCode.OK, payload=b'\xAA' * 32)

    def process_user_cmd(self, req: Request, data: protocol_typing.RequestData) -> Optional[Response]:
        if self.ignore_user_command:
            return None
        if req.subfn == 0:
            return Response(cmd.UserCommand, subfn=req.subfn, code=ResponseCode.OK, payload=b'\xAA' * 32)
        elif req.subfn == 1:
            return Response(cmd.UserCommand, subfn=req.subfn, code=ResponseCode.OK, payload=req.payload)
        else:
            return Response(cmd.UserCommand, subfn=req.subfn, code=ResponseCode.FailureToProceed)

    def start(self) -> None:
        self.logger.debug('Starting thread')
        self.request_shutdown = False
        self.thread_started_event.clear()
        self.thread = threading.Thread(target=self.thread_task)
        self.thread.start()
        self.thread_started_event.wait()
        self.logger.debug('Thread started')

    def stop(self) -> None:
        if self.thread is not None:
            self.logger.debug('Stopping thread')
            self.request_shutdown = True
            self.thread.join()
            self.logger.debug('Thread stopped')
            self.thread = None

    def initiate_session(self) -> None:
        self.session_id = random.randrange(0, 0xFFFFFFFF)
        self.connected = True
        self.logger.info('Initiating session. SessionID = 0x%08x', self.session_id)

    def destroy_session(self) -> None:
        self.logger.info('Destroying session. SessionID = 0x%08x', self.session_id)
        self.session_id = None
        self.connected = False

    def get_firmware_id(self) -> bytes:
        return self.firmware_id

    def get_firmware_id_ascii(self) -> str:
        return self.firmware_id.hex().lower()

    def is_connected(self) -> bool:
        return self.connected

    def force_connect(self) -> None:
        self.connected = True

    def force_disconnect(self) -> None:
        self.connected = False

    def disable_comm(self) -> None:
        self.comm_enabled = False

    def enable_comm(self) -> None:
        self.comm_enabled = True

    def disable_datalogging(self) -> None:
        self.supported_features['datalogging'] = False

    def enable_datalogging(self) -> None:
        self.supported_features['datalogging'] = True

    def is_datalogging_enabled(self) -> bool:
        return self.supported_features['datalogging']

    def clear_request_history(self) -> None:
        with self.request_history_lock:
            self.request_history = []

    def get_request_history(self) -> List[RequestLogRecord]:
        with self.request_history_lock:
            history = self.request_history.copy()
        return history

    def send(self, response: Response) -> None:
        if self.comm_enabled:
            self.link.emulate_device_write(response.to_bytes())

    def read(self) -> Optional[Request]:
        data = self.link.emulate_device_read()
        if len(data) > 0 and self.comm_enabled:
            return Request.from_bytes(data)
        return None

    def add_additional_task(self, task: Callable[[], None]) -> None:
        with self.additional_tasks_lock:
            self.additional_tasks.append(task)

    def clear_addition_tasks(self) -> None:
        with self.additional_tasks_lock:
            self.additional_tasks.clear()

    def add_forbidden_region(self, start: int, size: int) -> None:
        self.forbidden_regions.append(MemoryRegion(start=start, size=size))

    def add_readonly_region(self, start: int, size: int) -> None:
        self.readonly_regions.append(MemoryRegion(start=start, size=size))

    def write_memory(self, address: int, data: Union[bytes, bytearray], check_access_rights: bool = True) -> None:
        if check_access_rights:
            for region in self.forbidden_regions:
                if region.touches(MemoryRegion(address, len(data))):
                    raise NotAllowedException("Write from 0x%08x with size %d touches a forbidden memory region that span from 0x%08x to 0x%08x" %
                                              (address, len(data), region.start, region.end))

            for region in self.readonly_regions:
                if region.touches(MemoryRegion(address, len(data))):
                    raise NotAllowedException("Write from 0x%08x with size %d touches a readonly memory region that span from 0x%08x to 0x%08x" %
                                              (address, len(data), region.start, region.end))

            if self.supported_features['memory_write'] == False:
                raise NotAllowedException("Writing to memory is not allowed")

        with self.memory_lock:
            self.memory.write(address, data)

    def write_memory_masked(self, address: int, data: Union[bytes, bytearray], mask: Union[bytes, bytearray], check_access_rights: bool = True) -> None:
        assert len(mask) == len(data), "Data and mask must be the same length"
        if check_access_rights:
            for region in self.forbidden_regions:
                if region.touches(MemoryRegion(address, len(data))):
                    raise NotAllowedException("Write from 0x%08x with size %d touches a forbidden memory region that span from 0x%08x to 0x%08x" %
                                              (address, len(data), region.start, region.end))

            for region in self.readonly_regions:
                if region.touches(MemoryRegion(address, len(data))):
                    raise NotAllowedException("Write from 0x%08x with size %d touches a readonly memory region that span from 0x%08x to 0x%08x" %
                                              (address, len(data), region.start, region.end))

            if self.supported_features['memory_write'] == False:
                raise NotAllowedException("Writing to memory is not allowed")

        with self.memory_lock:
            memdata = bytearray(self.memory.read(address, len(data)))
            for i in range(len(data)):
                memdata[i] &= (data[i] | (~mask[i]))
                memdata[i] |= (data[i] & (mask[i]))
            self.memory.write(address, memdata)

    def read_memory(self, address: int, length: int, check_access_rights: bool = True) -> bytes:
        if check_access_rights:
            for region in self.forbidden_regions:
                if region.touches(MemoryRegion(address, length)):
                    raise NotAllowedException("Read from 0x%08x with size %d touches a forbidden memory region that span from 0x%08x to 0x%08x" %
                                              (address, length, region.start, region.end))

        with self.memory_lock:
            data = self.memory.read(address, length)

        return data

    def get_rpv_definition(self, rpv_id: int) -> RuntimePublishedValue:
        if rpv_id not in self.rpvs:
            raise ValueError('Unknown RPV ID 0x%04X' % rpv_id)
        return self.rpvs[rpv_id]['definition']

    def get_rpv_definition_map(self) -> Dict[int, RuntimePublishedValue]:
        output: Dict[int, RuntimePublishedValue] = {}
        for rpv_id in self.rpvs:
            output[rpv_id] = self.get_rpv_definition(rpv_id)
        return output

    def get_rpvs(self) -> List[RuntimePublishedValue]:
        output: List[RuntimePublishedValue] = []
        with self.rpv_lock:
            for id in self.rpvs:
                output.append(self.rpvs[id]['definition'])

        return output

    def write_rpv(self, rpv_id: int, value: Encodable) -> None:
        if rpv_id not in self.rpvs:
            raise ValueError('Unknown RuntimePublishedValue with ID 0x%04X' % rpv_id)

        with self.rpv_lock:
            self.rpvs[rpv_id]['value'] = value

    def read_rpv(self, rpv_id: int) -> Encodable:
        with self.rpv_lock:
            val = self.rpvs[rpv_id]['value']

        if rpv_id not in self.rpvs:
            raise ValueError('Unknown RuntimePublishedValue with ID 0x%04X' % rpv_id)
        return val
