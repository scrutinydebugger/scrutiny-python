#    datalogging_poller.py
#        Component of the Device Handler that handles the datalogging feature within the device.
#        Poll for status, new data and configure the device
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

import logging
import traceback
from enum import Enum, auto
from dataclasses import dataclass
import copy

from scrutiny.server.protocol import *
from scrutiny.server.device.request_dispatcher import RequestDispatcher, SuccessCallback, FailureCallback
import scrutiny.server.datalogging.definitions.device as device_datalogging
import scrutiny.server.protocol.typing as protocol_typing
import scrutiny.server.protocol.commands as cmd
from scrutiny.server.tools import Timer
from scrutiny.server.protocol.crc32 import crc32
from scrutiny.core.basic_types import RuntimePublishedValue
from scrutiny.server.datalogging.datalogging_utilities import extract_signal_from_data

from scrutiny.core.typehints import GenericCallback
from typing import Optional, Any, cast, Callable, List, Dict


class FSMState(Enum):
    IDLE = auto()
    GET_SETUP = auto()
    WAIT_FOR_REQUEST = auto()
    CONFIGURING = auto()
    ARMING = auto()
    WAIT_FOR_DATA = auto()
    READ_METADATA = auto()
    RETRIEVING_DATA = auto()
    DATA_RETRIEVAL_FINISHED = auto()


class DeviceAcquisitionRequestCompletionCallback(GenericCallback):
    callback: Callable[[bool, Optional[List[List[bytes]]]], None]


class DataloggingReceiveSetupCallback(GenericCallback):
    callback: Callable[[device_datalogging.DataloggingSetup], None]


@dataclass
class AcquisitionRequest:
    loop_id: int
    config: device_datalogging.Configuration
    completion_callback: DeviceAcquisitionRequestCompletionCallback


@dataclass
class ReceivedChunk:
    acquisition_id: int
    crc: Optional[int]
    finished: bool
    rolling_counter: int
    data: bytes


class DataloggingPoller:

    UPDATE_STATUS_INTERVAL_IDLE = 0.5
    UPDATE_STATUS_INTERVAL_ACQUIRING = 0.2
    MAX_FAILURE_WHILE_READING = 5

    logger: logging.Logger
    dispatcher: RequestDispatcher       # We put the request in here, and we know they'll go out
    protocol: Protocol                  # The actual protocol. Used to build the request payloads
    request_priority: int               # Our dispatcher priority
    stop_requested: bool    # Requested to stop polling
    request_pending: bool   # True when we are waiting for a request to complete
    started: bool           # Indicate if enabled or not
    device_setup: Optional[device_datalogging.DataloggingSetup]
    error: bool
    enabled: bool
    state: FSMState
    previous_state: FSMState
    update_status_timer: Timer
    device_datalogging_state: device_datalogging.DataloggerState
    max_response_payload_size: Optional[int]
    rpv_map: Dict[int, RuntimePublishedValue]

    arm_completed: bool
    new_request_received: bool
    acquisition_request: Optional[AcquisitionRequest]
    request_failed: bool
    configure_completed: bool
    failure_counter: int
    data_read_success: bool
    bytes_received: bytearray
    read_rolling_counter: int
    require_status_update: bool
    ready_to_receive_request: bool

    acquisition_metadata: Optional[device_datalogging.AcquisitionMetadata]
    received_data_chunk: Optional[ReceivedChunk]
    receive_setup_callback: Optional[DataloggingReceiveSetupCallback]

    def __init__(self, protocol: Protocol, dispatcher: RequestDispatcher, request_priority: int):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self.protocol = protocol
        self.request_priority = request_priority

        self.reset()

    def reset(self):
        """Put back the datalogging poller to its startup state"""

        self.acquisition_request = None
        self.enabled = True
        self.receive_setup_callback = None
        self.actual_config_id = 0
        self.device_datalogging_state = device_datalogging.DataloggerState.IDLE
        self.max_response_payload_size = None
        self.update_status_timer = Timer(self.UPDATE_STATUS_INTERVAL_IDLE)
        self.rpv_map = {}
        self.set_standby()

    def set_standby(self):
        """Put back the datalogging poller to an idle state without destroying important internal values"""
        self.mark_active_acquisition_failed_if_any()

        self.started = False
        self.stop_requested = False
        self.request_pending = False
        self.device_setup = None
        self.error = False
        self.state = FSMState.IDLE
        self.previous_state = FSMState.IDLE
        self.new_request_received = False
        self.acquisition_request = None
        self.request_failed = False
        self.configure_completed = False
        self.arm_completed = False
        self.update_status_timer.stop()
        self.device_datalogging_state = device_datalogging.DataloggerState.IDLE
        self.failure_counter = 0
        self.data_read_success = False
        self.bytes_received = bytearray()
        self.read_rolling_counter = 0
        self.acquisition_metadata = None
        self.require_status_update = False
        self.ready_to_receive_request = False

    def configure_rpvs(self, rpvs: List[RuntimePublishedValue]):
        self.rpv_map.clear()
        for rpv in rpvs:
            self.rpv_map[rpv.id] = rpv

        self.logger.debug("RPV map configured with %d" % len(self.rpv_map))

    def set_max_response_payload_size(self, max_response_payload_size: int) -> None:
        self.max_response_payload_size = max_response_payload_size

    def start(self) -> None:
        """ Launch polling of data """
        if self.enabled:
            self.started = True

    def stop(self) -> None:
        """ Stop the poller """
        self.stop_requested = True

    def disable(self) -> None:
        self.enabled = False
        self.stop()

    def enable(self) -> None:
        self.enabled = True

    def is_enabled(self) -> bool:
        return self.enabled

    def get_datalogger_state(self) -> device_datalogging.DataloggerState:
        return self.device_datalogging_state

    def get_device_setup(self) -> Optional[device_datalogging.DataloggingSetup]:
        return self.device_setup

    def set_datalogging_callbacks(self, receive_setup: DataloggingReceiveSetupCallback):
        self.receive_setup_callback = receive_setup

    def mark_active_acquisition_failed_if_any(self):
        if self.acquisition_request is not None:
            self.acquisition_request.completion_callback(False, None)
            self.acquisition_request = None

    def mark_active_acquisition_success(self, data: bytes) -> None:
        if self.acquisition_request is not None:
            if self.device_setup is None:
                self.acquisition_request.completion_callback(False, None)
                self.logger.error("Cannot mark acquisition successfully completed as no device setup is available")
            else:
                try:
                    deinterleaved_data = extract_signal_from_data(
                        data=data,
                        config=self.acquisition_request.config,
                        rpv_map=self.rpv_map,
                        encoding=self.device_setup.encoding)
                    self.acquisition_request.completion_callback(True, deinterleaved_data)
                except Exception as e:
                    self.logger.error("Failed to parse data received from device datalogging acquisition. %s" % str(e))
                    self.logger.debug(traceback.format_exc())
                    self.acquisition_request.completion_callback(False, None)

                self.acquisition_request = None

    def request_acquisition(self, loop_id: int, config: device_datalogging.Configuration, callback: DeviceAcquisitionRequestCompletionCallback) -> None:
        if not self.max_response_payload_size:
            raise ValueError("Maximum response payload size must be defined first")

        if not self.is_ready_to_receive_new_request():
            raise RuntimeError("Not ready to receive a new acquisition request")

        assert self.device_setup is not None    # Will be set if is_ready_to_receive_new_request() returns True
        if len(config.get_signals()) > self.device_setup.max_signal_count:
            raise ValueError("Too many signals in configuration. Maximum = %d" % self.device_setup.max_signal_count)

        self.mark_active_acquisition_failed_if_any()

        self.acquisition_request = AcquisitionRequest(
            loop_id=loop_id,
            config=config,
            completion_callback=callback
        )

        self.new_request_received = True

    def is_ready_to_receive_new_request(self) -> bool:
        return self.ready_to_receive_request and not self.error

    def process(self) -> None:
        """To be called periodically to make the process move forward"""
        if not self.started or not self.enabled:
            self.set_standby()
            return
        elif self.stop_requested and not self.request_pending:
            self.started = False
            self.set_standby()
            return
        elif self.error:    # only way out is a reset
            self.mark_active_acquisition_failed_if_any()
            return

        if self.state in [FSMState.WAIT_FOR_DATA]:  # Fast update when waiting for trigger
            self.update_status_timer.set_timeout(self.UPDATE_STATUS_INTERVAL_ACQUIRING)
        else:   # Slow update otherwise
            self.update_status_timer.set_timeout(self.UPDATE_STATUS_INTERVAL_IDLE)

        if not self.request_pending:
            if self.require_status_update or self.update_status_timer.is_timed_out():
                self.dispatch(self.protocol.datalogging_get_status())
                self.update_status_timer.start()

        try:
            state_entry = self.previous_state != self.state
            next_state = self.state

            if self.state == FSMState.IDLE:
                self.mark_active_acquisition_failed_if_any()
                self.device_setup = None
                self.configure_completed = False
                self.arm_completed = False
                self.ready_to_receive_request = False
                self.update_status_timer.start()
                next_state = FSMState.GET_SETUP

            elif self.state == FSMState.GET_SETUP:
                if state_entry:
                    self.request_failed = False

                if not self.request_pending and self.device_setup is None:
                    self.dispatch(self.protocol.datalogging_get_setup())

                if self.device_setup is not None:
                    if self.receive_setup_callback is not None:
                        self.receive_setup_callback(copy.copy(self.device_setup))
                    next_state = FSMState.WAIT_FOR_REQUEST
                    self.logger.debug("Datalogging setup received. %s" % (self.device_setup.__dict__))

            elif self.state == FSMState.WAIT_FOR_REQUEST:
                if state_entry:
                    self.ready_to_receive_request = True

                if not self.request_pending:
                    if self.new_request_received:
                        self.new_request_received = False
                        assert self.acquisition_request is not None

                        self.actual_config_id = (self.actual_config_id + 1) & 0xFFFF    # Validation token associated with acquisition by the device.
                        request = self.protocol.datalogging_configure(
                            loop_id=self.acquisition_request.loop_id,
                            config_id=self.actual_config_id,
                            config=self.acquisition_request.config
                        )
                        self.dispatch(request)
                        next_state = FSMState.CONFIGURING

            elif self.state == FSMState.CONFIGURING:    # Waiting on configuration completed
                if state_entry:
                    self.configure_completed = False

                if self.new_request_received:   # New request interrupts the previous one
                    if not self.request_pending:
                        next_state = FSMState.WAIT_FOR_REQUEST

                elif self.request_failed:
                    next_state = FSMState.IDLE

                elif self.configure_completed:
                    self.configure_completed = False
                    self.dispatch(self.protocol.datalogging_arm_trigger())
                    next_state = FSMState.ARMING

            elif self.state == FSMState.ARMING:
                if state_entry:
                    self.arm_completed = False

                if self.new_request_received:   # New request interrupts the previous one
                    if not self.request_pending:
                        next_state = FSMState.WAIT_FOR_REQUEST

                elif self.request_failed:
                    next_state = FSMState.IDLE

                elif self.arm_completed:
                    next_state = FSMState.WAIT_FOR_DATA

            elif self.state == FSMState.WAIT_FOR_DATA:
                if state_entry:
                    self.require_status_update = True

                if self.new_request_received:   # New request interrupts the previous one
                    if not self.request_pending:
                        next_state = FSMState.WAIT_FOR_REQUEST

                elif self.require_status_update == False:
                    if self.device_datalogging_state == device_datalogging.DataloggerState.ACQUISITION_COMPLETED:
                        next_state = FSMState.READ_METADATA

            elif self.state == FSMState.READ_METADATA:
                # Starting from here, we have previous data, it's beneficial to be resilient to communication problems
                if state_entry:
                    self.acquisition_metadata = None
                    self.failure_counter = 0
                    self.request_failed = False

                if self.acquisition_metadata is not None:
                    if self.acquisition_metadata.config_id != self.actual_config_id:
                        self.logger.error("Data acquired is not the one that was expected. Config ID mismatch. Expected %d, Gotten %d" %
                                          (self.actual_config_id, self.acquisition_metadata.config_id))
                        next_state = FSMState.WAIT_FOR_REQUEST
                    else:
                        next_state = FSMState.RETRIEVING_DATA

                elif self.request_failed:
                    self.request_failed = False
                    self.failure_counter += 1
                    if self.failure_counter >= self.MAX_FAILURE_WHILE_READING:
                        self.logger.error("Too many communication error. Giving up reading the acquisition")
                        next_state = FSMState.DATA_RETRIEVAL_FINISHED

                elif not self.request_pending:
                    self.dispatch(self.protocol.datalogging_get_acquisition_metadata())

            elif self.state == FSMState.RETRIEVING_DATA:
                if state_entry:
                    self.data_read_success = False
                    self.request_failed = False
                    self.failure_counter = 0
                    self.read_rolling_counter = 0
                    self.received_data_chunk = None
                    self.bytes_received = bytearray()

                if self.new_request_received:   # New request interrupts the previous one
                    if not self.request_pending:
                        next_state = FSMState.WAIT_FOR_REQUEST

                elif self.request_failed:
                    self.request_failed = False
                    self.failure_counter += 1
                    if self.failure_counter >= self.MAX_FAILURE_WHILE_READING:
                        self.logger.error("Too many communication error. Giving up reading the acquisition")
                        next_state = FSMState.DATA_RETRIEVAL_FINISHED

                elif self.received_data_chunk is not None:
                    assert self.max_response_payload_size is not None
                    assert self.acquisition_metadata is not None
                    assert self.device_setup is not None

                    if self.received_data_chunk.acquisition_id != self.acquisition_metadata.acquisition_id:
                        self.logger.error("Data acquired is not the one that was expected. Acquisition ID mismatch. Expected %d, Gotten %d" %
                                          (self.acquisition_metadata.acquisition_id, self.received_data_chunk.acquisition_id))
                        next_state = FSMState.DATA_RETRIEVAL_FINISHED

                    elif self.received_data_chunk.rolling_counter != self.read_rolling_counter:
                        self.logger.error("Rolling counter mismatch. Expected %d, gotten %d" %
                                          (self.read_rolling_counter, self.received_data_chunk.rolling_counter))
                        next_state = FSMState.DATA_RETRIEVAL_FINISHED

                    else:
                        self.bytes_received += self.received_data_chunk.data

                        if self.received_data_chunk.finished:
                            assert self.received_data_chunk.crc is not None  # Enforced by protocol

                            computed_crc = crc32(self.bytes_received)
                            if self.received_data_chunk.crc != computed_crc:
                                self.logger.error("CRC mismatch for acquisition. Expected 0x%08x, gotten 0x%08x" %
                                                  (computed_crc, self.received_data_chunk.crc))
                                next_state = FSMState.DATA_RETRIEVAL_FINISHED
                            else:
                                self.data_read_success = True   # Yay! Success!
                                next_state = FSMState.DATA_RETRIEVAL_FINISHED
                        else:
                            if not self.request_pending:
                                self.read_rolling_counter = (self.read_rolling_counter + 1) & 0xFF
                                read_request = self.protocol.datalogging_read_acquisition(
                                    data_read=len(self.bytes_received),
                                    encoding=self.device_setup.encoding,
                                    tx_buffer_size=self.max_response_payload_size,
                                    total_size=self.acquisition_metadata.data_size
                                )
                                self.dispatch(read_request)
                    self.received_data_chunk = None
                else:
                    assert self.max_response_payload_size is not None
                    assert self.acquisition_metadata is not None
                    assert self.device_setup is not None

                    if not self.request_pending:
                        read_request = self.protocol.datalogging_read_acquisition(
                            data_read=len(self.bytes_received),
                            encoding=self.device_setup.encoding,
                            tx_buffer_size=self.max_response_payload_size,
                            total_size=self.acquisition_metadata.data_size
                        )
                        self.dispatch(read_request)

            elif self.state == FSMState.DATA_RETRIEVAL_FINISHED:
                if state_entry:
                    if not self.data_read_success:
                        self.logger.error("Failed to read acquisition. Calling callback with success=False")
                        self.mark_active_acquisition_failed_if_any()
                    else:
                        self.logger.debug("Successfully read the acquisition. Calling callback with success=True")
                        self.mark_active_acquisition_success(self.bytes_received)

                next_state = FSMState.WAIT_FOR_REQUEST
            else:
                raise RuntimeError('Unknown FSM state %s' % str(self.state))

            self.previous_state = self.state
            if next_state != self.state:
                self.logger.debug("Moving state from %s to %s. Last device status reading is %s" %
                                  (self.state.name, next_state.name, self.device_datalogging_state.name))
            self.state = next_state
        except Exception as e:
            self.error = True
            self.logger.error("State machine error: %s" % (str(e)))
            self.logger.debug(traceback.format_exc())

    def dispatch(self, req: Request) -> None:
        """Sends a request to the request dispatcher and assign the corrects completion callbacks"""
        if self.request_pending:    # We don't stack request (even if we could)
            raise RuntimeError("Dispatched a request before having received the previous response")

        self.dispatcher.register_request(
            req,
            SuccessCallback(self.success_callback),
            FailureCallback(self.failure_callback),
            priority=self.request_priority)
        self.request_pending = True
        self.request_failed = False

    def success_callback(self, request: Request, response: Response, params: Any = None) -> None:
        """Called when a request completes and succeeds"""
        self.logger.debug("Success callback. Request=%s. Response Code=%s, Params=%s" % (request, response.code, params))

        if response.code == ResponseCode.OK:
            try:
                subfunction = cmd.DatalogControl.Subfunction(response.subfn)
                if subfunction == cmd.DatalogControl.Subfunction.GetStatus:
                    self.process_get_status_success(response)
                elif subfunction == cmd.DatalogControl.Subfunction.GetSetup:
                    self.process_get_setup_success(response)
                elif subfunction == cmd.DatalogControl.Subfunction.ConfigureDatalog:
                    self.process_configure_success(response)
                elif subfunction == cmd.DatalogControl.Subfunction.ArmTrigger:
                    self.process_arm_success(response)
                elif subfunction == cmd.DatalogControl.Subfunction.GetAcquisitionMetadata:
                    self.process_get_acq_metadata_success(response)
                elif subfunction == cmd.DatalogControl.Subfunction.ReadAcquisition:
                    self.process_read_acquisition_success(response)

            except Exception as e:
                self.error = True
                self.logger.error('Cannot process response. %s' % (str(e)))
                self.logger.debug(traceback.format_exc())
        else:
            self.request_failed = True
            self.logger.error('Request got Nacked. %s' % response.code)

        self.completed()

    def failure_callback(self, request: Request, params: Any = None) -> None:
        """Callback called by the request dispatcher when a request fails to complete"""
        self.logger.debug("Failure callback. Request=%s. Params=%s" % (request, params))
        subfn = cmd.DatalogControl.Subfunction(request.subfn)

        if subfn != cmd.DatalogControl.Subfunction.GetStatus:   # We ignore failures for get status as they are periodic
            self.request_failed = False

        self.completed()

    def completed(self) -> None:
        """ Common code between success and failure"""
        self.request_pending = False

    def process_get_status_success(self, response: Response):
        response_data = cast(protocol_typing.Response.DatalogControl.GetStatus, self.protocol.parse_response(response))

        if self.device_datalogging_state != response_data['state']:
            self.logger.debug("Device datalogging status changed from %s to %s" % (self.device_datalogging_state.name, response_data['state'].name))
        self.device_datalogging_state = response_data['state']
        self.require_status_update = False

    def process_get_setup_success(self, response: Response):
        if self.state != FSMState.GET_SETUP:
            raise RuntimeError('Received a GetSetup response when none was asked')

        response_data = cast(protocol_typing.Response.DatalogControl.GetSetup, self.protocol.parse_response(response))
        self.device_setup = device_datalogging.DataloggingSetup(
            buffer_size=response_data['buffer_size'],
            encoding=response_data['encoding'],
            max_signal_count=response_data['max_signal_count']
        )

    def process_configure_success(self, response: Response):
        if self.state != FSMState.CONFIGURING:
            raise RuntimeError('Received a Configure response when none was asked')

        self.configure_completed = True

    def process_arm_success(self, response: Response):
        if self.state != FSMState.ARMING:
            raise RuntimeError('Received a ArmTrigger response when none was asked')

        self.arm_completed = True

    def process_get_acq_metadata_success(self, response: Response):
        if self.state != FSMState.READ_METADATA:
            raise RuntimeError('Received a GetAcquisitionMetadata response when none was asked')

        response_data = cast(protocol_typing.Response.DatalogControl.GetAcquisitionMetadata,
                             self.protocol.parse_response(response))

        self.acquisition_metadata = device_datalogging.AcquisitionMetadata(
            acquisition_id=response_data['acquisition_id'],
            config_id=response_data['config_id'],
            data_size=response_data['datasize'],
            number_of_points=response_data['nb_points'],
            points_after_trigger=response_data['points_after_trigger']
        )

    def process_read_acquisition_success(self, response: Response):
        if self.state != FSMState.RETRIEVING_DATA:
            raise RuntimeError('Received a ReadAcquisition response when none was asked')

        response_data = cast(protocol_typing.Response.DatalogControl.ReadAcquisition, self.protocol.parse_response(response))
        self.received_data_chunk = ReceivedChunk(
            acquisition_id=response_data['acquisition_id'],
            finished=response_data['finished'],
            crc=response_data['crc'],
            rolling_counter=response_data['rolling_counter'],
            data=response_data['data']
        )
