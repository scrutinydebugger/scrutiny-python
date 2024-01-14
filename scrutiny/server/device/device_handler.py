#    device_handler.py
#        Manage the communication with the device at high level.
#        Try to establish a connection, once it succeed, reads the device configuration.
#        
#        Will keep the communication ongoing and will request for memory dump based on the
#        Datastore state
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = [
    'DeviceHandler',
    'RawMemoryWriteRequest',
    'RawMemoryReadRequest',
    'RawMemoryReadRequestCompletionCallback',
    'RawMemoryWriteRequestCompletionCallback',
    'DeviceAcquisitionRequestCompletionCallback'
]

import copy
import logging
import binascii
import time
from enum import Enum
import traceback
from uuid import uuid4
import math
from scrutiny.server.datastore.datastore_entry import DatastoreRPVEntry, EntryType
import scrutiny.server.datalogging.definitions.device as device_datalogging
from scrutiny.server.protocol import *
import scrutiny.server.protocol.typing as protocol_typing
from scrutiny.server.protocol.comm_handler import CommHandler
from scrutiny.server.protocol.commands import DummyCommand
from scrutiny.server.device.request_dispatcher import RequestDispatcher, RequestRecord, SuccessCallback, FailureCallback
from scrutiny.server.device.submodules.device_searcher import DeviceSearcher
from scrutiny.server.device.submodules.heartbeat_generator import HeartbeatGenerator
from scrutiny.server.device.submodules.info_poller import InfoPoller, ProtocolVersionCallback, CommParamCallback
from scrutiny.server.device.submodules.session_initializer import SessionInitializer
from scrutiny.server.device.submodules.memory_reader import MemoryReader, RawMemoryReadRequestCompletionCallback, RawMemoryReadRequest
from scrutiny.server.device.submodules.memory_writer import MemoryWriter, RawMemoryWriteRequestCompletionCallback, RawMemoryWriteRequest
from scrutiny.server.device.submodules.datalogging_poller import DataloggingPoller, DeviceAcquisitionRequestCompletionCallback
from scrutiny.server.device.device_info import DeviceInfo
from scrutiny.tools import Timer
from scrutiny.server.datastore.datastore import Datastore
from scrutiny.server.device.links import AbstractLink, LinkConfig
from scrutiny.core.firmware_id import PLACEHOLDER as DEFAULT_FIRMWARE_ID


from typing import TypedDict, Optional, Callable, Any, Dict, cast, List
from scrutiny.core.typehints import GenericCallback

DEFAULT_FIRMWARE_ID_ASCII = binascii.hexlify(DEFAULT_FIRMWARE_ID).decode('ascii')
"""Default firmware ID assigned to a binary that uses libscrutiny-embedded without tagging the binary after compilation"""


class DisconnectCallback(GenericCallback):
    callback: Callable[[bool], None]


class DeviceStateChangedCallback(GenericCallback):
    callback: Callable[["DeviceHandler.ConnectionStatus"], None]


# callback(success, subfn, data, error_str) -> None
UserCommandCallback = Callable[[bool, int, Optional[bytes], Optional[str]], None]


class DeviceHandlerConfig(TypedDict, total=False):
    """DeviceHandler configuration in a dict format that can be loaded from a json file"""

    response_timeout: float
    """Amount of time to wait before considering that a request has timed out"""

    heartbeat_timeout: float
    """Time interval in between Heartbeat request. This value will be 
    overridden if the device requires a smaller interval"""

    default_address_size: int
    """Address size to use in the protocol before receiving the size from a device"""

    default_protocol_version: str
    """Default protocol version to use before a device broadcast its version"""

    max_request_size: int
    """Maximum payload size to send in the requests. This value can be overridden
    by the device if it broadcast a smaller limit"""

    max_response_size: int
    """Maximum payload size that can be sent in a response by the device. This value can be overridden
    by the device if it broadcast a smaller limit"""

    max_bitrate_bps: int
    """Maximum bitrate to use on the device communication channel.
    This value can be overridden if the device requires a smaller value"""

    link_type: str
    """The type of communication link to use to talk with a device. udp, serial, dummy, dummy_threadsafe, etc"""

    link_config: LinkConfig
    """The configuration dictionary that will configure the communication link layer. 
    Unique for each type of link (udp, serial, etc)"""


class DeviceHandler:
    """Handle the communication with the embedded device that implement libscrutiny-embedded.
    It will scan for device, try to connect to it if it finds one. Then if the connection succeeds,
    it will request all the device parameters and limitations (buffer size, throttling limits, number
    of Runtime Published Values, forbidden memory region, etc.)

    Once this is done, the device handler will start watching the datastore for entries that are watched by the API
    and will run read/write request on the device to keep the datastore in sync with the embedded device.
    """

    logger: logging.Logger
    config: DeviceHandlerConfig             # The configuration coming from the user
    datastore: Datastore    # A reference to the main Datastore
    dispatcher: RequestDispatcher           # The arbiter that receive all request to be sent and decides which one to send (uses a priority queue)
    device_searcher: DeviceSearcher         # Component of the DeviceHandler that search for a new device on the communication link
    session_initializer: SessionInitializer  # Component of the DeviceHandler that try to establish a connection to a found device
    heartbeat_generator: HeartbeatGenerator  # Component of the DeviceHandler that periodically enqueue heartbeat request to keep a session active
    memory_reader: MemoryReader     # Component of the DeviceHandler that polls the device memory to keep the datastore watched entries in sync with the device
    memory_writer: MemoryWriter     # Component of the DeviceHandler that fulfill writes requests on datastore entries
    info_poller: InfoPoller         # Component of the DeviceHandler that will gather all device parameters after a connection is established
    datalogging_poller: DataloggingPoller  # Component of the DeviceHandler that will interact with the device datalogging feature
    comm_handler: CommHandler       # Layer that handle the communication with the device. Converts Requests to bytes and bytes to response. Also tells if a request timed out
    protocol: Protocol      # The communication protocol. Encode and decodes request/response payload to meaning ful data
    device_info: Optional[DeviceInfo]   # All the information about the device gathered by the InfoPoller
    comm_broken: bool   # Flag indicating that we lost connection with the device. Resets the communication and the state machine.
    device_id: Optional[str]    # Firmware ID of the device on which we are connected.
    operating_mode: "DeviceHandler.OperatingMode"   # Operating mode - Normal or special modes for unit testing
    connected: bool  # True when a connection to a device has been made
    fsm_state: "DeviceHandler.FsmState"         # The internal state machine state
    last_fsm_state: "DeviceHandler.FsmState"    # The state machine state at the previous execution cycle
    active_request_record: Optional[RequestRecord]  # Request to the device on which we are waiting for
    device_session_id: Optional[int]       # The session ID given by the device upon connection
    disconnection_requested: bool   # The external world requested that we disconnect from the device
    disconnect_callback: Optional[DisconnectCallback]   # Callback called upon disconnection
    disconnect_complete: bool   # Flags indicating that a disconnect request has been completed
    comm_broken_count: int      # Counter keeping track of how many time we had communication issues
    fully_connected_ready: bool  # Indicates that the DeviceHandler is connected to a device and the initialization phase is correctly completed
    wait_clean_state_timestamp: float  # Timestamp to detect subcomponents that might be stuck
    server_session_id: Optional[str]    # A session id generated by the DeviceHandler upon connection
    device_state_changed_callbacks: List[DeviceStateChangedCallback]    # Calback called when the state machine changes state
    expect_no_timeout: bool  # Flag that makes communicaiton timeout a critical error. Used for unit testing.

    DEFAULT_PARAMS: DeviceHandlerConfig = {
        'response_timeout': 1.0,    # If a response take more than this delay to be received after a request is sent, drop the response.
        'heartbeat_timeout': 4.0,
        'default_address_size': 32,
        'default_protocol_version': '1.0',
        'max_request_size': 1024,
        'max_response_size': 1024,
        'max_bitrate_bps': 0
    }
    WAIT_CLEAN_STATE_TIMEOUT = 0.5

    # Low number = Low priority

    class RequestPriority:
        """Priority assigned to each type of requests. It will be used by the RequestDispatcher
        internal priority queue"""
        Disconnect = 8
        Connect = 7
        Heartbeat = 6
        UserCommand = 5
        WriteMemory = 4
        WriteRPV = 4
        Datalogging = 3
        ReadMemory = 2
        ReadRPV = 2
        PollInfo = 1
        Discover = 0

    class ConnectionStatus(Enum):
        """Status of the device handler given to the outside world"""
        UNKNOWN = -1
        DISCONNECTED = 0
        CONNECTING = 1
        CONNECTED_NOT_READY = 2
        CONNECTED_READY = 3

    class FsmState(Enum):
        """The Device Handler State Machine states"""
        INIT = 0
        WAIT_COMM_LINK = 1
        WAIT_CLEAN_STATE = 2
        DISCOVERING = 3
        CONNECTING = 4
        POLLING_INFO = 5
        WAIT_DATALOGGING_READY = 6
        READY = 7
        DISCONNECTING = 8

    class OperatingMode(Enum):
        """Tells the main function of the device handler. Modes different from Normal are meant for unit tests"""
        Normal = 0
        Test_CheckThrottling = 1

    def __init__(self, config: DeviceHandlerConfig, datastore: Datastore):
        self.logger = logging.getLogger(self.__class__.__name__)

        self.config = copy.copy(self.DEFAULT_PARAMS)
        self.config.update(config)
        self.datastore = datastore
        self.dispatcher = RequestDispatcher()
        (major, minor) = self.config['default_protocol_version'].split('.')
        self.protocol = Protocol(int(major), int(minor))
        self.device_searcher = DeviceSearcher(self.protocol, self.dispatcher, priority=self.RequestPriority.Discover)
        self.session_initializer = SessionInitializer(self.protocol, self.dispatcher, priority=self.RequestPriority.Connect)
        self.heartbeat_generator = HeartbeatGenerator(self.protocol, self.dispatcher, priority=self.RequestPriority.Heartbeat)
        self.info_poller = InfoPoller(
            self.protocol,
            self.dispatcher,
            priority=self.RequestPriority.PollInfo,
            protocol_version_callback=ProtocolVersionCallback(self.get_protocol_version_callback),  # Called when protocol version is polled
            comm_param_callback=CommParamCallback(self.get_comm_params_callback),            # Called when communication params are polled
        )
        self.datalogging_poller = DataloggingPoller(
            self.protocol,
            self.dispatcher,
            self.RequestPriority.Datalogging
        )

        self.memory_reader = MemoryReader(self.protocol, self.dispatcher, self.datastore,
                                          request_priority=self.RequestPriority.ReadMemory)

        self.memory_writer = MemoryWriter(self.protocol, self.dispatcher, self.datastore,
                                          request_priority=self.RequestPriority.WriteMemory)

        self.comm_handler = CommHandler(cast(Dict[str, Any], self.config))
        self.comm_handler_open_restart_timer = Timer(1.0)

        self.heartbeat_generator.set_interval(max(0.5, self.config['heartbeat_timeout'] * 0.75))
        self.comm_broken = False
        self.device_id = None
        self.operating_mode = self.OperatingMode.Normal
        self.wait_clean_state_timestamp = time.time()
        self.active_request_record = None
        self.device_state_changed_callbacks = []
        self.expect_no_timeout = False  # Unit tests will set this to True

        if 'link_type' in self.config and 'link_config' in self.config:
            self.configure_comm(self.config['link_type'], self.config['link_config'])

        self.reset_comm()

    def register_device_state_change_callback(self, callback: DeviceStateChangedCallback) -> None:
        self.device_state_changed_callbacks.append(callback)

    def get_device_id(self) -> Optional[str]:
        """Returns the firmware ID of the connected device. None if not connected"""
        return self.device_id

    def set_operating_mode(self, mode: "DeviceHandler.OperatingMode") -> None:
        """Sets the operating mode of the DeviceHandler. Used only for unit testing"""
        if not isinstance(mode, self.OperatingMode):
            raise ValueError('mode must be an instance of DeviceHandler.OperatingMode')

        self.operating_mode = mode

    def request_datalogging_acquisition(self, loop_id: int, config: device_datalogging.Configuration, callback: DeviceAcquisitionRequestCompletionCallback) -> None:
        """Request the device for a datalogging acquisition. If a request was pending, this one will be aborted and the completion callback will be called with a failure indication. """
        self.datalogging_poller.request_acquisition(loop_id=loop_id, config=config, callback=callback)

    def cancel_datalogging_acquisition(self) -> None:
        """Cancel active acquisition if any"""
        self.datalogging_poller.cancel_acquisition_request()

    def datalogging_cancel_in_progress(self) -> bool:
        """Tells if a request cancel is in progress"""
        return self.datalogging_poller.cancel_in_progress()

    def datalogging_in_error(self) -> bool:
        """Tells if the datalogging submodule is in error"""
        return self.datalogging_poller.is_in_error()

    def datalogging_request_in_progress(self) -> bool:
        return self.datalogging_poller.request_in_progress()

    def reset_datalogging(self) -> None:
        """Forcefully reset the datalogging feature"""
        self.datalogging_poller.reset()

    def is_ready_for_datalogging_acquisition_request(self) -> bool:
        """Tells if the device is ready to receive to receive a datalogging acquisition request"""
        return self.datalogging_poller.is_ready_to_receive_new_request()

    def get_device_info(self) -> Optional[DeviceInfo]:
        """Returns all the information we have about the connected device. None if not connected"""
        return copy.copy(self.device_info)

    def get_datalogger_state(self) -> Optional[device_datalogging.DataloggerState]:
        """Return the state of the datalogging state machine within the device"""
        return self.datalogging_poller.get_datalogger_state()

    def get_datalogging_setup(self) -> Optional[device_datalogging.DataloggingSetup]:
        """Get the device datalogging configuration (encoding, buffer size, etc)"""
        return self.datalogging_poller.get_device_setup()

    def get_datalogging_acquisition_completion_ratio(self) -> Optional[float]:
        """Returns a value between 0 and 1 indicating how far the acquisition is frm being completed once the trigger event has been launched"""
        return self.datalogging_poller.get_completion_ratio()

    def get_comm_error_count(self) -> int:
        """Returns the number of communication issue we have encountered since startup"""
        return self.comm_broken_count

    def is_throttling_enabled(self) -> bool:
        """Returns True if throttling is enabled on the communication with the device"""
        return self.comm_handler.is_throttling_enabled()

    def get_throttling_bitrate(self) -> Optional[float]:
        """Returns the target mean bitrate that the throttling will try to limit to. None if throttling is not enabled"""
        return self.comm_handler.get_throttling_bitrate()

    def read_memory(self, address: int, size: int, callback: Optional[RawMemoryReadRequestCompletionCallback] = None) -> RawMemoryReadRequest:
        return self.memory_reader.request_memory_read(address, size, callback)

    def write_memory(self, address: int, data: bytes, callback: Optional[RawMemoryWriteRequestCompletionCallback] = None) -> RawMemoryWriteRequest:
        return self.memory_writer.request_memory_write(address, data, callback)

    def request_user_command(self, subfn: int, data: bytes, callback: UserCommandCallback) -> None:
        if not self.fully_connected_ready:
            raise Exception("The connection to the device is not fully ready")

        assert self.device_info is not None
        assert self.device_info.supported_feature_map is not None
        assert self.device_info.max_rx_data_size is not None

        if not self.device_info.supported_feature_map['user_command']:
            raise Exception("The device does not support the user command feature")

        if not isinstance(subfn, int) or subfn < 0 or subfn > 255:
            raise ValueError("Invalid subfunction")

        if len(data) > self.device_info.max_rx_data_size:
            raise ValueError("The given does not fit in the device rexeice buffer")

        def success_callback(request: Request, response: Response, *args:Any, **kwargs:Any) -> None:
            assert request.subfn == response.subfn  # We trust the Dispatcher to match them

            subfn = response.subfn
            if isinstance(subfn, Enum):
                subfn = cast(int, subfn.value)

            if response.code == ResponseCode.OK:
                callback(True, subfn, response.payload, None)
            else:
                callback(False, subfn, None, "Device responded with code %s" % response.code.name)

        def failure_callback(request: Request, *args:Any, **kwargs:Any) -> None:
            subfn = request.subfn
            if isinstance(subfn, Enum):
                subfn = cast(int, subfn.value)

            callback(False, subfn, None, "Failed to request the UserCommand with subfunction %s and %d bytes of data" %
                     (subfn, request.data_size()))

        self.dispatcher.register_request(
            request=self.protocol.user_command(subfn, data),
            success_callback=SuccessCallback(success_callback),
            failure_callback=FailureCallback(failure_callback),
            priority=self.RequestPriority.UserCommand
        )

    def get_comm_params_callback(self, partial_device_info: DeviceInfo) -> None:
        """Callback given to InfoPoller to be called whenever the GetParams command completes."""
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

        max_bitrate_bps = float('inf')
        if partial_device_info.max_bitrate_bps > 0:
            max_bitrate_bps = min(partial_device_info.max_bitrate_bps, max_bitrate_bps)

        if self.config['max_bitrate_bps'] is not None and self.config['max_bitrate_bps'] > 0:
            max_bitrate_bps = min(self.config['max_bitrate_bps'], max_bitrate_bps)

        if math.isinf(max_bitrate_bps):
            self.comm_handler.disable_throttling()
        else:
            self.logger.info('Device has requested a maximum bitrate of %d bps. Activating throttling.' % max_bitrate_bps)
            self.comm_handler.enable_throttling(max_bitrate_bps)

        max_request_payload_size = min(self.config['max_request_size'], partial_device_info.max_rx_data_size)
        max_response_payload_size = min(self.config['max_response_size'], partial_device_info.max_tx_data_size)

        # Will do a safety check before emitting a request
        self.memory_reader.set_size_limits(max_request_payload_size=max_request_payload_size, max_response_payload_size=max_response_payload_size)
        self.memory_writer.set_size_limits(max_request_payload_size=max_request_payload_size, max_response_payload_size=max_response_payload_size)
        self.dispatcher.set_size_limits(max_request_payload_size=max_request_payload_size, max_response_payload_size=max_response_payload_size)
        self.datalogging_poller.set_max_response_payload_size(max_response_payload_size)
        self.protocol.set_address_size_bits(partial_device_info.address_size_bits)
        self.heartbeat_generator.set_interval(max(0.5, float(partial_device_info.heartbeat_timeout_us) / 1000000.0 * 0.75))

    def get_protocol_version_callback(self, major: int, minor: int) -> None:
        """Callback called by the InfoPoller whenever the protocol version is gotten after a GetProtocol command"""
        # In the POLLING_INFO stage, there is a point where we will have gotten the communication params.
        # This callback is called right after it so we can adapt.
        # We can raise exception here.
        # They will be logged by info_poller. info_poller will go to error state. DeviceHandler will notice that and reset communication

        if not isinstance(major, int) or not isinstance(minor, int):
            raise Exception('Protocol version gotten from device not valid.')

        actual_major, actual_minor = self.protocol.get_version()

        if actual_major != major or actual_minor != minor:
            raise Exception('Device protocol says that its protocol version is V%d.%d, but previously said that it was V%d.%d when discovered. Something is not working properly.' % (
                major, minor, actual_major, actual_minor))

    # Tells the state of our connection with the device.

    def get_connection_status(self) -> "DeviceHandler.ConnectionStatus":
        """Return a status meaningful for the outside world. Used to display the connection light (red, yellow, green) in the UI"""
        if self.connected:
            if self.fully_connected_ready:
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

    def get_comm_session_id(self) -> Optional[str]:
        """Return a unique ID string for the actual device connection. None if connection status is not CONNECTED_READY"""
        if self.fully_connected_ready:
            assert self.server_session_id is not None
        return self.server_session_id

    def get_comm_link(self) -> Optional[AbstractLink]:
        return self.comm_handler.get_link()

    def get_link_type(self) -> str:
        """Returns what type of link is used to communicate with the device (serial, UDP, CanBus, etc)"""
        return self.comm_handler.get_link_type()

    # Set communication state to a fresh start.
    def reset_comm(self) -> None:
        """Reset the communication with the device. Reset all state machines, clear pending requests, reset internal status"""
        if self.comm_broken and self.device_id is not None:
            self.logger.info('Communication with device stopped. Searching for a new device')

        if self.active_request_record is not None:
            self.active_request_record.complete(False)

        self.connected = False
        self.fsm_state = self.FsmState.INIT
        self.last_fsm_state = self.FsmState.INIT
        self.active_request_record = None
        self.device_id = None
        self.device_info = None
        self.comm_broken = False
        self.stop_all_submodules()
        self.dispatcher.reset()
        self.device_session_id = None
        self.server_session_id = None
        self.disconnection_requested = False
        self.disconnect_callback = None
        self.disconnect_complete = False
        self.comm_broken_count = 0
        self.fully_connected_ready = False
        self.comm_handler.reset()
        self.protocol.set_address_size_bits(self.config['default_address_size'])  # Set back the protocol to decode addresses of this size.
        (major, minor) = self.config['default_protocol_version'].split('.')
        self.protocol.set_version(int(major), int(minor))

        if self.config['max_bitrate_bps'] is not None and self.config['max_bitrate_bps'] > 0:
            self.comm_handler.enable_throttling(self.config['max_bitrate_bps'])
        else:
            self.comm_handler.disable_throttling()

        max_request_payload_size = self.config['max_request_size']
        max_response_payload_size = self.config['max_response_size']
        self.memory_reader.set_size_limits(max_request_payload_size=max_request_payload_size, max_response_payload_size=max_response_payload_size)
        self.memory_writer.set_size_limits(max_request_payload_size=max_request_payload_size, max_response_payload_size=max_response_payload_size)
        self.dispatcher.set_size_limits(max_request_payload_size=max_request_payload_size, max_response_payload_size=max_response_payload_size)
        self.datalogging_poller.set_max_response_payload_size(max_response_payload_size)

        self.datastore.clear(entry_type=EntryType.RuntimePublishedValue)    # Device handler own RPVs
        self.protocol.configure_rpvs([])    # Empty list

    # Open communication channel based on config
    def configure_comm(self, link_type: str, link_config: LinkConfig = {}) -> None:
        """Configure the communication channel used to communicate with the device. Can be UDP, serial, etc"""
        self.comm_handler.set_link(link_type, link_config)
        self.reset_comm()
        self.comm_handler_open_restart_timer.stop()

    def validate_link_config(self, link_type: str, link_config: LinkConfig) -> None:
        """Raise an exception if the given config is not adequate for the given link type"""
        self.comm_handler.validate_link_config(link_type, link_config)

    def send_disconnect(self, disconnect_callback: Optional[DisconnectCallback] = None) -> None:
        """Request a disconnection with the device. Mainly used for unit testing"""
        self.logger.debug('Disconnection requested.')
        self.disconnection_requested = True
        self.disconnect_callback = disconnect_callback

    def stop_comm(self) -> None:
        """Close the communication channel with the device"""
        if self.comm_handler is not None:
            self.comm_handler.close()
        self.reset_comm()

    def process(self) -> None:
        """To be called periodically"""

        self.device_searcher.process()
        self.heartbeat_generator.process()
        self.info_poller.process()
        self.datalogging_poller.process()
        self.session_initializer.process()
        self.memory_reader.process()
        self.memory_writer.process()
        self.dispatcher.process()

        self.process_comm()      # Make sure request and response are being exchanged with the device

        previous_status = self.get_connection_status()
        self.do_state_machine()
        new_status = self.get_connection_status()

        if new_status != previous_status:
            for callback in self.device_state_changed_callbacks:
                callback(new_status)

    def reset_bitrate_monitor(self) -> None:
        """Reset internal bitrate counter"""
        self.comm_handler.reset_bitrate_monitor()

    def get_average_bitrate(self) -> float:
        """Returns the average bitrate measured"""
        return self.comm_handler.get_average_bitrate()

    def exec_ready_task(self, state_entry: bool = False) -> None:
        """Task to execute when the state machine is in Ready state (connected to a device and successful initialization phase)"""
        if self.operating_mode == self.OperatingMode.Normal:
            if state_entry:
                self.memory_reader.start()
                self.memory_writer.start()
            # Nothing else to do
        elif self.operating_mode == self.OperatingMode.Test_CheckThrottling:    # For unit tests
            if self.dispatcher.peek_next() is None:
                dummy_request = Request(DummyCommand, subfn=1, payload=b'\x00' * 32, response_payload_size=32);
                self.dispatcher.register_request(dummy_request, success_callback=SuccessCallback(
                    lambda *args, **kwargs: None), failure_callback=FailureCallback(self.test_failure_callback))

    def test_failure_callback(self, request: Request, params: Any) -> None:
        """Callback used for unit testing only"""
        if self.operating_mode == self.OperatingMode.Test_CheckThrottling:
            self.logger.error('Dummy Command failed to be achieved. Stopping test')
            self.comm_broken = True

    def do_state_machine(self) -> None:
        """Execute the internal state machine. This is the main logic of the DeviceHandler"""
        if self.comm_broken:
            self.comm_broken_count += 1
            self.fsm_state = self.FsmState.INIT

        # ===   FSM  ===
        state_entry: bool = True if self.fsm_state != self.last_fsm_state else False
        next_state: "DeviceHandler.FsmState" = self.fsm_state
        if self.fsm_state == self.FsmState.INIT:
            self.reset_comm()
            next_state = self.FsmState.WAIT_COMM_LINK

        elif self.fsm_state == self.FsmState.WAIT_COMM_LINK:
            if self.comm_handler.is_open():
                next_state = self.FsmState.WAIT_CLEAN_STATE

        elif self.fsm_state == self.FsmState.WAIT_CLEAN_STATE:
            if state_entry:
                self.wait_clean_state_timestamp = time.time()

            fully_stopped = True
            fully_stopped = fully_stopped and self.device_searcher.fully_stopped()
            fully_stopped = fully_stopped and self.heartbeat_generator.fully_stopped()
            fully_stopped = fully_stopped and self.info_poller.fully_stopped()
            fully_stopped = fully_stopped and self.datalogging_poller.fully_stopped()
            fully_stopped = fully_stopped and self.session_initializer.fully_stopped()
            fully_stopped = fully_stopped and self.memory_reader.fully_stopped()
            fully_stopped = fully_stopped and self.memory_writer.fully_stopped()

            if fully_stopped:
                next_state = self.FsmState.DISCOVERING

            if time.time() - self.wait_clean_state_timestamp > self.WAIT_CLEAN_STATE_TIMEOUT:
                if not self.device_searcher.fully_stopped():
                    self.logger.error("Device searcher is not stopping. Forcefully resetting.")
                    self.device_searcher.reset()

                if not self.heartbeat_generator.fully_stopped():
                    self.logger.error("Heartbeat Generator is not stopping. Forcefully resetting.")
                    self.heartbeat_generator.reset()

                if not self.datalogging_poller.fully_stopped():
                    self.logger.error("Datalogging Poller is not stopping. Forcefully resetting.")
                    self.datalogging_poller.reset()

                if not self.info_poller.fully_stopped():
                    self.logger.error("Info Poller is not stopping. Forcefully resetting.")
                    self.info_poller.reset()

                if not self.session_initializer.fully_stopped():
                    self.logger.error("Session initializer not stopping. Forcefully resetting.")
                    self.session_initializer.reset()

                if not self.memory_reader.fully_stopped():
                    self.logger.error("Memory reader not stopping. Forcefully resetting.")
                    self.memory_reader.reset()

                if not self.memory_writer.fully_stopped():
                    self.logger.error("Memory writer not stopping. Forcefully resetting.")
                    self.memory_writer.reset()

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
                self.device_session_id = self.session_initializer.get_session_id()
                session_id_str = 'None' if self.device_session_id is None else '0x%08x' % self.device_session_id
                self.logger.debug("Device session ID set : %s" % session_id_str)
                assert self.device_session_id is not None
                self.heartbeat_generator.set_session_id(self.device_session_id)
                self.heartbeat_generator.start()    # This guy will send recurrent heartbeat request. If that request fails (timeout), comm will be reset
                self.connected = True
                self.logger.info('Connected to device "%s" (ID: %s) with session ID %s' %
                                 (self.device_display_name, self.device_id, session_id_str))
                next_state = self.FsmState.POLLING_INFO
            elif self.session_initializer.is_in_error():
                self.session_initializer.stop()
                self.logger.error('Failed to initialize session.')
                self.comm_broken = True
            elif self.disconnection_requested:
                self.stop_all_submodules()
                next_state = self.FsmState.DISCONNECTING

        # ========= [POLLING_INFO] =======
        elif self.fsm_state == self.FsmState.POLLING_INFO:
            if self.disconnection_requested:
                self.stop_all_submodules()
                next_state = self.FsmState.DISCONNECTING

            if state_entry:
                self.info_poller.start()
                # make mypy happy
                assert self.device_id is not None
                assert self.device_display_name is not None
                # Set known info after start, otherwise it will be deleted and data will be missing.
                self.info_poller.set_known_info(device_id=self.device_id, device_display_name=self.device_display_name)  # To write to the device_info

            if self.info_poller.is_in_error():
                self.logger.info('Impossible to poll data from the device. Restarting communication')
                next_state = self.FsmState.INIT

            elif self.info_poller.done():
                self.device_info = self.info_poller.get_device_info()   # Make a copy if the data fetched by the infoPoller
                self.info_poller.stop()

                if self.device_info is None or not self.device_info.all_ready():    # No property should be None
                    self.logger.error('Data polled from device is incomplete. Restarting communication.')
                    self.logger.debug(str(self.device_info))
                    next_state = self.FsmState.INIT
                else:
                    next_state = self.FsmState.WAIT_DATALOGGING_READY
                    assert self.device_info.supported_feature_map is not None
                    self.memory_writer.allow_memory_write(self.device_info.supported_feature_map['memory_write'])
                    assert self.device_info.forbidden_memory_regions is not None
                    assert self.device_info.readonly_memory_regions is not None

                    for region in self.device_info.forbidden_memory_regions:
                        self.memory_writer.add_forbidden_region(region.start, region.size)
                        self.memory_reader.add_forbidden_region(region.start, region.size)
                    for region in self.device_info.readonly_memory_regions:
                        self.memory_writer.add_readonly_region(region.start, region.size)

        # ========= [WAIT_DATALOGGING_READY] ==========
        elif self.fsm_state == self.FsmState.WAIT_DATALOGGING_READY:
            if state_entry:
                assert self.device_info is not None
                assert self.device_info.supported_feature_map is not None
                if self.device_info.supported_feature_map['datalogging']:
                    self.logger.debug("Enabling datalogging handling")
                    self.datalogging_poller.enable()
                    self.datalogging_poller.start()
                else:
                    self.logger.debug("Disabling datalogging handling")
                    self.datalogging_poller.disable()
                    next_state = self.FsmState.READY
            else:
                if self.datalogging_poller.is_ready_to_receive_new_request():
                    next_state = self.FsmState.READY
                elif self.datalogging_poller.is_in_error():
                    self.logger.error('Datalogging failed to initialize properly')
                    next_state = self.FsmState.INIT
                elif not self.datalogging_poller.is_started() or not self.datalogging_poller.is_enabled():
                    self.logger.error('Datalogging poller got disabled unexpectedly')
                    next_state = self.FsmState.INIT

        # ========= [READY] ==========
        elif self.fsm_state == self.FsmState.READY:
            if state_entry:
                assert self.device_info is not None
                assert self.device_info.runtime_published_values is not None
                for rpv in self.device_info.runtime_published_values:
                    self.datastore.add_entry(DatastoreRPVEntry.make(rpv))
                self.protocol.configure_rpvs(self.device_info.runtime_published_values)
                self.datalogging_poller.configure_rpvs(self.device_info.runtime_published_values)

                self.server_session_id = uuid4().hex
                self.logger.info('Communication with device "%s" (ID: %s) fully ready. Assigning session ID: %s' %
                                 (self.device_display_name, self.device_id, self.server_session_id))
                self.logger.debug("Device information : %s" % self.device_info)

            self.exec_ready_task(state_entry)

            self.fully_connected_ready = True

            if self.disconnection_requested:
                self.stop_all_submodules()
                self.server_session_id = None
                self.fully_connected_ready = False
                next_state = self.FsmState.DISCONNECTING

            if self.dispatcher.is_in_error():
                next_state = self.FsmState.INIT

       # ========= [DISCONNECTING] ==========
        elif self.fsm_state == self.FsmState.DISCONNECTING:
            if state_entry:
                self.disconnect_complete = False

            if not self.connected or self.device_session_id is None:
                next_state = self.FsmState.INIT
            else:
                if state_entry:
                    self.dispatcher.register_request(
                        request=self.protocol.comm_disconnect(self.device_session_id),
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

    def disconnect_complete_success(self, request: Request, response_code: ResponseCode, response_data: protocol_typing.ResponseData, params: Any = None) -> None:
        """Callback called when a disconnect request completes successfully"""
        self.disconnect_complete = True
        if self.disconnect_callback is not None:
            self.disconnect_callback.__call__(True)

    def disconnect_complete_failure(self, request: Request, params: Any = None) -> None:
        """Callback called when a disconnect request fails to complete"""
        self.disconnect_complete = True
        if self.disconnect_callback is not None:
            self.disconnect_callback.__call__(False)

    def process_comm(self) -> None:
        """Process the communication with the device. To be called periodically"""
        done: bool = False

        # Try open automatically the communication with device if we can
        if not self.comm_handler.is_open():
            # Try to open comm only if the link is set
            if self.comm_handler.get_link() is not None:
                if self.comm_handler_open_restart_timer.is_stopped() or self.comm_handler_open_restart_timer.is_timed_out():
                    self.logger.debug("Starting communication")
                    self.comm_handler_open_restart_timer.start()
                    self.comm_handler.open()
                    self.reset_comm()   # Make sure to restart

        while not done:
            done = True
            self.comm_handler.process()     # Process reception

            if not self.comm_handler.is_open():
                break

            if self.active_request_record is None:  # We haven't send a request
                if not self.comm_handler.waiting_response():
                    record = self.dispatcher.pop_next()

                    if record is not None:              # A new request to send
                        self.active_request_record = record
                        self.comm_handler.send_request(record.request)
                else:  # Should not happen normally
                    self.logger.critical(
                        'Device handler believes there is no active request but comm handler says there is. This is not supposed to happen')
            else:
                if self.comm_handler.has_timed_out():       # The request we have sent has timed out.. no response
                    error_msg = 'Request timed out. %s' % self.active_request_record.request
                    if self.expect_no_timeout:  # For testing debug
                        raise TimeoutError(error_msg)
                    else:
                        self.logger.debug(error_msg)
                    self.comm_broken = True
                    self.comm_handler.clear_timeout()
                    self.active_request_record.complete(success=False)

                elif self.comm_handler.waiting_response():      # We are still waiting for a response
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
                    self.logger.error('Request processing finished with no valid response available.')
                    self.comm_handler.reset()
                    self.active_request_record.complete(success=False)

                if self.active_request_record is not None:          # double check if None here in case the user shut down communication in a callback
                    if self.active_request_record.is_completed():   # If we have called a callback, then we are done with this request.
                        self.active_request_record = None
                        done = False    # There might be another request pending. Send right away

            self.comm_handler.process()      # Process new transmission now.

    def stop_all_submodules(self)-> None:
        self.memory_reader.stop()
        self.memory_writer.stop()
        self.datalogging_poller.stop()
        self.info_poller.stop()
        self.heartbeat_generator.stop()
        self.device_searcher.stop()
        self.session_initializer.stop()
