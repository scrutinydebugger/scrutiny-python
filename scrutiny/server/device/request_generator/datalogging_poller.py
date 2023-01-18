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

from scrutiny.server.protocol import *
from scrutiny.server.device.request_dispatcher import RequestDispatcher, SuccessCallback, FailureCallback
import scrutiny.server.datalogging.definitions as datalogging
import scrutiny.server.protocol.typing as protocol_typing
import scrutiny.server.protocol.commands as cmd
from scrutiny.server.tools import Timer
from scrutiny.server.datalogging.definitions import AcquisitionMetadata
from scrutiny.server.protocol.crc32 import crc32

from scrutiny.core.typehints import GenericCallback
from typing import Optional, Any, cast, Callable


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


class AcquisitionRequestCompletionCallback(GenericCallback):
    callback: Callable[[bool, Optional[bytes]], None]


class DataloggingReceiveSetupCallback(GenericCallback):
    callback: Callable[[int, datalogging.Encoding], None]


@dataclass
class AcquisitionRequest:
    loop_id: int
    config: datalogging.Configuration
    completion_callback: AcquisitionRequestCompletionCallback


@dataclass
class ReceivedChunk:
    acquisition_id: int
    crc: Optional[int]
    finished: bool
    rolling_counter: int
    data: bytes


class DataloggingPoller:
    class DeviceSetup:
        encoding: datalogging.Encoding
        buffer_size: int

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
    device_setup: Optional["DataloggingPoller.DeviceSetup"]
    error: bool
    enabled: bool
    state: FSMState
    previous_state: FSMState
    update_status_timer: Timer
    device_datalogging_status: datalogging.DataloggerStatus
    max_response_payload_size: Optional[int]

    arm_completed: bool
    new_request_received: bool
    acquisition_request: Optional[AcquisitionRequest]
    request_failed: bool
    configure_completed: bool
    failure_counter: int
    data_read_success: bool
    bytes_received: bytearray
    read_rolling_counter: int

    acquisition_metadata: Optional[AcquisitionMetadata]
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
        self.device_datalogging_status = DataloggerStatus.IDLE
        self.max_response_payload_size = None
        self.update_status_timer = Timer(self.UPDATE_STATUS_INTERVAL_IDLE)
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
        self.device_datalogging_status = DataloggerStatus.IDLE
        self.failure_counter = 0
        self.data_read_success = False
        self.bytes_received = bytearray()
        self.read_rolling_counter = 0
        self.acquisition_metadata = None

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

    def set_datalogging_callbacks(self, receive_setup: DataloggingReceiveSetupCallback):
        self.receive_setup_callback = receive_setup

    def mark_active_acquisition_failed_if_any(self):
        if self.acquisition_request is not None:
            self.acquisition_request.completion_callback(False, None)
            self.acquisition_request = None

    def mark_active_acquisition_success(self, data: bytes) -> None:
        if self.acquisition_request is not None:
            self.acquisition_request.completion_callback(True, data)
            self.acquisition_request = None

    def request_acquisition(self, loop_id: int, config: datalogging.Configuration, callback: AcquisitionRequestCompletionCallback) -> None:
        if self.max_response_payload_size:
            raise ValueError("Maximum response payload size must be defined first")

        self.mark_active_acquisition_failed_if_any()

        self.acquisition_request = AcquisitionRequest(
            loop_id=loop_id,
            config=config,
            completion_callback=callback
        )

        self.new_request_received = True

    def process(self) -> None:
        """To be called periodically to make the process move forward"""
        if not self.started or not self.enabled:
            self.set_standby()
            return
        elif self.stop_requested and not self.request_pending:
            self.started = False
            self.set_standby()
            return
        elif self.error:
            if self.acquisition_request is not None:
                self.acquisition_request.completion_callback(False, None)
                self.acquisition_request = None
            return

        if self.state in [FSMState.WAIT_FOR_DATA]:  # Fast update when waiting for trigger
            self.update_status_timer.set_timeout(self.UPDATE_STATUS_INTERVAL_ACQUIRING)
        else:   # Slow update otherwise
            self.update_status_timer.set_timeout(self.UPDATE_STATUS_INTERVAL_IDLE)

        if self.update_status_timer.is_timed_out() and not self.request_pending:
            self.dispatch(self.protocol.datalogging_get_status())
            self.update_status_timer.start()

        try:
            if self.state == FSMState.IDLE:
                self.mark_active_acquisition_failed_if_any()
                self.device_setup = None
                self.configure_completed = False
                self.arm_completed = False
                self.update_status_timer.start()
                self.state = FSMState.GET_SETUP

            state_entry = self.previous_state != self.state
            next_state = self.state
            if self.state == FSMState.GET_SETUP:
                if state_entry:
                    self.request_failed = False

                if not self.request_pending and self.device_setup is None:
                    self.dispatch(self.protocol.datalogging_get_setup())

                if self.device_setup is not None:
                    if self.receive_setup_callback is not None:
                        self.receive_setup_callback(buffer_size=self.device_setup.buffer_size, encoding=self.device_setup.encoding)
                    next_state = FSMState.WAIT_FOR_REQUEST

            elif self.state == FSMState.WAIT_FOR_REQUEST:
                if state_entry:
                    self.mark_active_acquisition_failed_if_any()

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
                    next_state = FSMState.WAIT_FOR_REQUEST

                if self.request_failed:
                    next_state = FSMState.IDLE

                if self.configure_completed:
                    self.configure_completed = False
                    self.dispatch(self.protocol.datalogging_arm_trigger())
                    next_state = FSMState.ARMING

            elif self.state == FSMState.ARMING:
                if state_entry:
                    self.arm_completed = False

                if self.request_failed:
                    next_state = FSMState.IDLE

                if self.arm_completed:
                    next_state = FSMState.WAIT_FOR_DATA

            elif self.state == FSMState.WAIT_FOR_DATA:
                if self.new_request_received:   # New request interrupts the previous one
                    next_state = FSMState.WAIT_FOR_REQUEST

                if self.device_datalogging_status == datalogging.DataloggerStatus.ACQUISITION_COMPLETED:
                    next_state = FSMState.READ_METADATA

            elif self.state == FSMState.READ_METADATA:
                # Starting from here, we have previous data, it's beneficial to be resilient to communication problems
                if state_entry:
                    self.acquisition_metadata = None
                    self.failure_counter = 0

                if self.acquisition_metadata is not None:
                    if self.acquisition_metadata.config_id != self.actual_config_id:
                        self.logger.error("Data acquired is not the one that was expected. Config ID mismatch. Expected %d, Gotten %d" %
                                          (self.acquisition_metadata.config_id, self.actual_config_id))
                        next_state = FSMState.WAIT_FOR_REQUEST
                    else:
                        next_state = FSMState.RETRIEVING_DATA
                elif self.request_failed:
                    self.request_failed = False
                    self.failure_counter += 1
                    if self.failure_counter >= self.MAX_FAILURE_WHILE_READING:
                        next_state = FSMState.DATA_RETRIEVAL_FINISHED

                elif not self.request_pending:
                    self.dispatch(self.protocol.datalogging_get_acquisition_metadata())

            elif self.state == FSMState.RETRIEVING_DATA:
                if state_entry:
                    self.data_read_success = False
                    self.request_failed = False
                    self.failure_counter = 0
                    self.received_data_chunk = None

                if self.new_request_received:   # New request interrupts the previous one
                    next_state = FSMState.WAIT_FOR_REQUEST

                elif self.request_failed:
                    self.request_failed = False
                    self.failure_counter += 1
                    if self.failure_counter >= self.MAX_FAILURE_WHILE_READING:
                        next_state = FSMState.DATA_RETRIEVAL_FINISHED

                elif self.received_data_chunk is not None:
                    assert self.max_response_payload_size is not None
                    assert self.acquisition_metadata is not None
                    assert self.device_setup is not None

                    if self.received_data_chunk.acquisition_id != self.acquisition_metadata.acquisition_id:
                        self.logger.error("Data acquired is not the one that was expected. Acquisition ID mismatch. Expected %d, Gotten %d" %
                                          (self.received_data_chunk.acquisition_id, self.acquisition_metadata.acquisition_id))
                        next_state = FSMState.DATA_RETRIEVAL_FINISHED

                    elif self.received_data_chunk.rolling_counter != self.read_rolling_counter:
                        self.logger.error("Rolling counter mismatch. Expected %d, gotten %d" %
                                          (self.received_data_chunk.rolling_counter, self.read_rolling_counter))
                        next_state = FSMState.DATA_RETRIEVAL_FINISHED

                    else:
                        self.bytes_received += self.received_data_chunk.data

                        if self.received_data_chunk.finished:
                            assert self.received_data_chunk.crc is not None  # Enforced by protocol

                            computed_crc = crc32(self.bytes_received)
                            if self.received_data_chunk.crc != computed_crc:
                                self.logger.error("CRC mismatch for acquisition. Expected 0x%08x, gotten 0x%08x" %
                                                  (self.received_data_chunk.crc, computed_crc))
                                next_state = FSMState.DATA_RETRIEVAL_FINISHED
                            else:
                                self.data_read_success = True
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

            elif self.state == FSMState.DATA_RETRIEVAL_FINISHED:
                if state_entry:
                    if not self.data_read_success:
                        self.mark_active_acquisition_failed_if_any()
                    else:
                        self.mark_active_acquisition_success(self.bytes_received)
            else:
                raise RuntimeError('Unknown FSM state %s' % str(self.state))

            self.previous_state = self.state
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
        self.device_datalogging_status = response_data['status']

    def process_get_setup_success(self, response: Response):
        if self.state != FSMState.GET_SETUP:
            raise RuntimeError('Received a GetSetup response when none was asked')

        response_data = cast(protocol_typing.Response.DatalogControl.GetSetup, self.protocol.parse_response(response))
        self.device_setup = DataloggingPoller.DeviceSetup()
        self.device_setup.buffer_size = response_data['buffer_size']
        self.device_setup.encoding = response_data['encoding']

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
