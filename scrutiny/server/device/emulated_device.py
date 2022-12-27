#    emulated_device.py
#        Emulate a device that is compiled with the C++ lib.
#        For unit testing purpose
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import threading
import time
import logging
import random
import traceback
from scrutiny.core.codecs import Encodable

import scrutiny.server.protocol.commands as cmd
from scrutiny.server.device.links.dummy_link import DummyLink, ThreadSafeDummyLink
from scrutiny.server.protocol import Protocol, Request, Response, ResponseCode
import scrutiny.server.protocol.typing as protocol_typing
from scrutiny.core.memory_content import MemoryContent
from scrutiny.core.basic_types import RuntimePublishedValue, EmbeddedDataType

from typing import List, Dict, Optional, Union, Any, Tuple, TypedDict, cast, Set


class RequestLogRecord:
    __slots__ = ('request', 'response')

    request: Request
    response: Response

    def __init__(self, request, response):
        self.request = request
        self.response = response


class RPVValuePair(TypedDict):
    definition: RuntimePublishedValue
    value: Any


class EmulatedDevice:
    logger: logging.Logger
    link: Union[DummyLink, ThreadSafeDummyLink]
    firmware_id: bytes
    request_history: List[RequestLogRecord]
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
    forbidden_regions: List[Dict[str, int]]
    readonly_regions: List[Dict[str, int]]
    session_id: Optional[int]
    memory: MemoryContent
    memory_lock: threading.Lock
    rpvs: Dict[int, RPVValuePair]

    def __init__(self, link):
        if not isinstance(link, DummyLink) and not isinstance(link, ThreadSafeDummyLink):
            raise ValueError('EmulatedDevice expects a DummyLink object')
        self.logger = logging.getLogger(self.__class__.__name__)
        self.link = link    # Preopened link.
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

        self.session_id = None
        self.memory = MemoryContent()
        self.memory_lock = threading.Lock()

        self.supported_features = {
            'memory_read': True,
            'memory_write': True,
            'datalogging': False,
            'user_command': False,
            '_64bits': False,
        }

        self.rpvs = {
            0x1000: {'definition': RuntimePublishedValue(id=0x1000, datatype=EmbeddedDataType.float64), 'value': 0.0},
            0x1001: {'definition': RuntimePublishedValue(id=0x1001, datatype=EmbeddedDataType.float32), 'value': 3.1415926},
            0x1002: {'definition': RuntimePublishedValue(id=0x1002, datatype=EmbeddedDataType.uint16), 'value': 0x1234},
            0x1003: {'definition': RuntimePublishedValue(id=0x1003, datatype=EmbeddedDataType.sint8), 'value': -65},
            0x1004: {'definition': RuntimePublishedValue(id=0x1004, datatype=EmbeddedDataType.boolean), 'value': True}
        }

        self.forbidden_regions = [
            {'start': 0x100, 'end': 0x1FF},
            {'start': 0x1000, 'end': 0x10FF}]

        self.readonly_regions = [
            {'start': 0x200, 'end': 0x2FF},
            {'start': 0x800, 'end': 0x8FF},
            {'start': 0x900, 'end': 0x9FF}]

        self.protocol.configure_rpvs([self.rpvs[id]['definition'] for id in self.rpvs])

    def thread_task(self) -> None:
        self.thread_started_event.set()
        while not self.request_shutdown:
            request = None
            try:
                request = self.read()
            except Exception as e:
                self.logger.error('Error decoding request. %s' % str(e))

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

                self.request_history.append(RequestLogRecord(request=request, response=response))

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
        elif req.command == cmd.DummyCommand:
            response = self.process_dummy_cmd(req, data)

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
                response = self.protocol.respond_comm_discover(self.firmware_id, 'EmulatedDevice')
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
            response = self.protocol.respond_special_memory_region_location(data['region_type'], data['region_index'], region['start'], region['end'])

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
                self.logger.warning("Failed to read memory: %s" % e)
                self.logger.debug(traceback.format_exc())
                response = Response(req.command, subfunction, ResponseCode.FailureToProceed)

        elif subfunction == cmd.MemoryControl.Subfunction.Write:
            data = cast(protocol_typing.Request.MemoryControl.Write, data)
            response_blocks_write = []
            for block_to_write in data['blocks_to_write']:
                self.write_memory(block_to_write['address'], block_to_write['data'])
                response_blocks_write.append((block_to_write['address'], len(block_to_write['data'])))

            response = self.protocol.respond_write_memory_blocks(response_blocks_write)

        elif subfunction == cmd.MemoryControl.Subfunction.WriteMasked:
            data = cast(protocol_typing.Request.MemoryControl.WriteMasked, data)
            response_blocks_write = []
            for block_to_write in data['blocks_to_write']:
                self.write_memory_masked(block_to_write['address'], block_to_write['data'], block_to_write['write_mask'])
                response_blocks_write.append((block_to_write['address'], len(block_to_write['data'])))

            response = self.protocol.respond_write_memory_blocks_masked(response_blocks_write)

        elif subfunction == cmd.MemoryControl.Subfunction.ReadRPV:
            data = cast(protocol_typing.Request.MemoryControl.ReadRPV, data)
            read_response_data: List[Tuple[int, Any]] = []
            for rpv_id in data['rpvs_id']:
                if rpv_id not in self.rpvs:
                    raise Exception('Unknown RPV with ID 0x%x' % rpv_id)
                value = self.rpvs[rpv_id]['value']
                read_response_data.append((rpv_id, value))

            response = self.protocol.respond_read_runtime_published_values(read_response_data)

        elif subfunction == cmd.MemoryControl.Subfunction.WriteRPV:
            data = cast(protocol_typing.Request.MemoryControl.WriteRPV, data)
            write_response_data: List[int] = []
            for id_data_pair in data['rpvs']:
                id = id_data_pair['id']
                value = id_data_pair['value']

                if id not in self.rpvs:
                    raise Exception('Unknown RPV with ID 0x%x' % id)
                self.rpvs[id]['value'] = value
                write_response_data.append(id)

            response = self.protocol.respond_write_runtime_published_values(write_response_data)

        else:
            self.logger.error('Unsupported subfunction "%s" for command : "%s"' % (subfunction, req.command.__name__))

        return response

    def process_dummy_cmd(self, req: Request, data: protocol_typing.RequestData):
        return Response(cmd.DummyCommand, subfn=req.subfn, code=ResponseCode.OK, payload=b'\xAA' * 32)

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

    def clear_request_history(self) -> None:
        self.request_history = []

    def get_request_history(self) -> List[RequestLogRecord]:
        return self.request_history

    def send(self, response: Response) -> None:
        if self.comm_enabled:
            self.link.emulate_device_write(response.to_bytes())

    def read(self) -> Optional[Request]:
        data = self.link.emulate_device_read()
        if len(data) > 0 and self.comm_enabled:
            return Request.from_bytes(data)
        return None

    def write_memory(self, address: int, data: Union[bytes, bytearray]) -> None:
        err = None
        self.memory_lock.acquire()
        try:
            self.memory.write(address, data)
        except Exception as e:
            err = e
        finally:
            self.memory_lock.release()

        if err:
            raise err

    def write_memory_masked(self, address: int, data: Union[bytes, bytearray], mask=Union[bytes, bytearray]) -> None:
        err = None
        assert len(mask) == len(data), "Data and mask must be the same length"

        self.memory_lock.acquire()
        try:
            memdata = bytearray(self.memory.read(address, len(data)))
            for i in range(len(data)):
                memdata[i] &= (data[i] | (~mask[i]))
                memdata[i] |= (data[i] & (mask[i]))
            self.memory.write(address, memdata)
        except Exception as e:
            err = e
        finally:
            self.memory_lock.release()

        if err:
            raise err

    def read_memory(self, address: int, length: int) -> bytes:
        self.memory_lock.acquire()
        err = None
        try:
            data = self.memory.read(address, length)
        except Exception as e:
            err = e
        finally:
            self.memory_lock.release()

        if err:
            raise err
        return data

    def get_rpvs(self) -> List[RuntimePublishedValue]:
        output: List[RuntimePublishedValue] = []
        for id in self.rpvs:
            output.append(self.rpvs[id]['definition'])
        return output

    def write_rpv(self, id: int, value: Any) -> None:
        if id not in self.rpvs:
            raise Exception('Unknown RuntimePublishedValue with ID %d' % id)
        self.rpvs[id]['value'] = value
