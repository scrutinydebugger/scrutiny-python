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
    device_setup: Optional[device_datalogging.DataloggingSetup]  # Datalogging capabilities broadcasted by the device
    error: bool     # Indicate that something went wrong
    enabled: bool   # Enable flag, does nothing if set to False
    state: FSMState  # The state of the state machine
    previous_state: FSMState    # Previous state of the state machine
    update_status_timer: Timer  # Time to poll for datalogging status periodically
    device_datalogging_state: device_datalogging.DataloggerState    # The state of the datalogging feature in the device
    # A value between 0 and 1 indicating the percentage of completion of the acquisition. Only valid in TRIGGERED state. None when N/A
    completion_ratio: Optional[float]
    max_response_payload_size: Optional[int]    # Maximum size of a payload that the device can send to the server
    rpv_map: Dict[int, RuntimePublishedValue]   # Map of RPV ID to their definition.

    arm_completed: bool         # Flag indicating the the device trigger was armed. Set by callback, read by FSM
    new_request_received: bool  # Indicates the the datalogging manager pushed a new request for acquisition.
    acquisition_request: Optional[AcquisitionRequest]   # The actively processed acquisition request. Set by callback, read by FSM
    request_failed: bool        # Flag indicating that the previous device request enqueued failed to process. Set by callback, read by FSM
    configure_completed: bool   # Flag indicating that the configuration stage has been successfully completed. Set by callback, read by FSM
    failure_counter: int        # Counter of that counts the number of time the device failed to respond to a request
    data_read_success: bool     # Flag indicating tha the data read request succeeded. Set by callback, read by FSM
    bytes_received: bytearray   # Number of bytes received so far while reading an acquisition content
    read_rolling_counter: int   # The rolling counter read from the last read request
    require_status_update: bool  # Flag indicating that it is time to read the datalogger state
    ready_to_receive_request: bool  # Flag indicating that the poller is ready to receive an acquisition request form the datalogging manager.

    acquisition_metadata: Optional[device_datalogging.AcquisitionMetadata]
    received_data_chunk: Optional[ReceivedChunk]

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
        self.completion_ratio = None

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
        """ Stop the DataloggingPoller """
        self.stop_requested = True

    def disable(self) -> None:
        """Disable the DataloggingPoller"""
        self.enabled = False
        self.stop()

    def enable(self) -> None:
        """Enable the DataloggingPoller"""
        self.enabled = True

    def is_enabled(self) -> bool:
        """Tells if the DataloggingPoller is enabled"""
        return self.enabled

    def get_datalogger_state(self) -> device_datalogging.DataloggerState:
        """Return the last datalogger state read"""
        return self.device_datalogging_state

    def get_device_setup(self) -> Optional[device_datalogging.DataloggingSetup]:
        """Return the datalogging setup structure if available. Contains buffer size, encoding and limits """
        return self.device_setup

    def get_completion_ratio(self) -> Optional[float]:
        """Returns a value between 0 and 1 indicating how far the acquisition is frm being completed once the trigger event has been launched"""
        return self.completion_ratio

    def mark_active_acquisition_failed_if_any(self):
        """Mark the currently processed acquisition request as completed with failure. Will call the completing callback with success=False"""
        if self.acquisition_request is not None:
            self.acquisition_request.completion_callback(False, None)
            self.acquisition_request = None

    def mark_active_acquisition_success(self, data: bytes) -> None:
        """Mark the currently processed acquisition request as completed with success. Will call the completing callback with success=True"""
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
        """Request a new datalogging acquisition. Will interrupt any other request and will be processed as soon as possible """
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
        """Tells if request_acquisition() can be called. """
        return self.ready_to_receive_request and not self.error

    def process(self) -> None:
        """To be called periodically to make the process move forward"""
        # Handle conditions that prevent the DataloggingPoller to function
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

        # Now check if it is time to fetch the datalogger status
        if self.state in [FSMState.WAIT_FOR_DATA]:  # Fast update when waiting for trigger
            self.update_status_timer.set_timeout(self.UPDATE_STATUS_INTERVAL_ACQUIRING)
        else:   # Slow update otherwise
            self.update_status_timer.set_timeout(self.UPDATE_STATUS_INTERVAL_IDLE)

        if not self.request_pending:
            if self.require_status_update or self.update_status_timer.is_timed_out():
                self.dispatch(self.protocol.datalogging_get_status())
                self.update_status_timer.stop()

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
                # We request the device for its datalogging feature configuration (or "setup" to keep vocabulary distinct)
                if state_entry:
                    self.request_failed = False

                if not self.request_pending and self.device_setup is None:
                    self.dispatch(self.protocol.datalogging_get_setup())

                if self.device_setup is not None:   # Set by callback
                    next_state = FSMState.WAIT_FOR_REQUEST
                    self.logger.debug("Datalogging setup received. %s" % (self.device_setup.__dict__))

            elif self.state == FSMState.WAIT_FOR_REQUEST:
                if state_entry:
                    self.ready_to_receive_request = True

                if not self.request_pending:
                    if self.new_request_received:   # Acquisition request pushed by DataloggingManager.
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

                elif self.request_failed:   # Set by callback
                    next_state = FSMState.IDLE

                elif self.configure_completed:  # Set by callback
                    self.configure_completed = False
                    self.dispatch(self.protocol.datalogging_arm_trigger())
                    next_state = FSMState.ARMING

            elif self.state == FSMState.ARMING:  # We arm as soon as configuration phase is complete
                if state_entry:
                    self.arm_completed = False

                # New request interrupts the previous one. Callback already called at this point. (done directly in request_acquisition())
                if self.new_request_received:
                    if not self.request_pending:
                        next_state = FSMState.WAIT_FOR_REQUEST

                elif self.request_failed:   # Set by callback
                    next_state = FSMState.IDLE

                elif self.arm_completed:    # Set by callback
                    next_state = FSMState.WAIT_FOR_DATA

            elif self.state == FSMState.WAIT_FOR_DATA:  # Here we wait for the device to acquire data, it can be long if the trigger condition is never met
                if state_entry:
                    # Since the moving forward condition is based on the device state, we need it to be up-to-date.
                    self.require_status_update = True

                if self.new_request_received:   # New request interrupts the previous one
                    if not self.request_pending:
                        next_state = FSMState.WAIT_FOR_REQUEST

                elif self.require_status_update == False:   # Set by GetStatus callback
                    if self.device_datalogging_state == device_datalogging.DataloggerState.ACQUISITION_COMPLETED:   # We have data!
                        next_state = FSMState.READ_METADATA

            elif self.state == FSMState.READ_METADATA:  # First, we check how much data we need to read so we can split the requests in small chunks
                # Starting from here, we have data. It's beneficial to be resilient to communication problems to reduce chances of important data loss
                if state_entry:
                    self.acquisition_metadata = None
                    self.failure_counter = 0
                    self.request_failed = False

                if self.acquisition_metadata is not None:   # Set by success callback
                    if self.acquisition_metadata.config_id != self.actual_config_id:
                        self.logger.error("Data acquired is not the one that was expected. Config ID mismatch. Expected %d, Gotten %d" %
                                          (self.actual_config_id, self.acquisition_metadata.config_id))
                        next_state = FSMState.WAIT_FOR_REQUEST
                    else:
                        next_state = FSMState.RETRIEVING_DATA

                elif self.request_failed:   # Set by failure callback
                    self.request_failed = False
                    self.failure_counter += 1    # Bit of fault tolerance to increase chances of keeping the data.
                    if self.failure_counter >= self.MAX_FAILURE_WHILE_READING:
                        self.logger.error("Too many communication error. Giving up reading the acquisition")
                        next_state = FSMState.DATA_RETRIEVAL_FINISHED

                elif not self.request_pending:  # Set by callback
                    self.dispatch(self.protocol.datalogging_get_acquisition_metadata())

            elif self.state == FSMState.RETRIEVING_DATA:    # We read the data buffer here. Multiple message exchange will happen
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

                elif self.request_failed:   # Set by failure callback
                    self.request_failed = False
                    self.failure_counter += 1
                    if self.failure_counter >= self.MAX_FAILURE_WHILE_READING:  # Bit of fault tolerance to increase chances of keeping the data.
                        self.logger.error("Too many communication error. Giving up reading the acquisition")
                        next_state = FSMState.DATA_RETRIEVAL_FINISHED

                elif self.received_data_chunk is not None:  # Set by success callback. We got a data chunk.
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

                    else:   # Safety fields are valid, we can process that chunk of data.
                        self.bytes_received += self.received_data_chunk.data

                        if self.received_data_chunk.finished:   # Last chunk
                            assert self.received_data_chunk.crc is not None  # Enforced by protocol

                            computed_crc = crc32(self.bytes_received)
                            if self.received_data_chunk.crc != computed_crc:
                                self.logger.error("CRC mismatch for acquisition. Expected 0x%08x, gotten 0x%08x" %
                                                  (computed_crc, self.received_data_chunk.crc))
                                next_state = FSMState.DATA_RETRIEVAL_FINISHED
                            else:
                                self.data_read_success = True   # Yay! Success!
                                next_state = FSMState.DATA_RETRIEVAL_FINISHED
                        else:   # Still more chunk to go
                            if not self.request_pending:
                                # Request another chunk
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
                    # We launch the first request here.
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
                # Here, retrieving data is finished. It can have succeeded or failed, bit it is finished.
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

        subfunction = cmd.DatalogControl.Subfunction(response.subfn)
        if subfunction == cmd.DatalogControl.Subfunction.GetStatus:
            self.update_status_timer.start()

        if response.code == ResponseCode.OK:
            try:
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
        """Process the response to GetStatus when the device returns OK code"""
        response_data = cast(protocol_typing.Response.DatalogControl.GetStatus, self.protocol.parse_response(response))

        if self.device_datalogging_state != response_data['state']:
            self.logger.debug("Device datalogging status changed from %s to %s" % (self.device_datalogging_state.name, response_data['state'].name))
        self.device_datalogging_state = response_data['state']
        self.completion_ratio = None
        if response_data['byte_counter_since_trigger'] != 0 and response_data['remaining_byte_from_trigger_to_complete'] != 0:
            self.completion_ratio = response_data['byte_counter_since_trigger'] / response_data['remaining_byte_from_trigger_to_complete']
            self.completion_ratio = min(max(self.completion_ratio, 0), 1)

        self.require_status_update = False

    def process_get_setup_success(self, response: Response):
        """Process the response to GetSetup when the device returns OK code"""
        if self.state != FSMState.GET_SETUP:
            raise RuntimeError('Received a GetSetup response when none was asked')

        response_data = cast(protocol_typing.Response.DatalogControl.GetSetup, self.protocol.parse_response(response))
        self.device_setup = device_datalogging.DataloggingSetup(
            buffer_size=response_data['buffer_size'],
            encoding=response_data['encoding'],
            max_signal_count=response_data['max_signal_count']
        )

    def process_configure_success(self, response: Response):
        """Process the response to Configure when the device returns OK code"""
        if self.state != FSMState.CONFIGURING:
            raise RuntimeError('Received a Configure response when none was asked')

        self.configure_completed = True

    def process_arm_success(self, response: Response):
        """Process the response to ArmTrigger when the device returns OK code"""
        if self.state != FSMState.ARMING:
            raise RuntimeError('Received a ArmTrigger response when none was asked')

        self.arm_completed = True

    def process_get_acq_metadata_success(self, response: Response):
        """Process the response to GetAcquisitionMetadata when the device returns OK code"""
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
        """Process the response to ReadAcquisition when the device returns OK code"""
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
