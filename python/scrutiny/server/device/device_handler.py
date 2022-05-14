#    device_handler.py
#        Manage the communication with the device at high level.
#        Try to establish a connection, once it succeed, reads the device configuration.
#        
#        Will keep the communication ongoing and will request for memory dump based on the
#        Datastore state
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import copy
import queue
import time
import logging
import binascii
from enum import Enum
import traceback

from scrutiny.server.protocol import *
from scrutiny.server.protocol.comm_handler import CommHandler
from scrutiny.server.protocol.commands import DummyCommand
from scrutiny.server.device.request_dispatcher import RequestDispatcher, RequestRecord, SuccessCallback, FailureCallback
from scrutiny.server.device.request_generator.device_searcher import DeviceSearcher
from scrutiny.server.device.request_generator.heartbeat_generator import HeartbeatGenerator
from scrutiny.server.device.request_generator.info_poller import InfoPoller, ProtocolVersionCallback, CommParamCallback
from scrutiny.server.device.request_generator.session_initializer import SessionInitializer
from scrutiny.server.device.request_generator.memory_reader import MemoryReader
from scrutiny.server.device.request_generator.memory_writer import MemoryWriter
from scrutiny.server.device.device_info import DeviceInfo

from scrutiny.server.tools import Timer
from scrutiny.server.datastore import Datastore
from scrutiny.server.device.links import AbstractLink
from scrutiny.core.firmware_id import PLACEHOLDER as DEFAULT_FIRMWARE_ID


from typing import TypedDict, Optional, Callable, Type, Any
from scrutiny.core.typehints import GenericCallback

DEFAULT_FIRMWARE_ID_ASCII = binascii.hexlify(DEFAULT_FIRMWARE_ID).decode('ascii')


class DisconnectCallback(GenericCallback):
    callback: Callable[[bool], None]


class DeviceHandlerParams(TypedDict, total=False):
    response_timeout: float
    heartbeat_timeout: float
    default_address_size: int
    default_protocol_version: str
    link_type: str
    link_config: Any


class DeviceHandler:
    logger: logging.Logger
    config: DeviceHandlerParams
    dispatcher: RequestDispatcher
    device_searcher: DeviceSearcher
    session_initializer: SessionInitializer
    heartbeat_generator: HeartbeatGenerator
    memory_reader: MemoryReader
    memory_writer: MemoryWriter
    info_poller: InfoPoller
    comm_handler: CommHandler
    protocol: Protocol
    datastore: Datastore
    device_info: Optional[DeviceInfo]
    comm_broken: bool
    device_id: Optional[str]
    operating_mode: "DeviceHandler.OperatingMode"
    connected: bool
    fsm_state: "DeviceHandler.FsmState"
    last_fsm_state: "DeviceHandler.FsmState"
    active_request_record: Optional[RequestRecord]
    session_id: Optional[int]
    disconnection_requested: bool
    disconnect_callback: Optional[DisconnectCallback]
    disconnect_complet: bool
    comm_broken_count: int

    DEFAULT_PARAMS: DeviceHandlerParams = {
        'response_timeout': 1.0,    # If a response take more than this delay to be received after a request is sent, drop the response.
        'heartbeat_timeout': 4.0,
        'default_address_size': 32,
        'default_protocol_version': '1.0'
    }

    # Low number = Low priority
    class RequestPriority:
        Disconnect = 6
        Connect = 5
        Heatbeat = 4
        WriteMemory = 3
        ReadMemory = 2
        PollInfo = 1
        Discover = 0

    class ConnectionStatus(Enum):
        UNKNOWN = -1
        DISCONNECTED = 0
        CONNECTING = 1
        CONNECTED_NOT_READY = 2
        CONNECTED_READY = 3

    class FsmState(Enum):
        INIT = 0
        DISCOVERING = 1
        CONNECTING = 2
        POLLING_INFO = 3
        READY = 4
        DISCONNECTING = 5

    class OperatingMode(Enum):
        Normal = 0
        Test_CheckThrottling = 1

    def __init__(self, config: DeviceHandlerParams, datastore: Datastore):
        self.logger = logging.getLogger(self.__class__.__name__)

        self.config = copy.copy(self.DEFAULT_PARAMS)
        self.config.update(config)
        self.datastore = datastore
        self.dispatcher = RequestDispatcher()
        (major, minor) = self.config['default_protocol_version'].split('.')
        self.protocol = Protocol(int(major), int(minor))
        self.device_searcher = DeviceSearcher(self.protocol, self.dispatcher, priority=self.RequestPriority.Discover)
        self.session_initializer = SessionInitializer(self.protocol, self.dispatcher, priority=self.RequestPriority.Connect)
        self.heartbeat_generator = HeartbeatGenerator(self.protocol, self.dispatcher, priority=self.RequestPriority.Heatbeat)
        self.info_poller = InfoPoller(
            self.protocol,
            self.dispatcher,
            priority=self.RequestPriority.PollInfo,
            protocol_version_callback=ProtocolVersionCallback(self.get_protocol_version_callback),  # Called when protocol version is polled
            comm_param_callback=CommParamCallback(self.get_comm_params_callback),            # Called when communication params are polled
        )

        self.memory_reader = MemoryReader(self.protocol, self.dispatcher, self.datastore,
                                          request_priority=self.RequestPriority.ReadMemory)

        self.memory_writer = MemoryWriter(self.protocol, self.dispatcher, self.datastore,
                                          request_priority=self.RequestPriority.WriteMemory)

        self.comm_handler = CommHandler(self.config)

        self.heartbeat_generator.set_interval(max(0.5, self.config['heartbeat_timeout'] * 0.75))
        self.comm_broken = False
        self.device_id = None
        self.operating_mode = self.OperatingMode.Normal

        self.reset_comm()

    def set_operating_mode(self, mode: "DeviceHandler.OperatingMode"):
        if not isinstance(mode, self.OperatingMode):
            raise ValueError('mode must be an instance of DeviceHandler.OperatingMode')

        self.operating_mode = mode

    def get_device_info(self) -> Optional[DeviceInfo]:
        return copy.copy(self.device_info)

    def get_comm_error_count(self) -> int:
        return self.comm_broken_count

    def is_throttling_enabled(self) -> bool:
        return self.comm_handler.is_throttling_enabled()

    def get_throttling_bitrate(self) -> float:
        return self.comm_handler.get_throttling_bitrate()

    def get_comm_params_callback(self, partial_device_info: DeviceInfo):
        # In the POLLING_INFO stage, there is a point where we will have gotten the communication params.
        # This callback is called right after it so we can adapt.
        # We can raise exception here.
        # They will be logged by info_poller. info_poller will go to error state. DeviceHandler will notice that and reset communication

        if not isinstance(partial_device_info.address_size_bits, int):
            raise Exception('Address size gotten from device not valid.')

        if partial_device_info.address_size_bits not in [8, 16, 32, 64]:
            raise Exception("The device have an address size of %d bits. This server only supports 8,16,32,64 bits" %
                            (partial_device_info.address_size_bits))

        if not isinstance(partial_device_info.heartbeat_timeout_us, int):
            raise Exception('Heartbeat timeout gotten from device is invalid')

        if not isinstance(partial_device_info.max_bitrate_bps, int):
            raise Exception('Max bitrate gotten from device is invalid')

        if not isinstance(partial_device_info.max_tx_data_size, int):
            raise Exception('Max TX data size gotten from device is invalid')

        if not isinstance(partial_device_info.max_rx_data_size, int):
            raise Exception('Max RX data size gotten from device is invalid')

        self.logger.info('Device has an address size of %d bits. Configuring protocol to encode/decode them accordingly.' %
                         partial_device_info.address_size_bits)

        if partial_device_info.max_bitrate_bps > 0:
            self.logger.info('Device has requested a maximum bitrate of %d bps. Activating throttling.' % partial_device_info.max_bitrate_bps)
            self.comm_handler.enable_throttling(partial_device_info.max_bitrate_bps)

        # Will do a safety check before emitting a request
        self.dispatcher.set_size_limits(partial_device_info.max_rx_data_size, partial_device_info.max_tx_data_size)
        self.protocol.set_address_size_bits(partial_device_info.address_size_bits)
        self.heartbeat_generator.set_interval(max(0.5, float(partial_device_info.heartbeat_timeout_us) / 1000000.0 * 0.75))

    def get_protocol_version_callback(self, major: int, minor: int):
        # In the POLLING_INFO stage, there is a point where we will have gotten the communication params.
        # This callback is called right after it so we can adapt.
        # We can raise exception here.
        # They will be logged by info_poller. info_poller will go to error state. DeviceHandler will notice that and reset communication

        if not isinstance(major, int) or not isinstance(minor, int):
            raise Exception('Protocol version gotten from device not valid.')

        self.logger.info('Configuring protocol to V%d.%d' % (major, minor))
        self.protocol.set_version(major, minor)   # This may raise an exception

    # Tells the state of our connection with the device.

    def get_connection_status(self) -> "DeviceHandler.ConnectionStatus":
        if self.connected:
            if self.fsm_state == self.FsmState.READY:
                return self.ConnectionStatus.CONNECTED_READY
            else:
                return self.ConnectionStatus.CONNECTED_NOT_READY

        if self.comm_broken:
            return self.ConnectionStatus.DISCONNECTED

        if self.fsm_state == self.FsmState.CONNECTING:
            return self.ConnectionStatus.CONNECTING

        if not self.connected:
            return self.ConnectionStatus.DISCONNECTED

        return self.ConnectionStatus.UNKNOWN

    def get_comm_link(self) -> Optional[AbstractLink]:
        return self.comm_handler.get_link()

    # Set communication state to a fresh start.
    def reset_comm(self) -> None:
        if self.comm_broken and self.device_id is not None:
            self.logger.info('Communication with device stopped. Searching for a new device')

        self.connected = False
        self.fsm_state = self.FsmState.INIT
        self.last_fsm_state = self.FsmState.INIT
        self.active_request_record = None
        self.device_id = None
        self.device_info = None
        self.comm_broken = False
        self.device_searcher.stop()
        self.heartbeat_generator.stop()
        self.info_poller.stop()
        self.session_initializer.stop()
        self.dispatcher.reset()
        self.memory_reader.stop()
        self.memory_writer.stop()
        self.session_id = None
        self.disconnection_requested = False
        self.disconnect_callback = None
        self.disconnect_complete = False
        self.comm_broken_count = 0
        self.protocol.set_address_size_bits(self.config['default_address_size'])  # Set back the protocol to decode addresses of this size.
        (major, minor) = self.config['default_protocol_version'].split('.')
        self.protocol.set_version(int(major), int(minor))
        self.comm_handler.disable_throttling()

    # Open communication channel based on config
    def init_comm(self) -> None:
        link_class: Type[AbstractLink]

        if self.config['link_type'] == 'none':
            return None

        if self.config['link_type'] == 'udp':
            from .links.udp_link import UdpLink
            link_class = UdpLink
        elif self.config['link_type'] == 'dummy':
            from .links.dummy_link import DummyLink
            link_class = DummyLink
        elif self.config['link_type'] == 'thread_safe_dummy':
            from .links.dummy_link import ThreadSafeDummyLink
            link_class = ThreadSafeDummyLink
        else:
            raise ValueError('Unknown link type %s' % self.config['link_type'])

        device_link = link_class(self.config['link_config'])  # instantiate the class
        self.comm_handler.open(device_link)
        self.reset_comm()

    def send_disconnect(self, disconnect_callback: Optional[DisconnectCallback] = None):
        self.logger.debug('Disconnection requested.')
        self.disconnection_requested = True
        self.disconnect_callback = disconnect_callback

    # Stop all communication with the device
    def stop_comm(self) -> None:
        if self.comm_handler is not None:
            self.comm_handler.close()
        self.reset_comm()

    def refresh_vars(self) -> None:
        pass

    # To be called periodically
    def process(self) -> None:
        self.device_searcher.process()
        self.heartbeat_generator.process()
        self.info_poller.process()
        self.session_initializer.process()
        self.memory_reader.process()
        self.memory_writer.process()
        self.dispatcher.process()

        self.handle_comm()      # Make sure request and response are being exchanged with the device
        self.do_state_machine()

    def reset_bitrate_monitor(self) -> None:
        self.comm_handler.reset_bitrate_monitor()

    def get_average_bitrate(self) -> float:
        return self.comm_handler.get_average_bitrate()

    def exec_ready_task(self, state_entry: bool = False) -> None:
        if self.operating_mode == self.OperatingMode.Normal:
            if state_entry:
                self.memory_reader.start()
                self.memory_writer.start()
            # Nothing else to do
        elif self.operating_mode == self.OperatingMode.Test_CheckThrottling:
            if self.dispatcher.peek_next() is None:
                dummy_request = Request(DummyCommand, subfn=1, payload=b'\x00' * 32, response_payload_size=32);
                self.dispatcher.register_request(dummy_request, success_callback=SuccessCallback(
                    lambda *args, **kwargs: None), failure_callback=FailureCallback(self.test_failure_callback))

    def test_failure_callback(self, request: Request, params: Any) -> None:
        if self.operating_mode == self.OperatingMode.Test_CheckThrottling:
            self.logger.error('Dummy Command failed to be achieved. Stopping test')
            self.comm_broken = True

    def do_state_machine(self) -> None:
        if self.comm_broken:
            self.comm_broken_count += 1
            self.fsm_state = self.FsmState.INIT

        # ===   FSM  ===
        state_entry: bool = True if self.fsm_state != self.last_fsm_state else False
        next_state: "DeviceHandler.FsmState" = self.fsm_state
        if self.fsm_state == self.FsmState.INIT:
            self.reset_comm()
            if self.comm_handler.is_open():
                next_state = self.FsmState.DISCOVERING

        # ============= [DISCOVERING] =====================
        elif self.fsm_state == self.FsmState.DISCOVERING:
            if state_entry:
                self.device_searcher.start()

            if self.device_searcher.device_found():
                found_device_id = self.device_searcher.get_device_firmware_id_ascii()
                if self.device_id is None:
                    self.device_display_name = self.device_searcher.get_device_display_name()
                    if not self.device_display_name:
                        self.device_display_name = 'Anonymous'
                    self.device_id = found_device_id
                    self.logger.info('Found a device. "%s" (ID: %s)' % (self.device_display_name, self.device_id))

                    if self.device_id == DEFAULT_FIRMWARE_ID_ASCII:
                        self.logger.warning(
                            "Firmware ID of this device is a default placeholder. Firmware might not have been tagged with a valid ID in the build toolchain.")

                    version = self.device_searcher.get_device_protocol_version()
                    if version is not None:
                        (major, minor) = version
                        self.logger.info('Configuring protocol to V%d.%d' % (major, minor))
                        self.protocol.set_version(major, minor)   # This may raise an exception

            if self.device_id is not None:
                self.device_searcher.stop()
                next_state = self.FsmState.CONNECTING

        # ============= [CONNECTING] =====================
        elif self.fsm_state == self.FsmState.CONNECTING:
            # Connection message can be handled synchronously as no request generator is active.
            # In other conditions, we should use the dispatcher and do everything asynchronously.
            if state_entry:
                self.session_initializer.start()

            if self.session_initializer.connection_successful():
                self.session_initializer.stop()
                self.session_id = self.session_initializer.get_session_id()
                session_id_str = 'None' if self.session_id is None else '0x%08x' % self.session_id
                self.logger.debug("Session ID set : %s" % session_id_str)
                self.heartbeat_generator.set_session_id(self.session_id)
                self.heartbeat_generator.start()    # This guy will send recurrent heartbeat request. If that request fails (timeout), comm will be reset
                self.connected = True
                self.logger.info('Connected to device "%s" (ID: %s) with session ID %s' %
                                 (self.device_display_name, self.device_id, session_id_str))
                next_state = self.FsmState.POLLING_INFO
            elif self.session_initializer.is_in_error():
                self.session_initializer.stop()
                self.comm_broken = True
            elif self.disconnection_requested:
                next_state = self.FsmState.DISCONNECTING

        # ========= [POLLING_INFO] =======
        elif self.fsm_state == self.FsmState.POLLING_INFO:
            if self.disconnection_requested:
                next_state = self.FsmState.DISCONNECTING

            if state_entry:
                self.info_poller.start()

            if self.info_poller.is_in_error():
                self.logger.info('Impossible to poll data from the device. Restarting communication')
                next_state = self.FsmState.INIT

            elif self.info_poller.done():
                self.device_info = self.info_poller.get_device_info()   # Make a copy if the data fetched by the infoPoller
                self.info_poller.stop()

                if self.device_info is None or not self.device_info.all_ready():    # No property should be None
                    self.logger.error('Data polled from device is incomplete. Restarting communication. %s')
                    self.logger.debug(str(self.device_info))
                    next_state = self.FsmState.INIT
                else:
                    next_state = self.FsmState.READY

        # ========= [READY] ==========
        elif self.fsm_state == self.FsmState.READY:
            if state_entry:
                self.logger.info('Communication with device "%s" (ID: %s) fully ready' % (self.device_display_name, self.device_id))
                self.logger.debug("Device information : %s" % self.device_info)

            self.exec_ready_task(state_entry)

            if self.disconnection_requested:
                self.memory_reader.stop()
                self.memory_writer.stop()
                next_state = self.FsmState.DISCONNECTING

            if self.dispatcher.is_in_error():
                next_state = self.FsmState.INIT

       # ========= [DISCONNECTING] ==========
        elif self.fsm_state == self.FsmState.DISCONNECTING:
            if state_entry:
                self.disconnect_complete = False

            if not self.connected or self.session_id is None:
                next_state = self.FsmState.INIT
            else:
                if state_entry:
                    self.dispatcher.register_request(
                        request=self.protocol.comm_disconnect(self.session_id),
                        success_callback=SuccessCallback(self.disconnect_complete_success),
                        failure_callback=FailureCallback(self.disconnect_complete_failure),
                        priority=self.RequestPriority.Disconnect
                    )

            if self.disconnect_complete:
                next_state != self.FsmState.DISCONNECTING

        else:
            raise Exception('Unknown FSM state : %s' % self.fsm_state)

        # ====  FSM END ====

        self.last_fsm_state = self.fsm_state
        if next_state != self.fsm_state:
            self.logger.debug('Moving FSM to state %s' % next_state)
        self.fsm_state = next_state

    def disconnect_complete_success(self, request: Request, response_code: ResponseCode, response_data: ResponseData, params: Any = None):
        self.disconnect_complete = True
        if self.disconnect_callback is not None:
            self.disconnect_callback.__call__(True)

    def disconnect_complete_failure(self, request: Request, params: Any = None):
        self.disconnect_complete = True
        if self.disconnect_callback is not None:
            self.disconnect_callback.__call__(False)

    def handle_comm(self) -> None:
        done: bool = False
        while not done:
            done = True
            self.comm_handler.process()     # Process reception

            if not self.comm_handler.is_open():
                break

            if self.active_request_record is None:  # We haven't send a request
                record = self.dispatcher.pop_next()

                if record is not None:              # A new request to send
                    self.active_request_record = record
                    self.comm_handler.send_request(record.request)
            else:
                if self.comm_handler.has_timed_out():       # The request we have sent has timed out.. no response
                    self.logger.debug('Request timed out. %s' % self.active_request_record.request)
                    self.comm_broken = True
                    self.comm_handler.clear_timeout()
                    self.active_request_record.complete(success=False)

                elif self.comm_handler.waiting_response():      # We are still wiating for a resonse
                    if self.comm_handler.response_available():  # We got a response! yay
                        response = self.comm_handler.get_response()

                        try:
                            self.active_request_record.complete(success=True, response=response)
                        except Exception as e:                   # Malformed response.
                            self.comm_broken = True
                            self.logger.error("Error in success callback. %s" % str(e))
                            self.logger.debug(traceback.format_exc())
                            self.active_request_record.complete(success=False)

                else:   # Comm handler decided to go back to Idle by itself. Most likely a valid message that was not the response of the request.
                    self.comm_broken = True
                    self.comm_handler.reset()
                    self.active_request_record.complete(success=False)

                if self.active_request_record is not None:          # double check if None here in case the user shut down communication in a callback
                    if self.active_request_record.is_completed():   # If we have called a callback, then we are done with this request.
                        self.active_request_record = None
                        done = False    # There might be another request pending. Send right away

            self.comm_handler.process()      # Process new transmission now.
