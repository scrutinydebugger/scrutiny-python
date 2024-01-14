#    datalogging_poller.py
#        Component of the Device Handler that handles the datalogging feature within the device.
#        Poll for status, new data and configure the device
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import logging
import traceback
from enum import Enum, auto
from dataclasses import dataclass

from scrutiny.server.protocol import *
from scrutiny.server.device.request_dispatcher import RequestDispatcher, SuccessCallback, FailureCallback
import scrutiny.server.datalogging.definitions.device as device_datalogging
import scrutiny.server.protocol.typing as protocol_typing
import scrutiny.server.protocol.commands as cmd
from scrutiny.tools import Timer
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
    DATA_RETRIEVAL_FINISHED_SUCCESS = auto()
    REQUEST_RESET = auto()


class DeviceAcquisitionRequestCompletionCallback(GenericCallback):
    callback: Callable[[bool, str, Optional[List[List[bytes]]], Optional[device_datalogging.AcquisitionMetadata]], None]


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


DatalogSubfn = cmd.DatalogControl.Subfunction


class DataloggingPoller:

    UPDATE_STATUS_INTERVAL_IDLE = 0.5
    UPDATE_STATUS_INTERVAL_ACQUIRING = 0.2
    MAX_FAILURE_WHILE_READING = 5

    logger: logging.Logger
    dispatcher: RequestDispatcher       # We put the request in here, and we know they'll go out
    protocol: Protocol                  # The actual protocol. Used to build the request payloads
    request_priority: int               # Our dispatcher priority
    stop_requested: bool    # Requested to stop polling
    request_pending: Dict[DatalogSubfn, bool]   # True when we are waiting for a request to complete
    # Flag indicating that the previous device request enqueued failed to process. Set by callback, read by FSM
    request_failed: Dict[DatalogSubfn, bool]
    started: bool           # Indicate if enabled or not
    device_setup: Optional[device_datalogging.DataloggingSetup]  # Datalogging capabilities broadcasted by the device
    error: bool     # Indicate that something went wrong
    enabled: bool   # Enable flag, does nothing if set to False
    state: FSMState  # The state of the state machine
    previous_state: FSMState    # Previous state of the state machine
    update_status_timer: Timer  # Time to poll for datalogging status periodically
    device_datalogging_state: Optional[device_datalogging.DataloggerState]    # The state of the datalogging feature in the device
    # A value between 0 and 1 indicating the percentage of completion of the acquisition. Only valid in TRIGGERED state. None when N/A
    completion_ratio: Optional[float]
    max_response_payload_size: Optional[int]    # Maximum size of a payload that the device can send to the server
    rpv_map: Dict[int, RuntimePublishedValue]   # Map of RPV ID to their definition.

    arm_completed: bool         # Flag indicating the the device trigger was armed. Set by callback, read by FSM
    cancel_requested: bool       # INdicates that the user wants to cancel the active acquisition
    acquisition_request: Optional[AcquisitionRequest]   # The actively processed acquisition request. Set by callback, read by FSM
    configure_completed: bool   # Flag indicating that the configuration stage has been successfully completed. Set by callback, read by FSM
    failure_counter: int        # Counter of that counts the number of time the device failed to respond to a request
    bytes_received: bytearray   # Number of bytes received so far while reading an acquisition content
    read_rolling_counter: int   # The rolling counter read from the last read request
    require_status_update: bool  # Flag indicating that it is time to read the datalogger state
    setup_completed: bool       # Flag indicating that the poller is ready to receive an acquisition request form the datalogging manager.
    reset_completed: bool      # Indicate that the requested reset command has completed successfully.

    acquisition_metadata: Optional[device_datalogging.AcquisitionMetadata]
    received_data_chunk: Optional[ReceivedChunk]

    def __init__(self, protocol: Protocol, dispatcher: RequestDispatcher, request_priority: int):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self.protocol = protocol
        self.request_priority = request_priority
        self.acquisition_request = None
        self.reset()

    def reset(self) -> None:
        """Put back the datalogging poller to its startup state"""
        self.logger.debug('Reset called')
        self.mark_active_acquisition_failed_if_any("Datalogger has been reset")    # Call user callback if required
        self.acquisition_request = None
        self.enabled = True
        self.actual_config_id = 0
        self.max_response_payload_size = None
        self.update_status_timer = Timer(self.UPDATE_STATUS_INTERVAL_IDLE)
        self.rpv_map = {}
        self.request_pending = {}
        self.request_failed = {}
        self.reset_completed = False
        for subfn in DatalogSubfn:
            self.request_pending[subfn] = False
            self.request_failed[subfn] = False
        self.set_standby()

    def set_standby(self) -> None:
        """Put back the datalogging poller to an idle state without destroying important internal values"""
        self.mark_active_acquisition_failed_if_any("Datalogger is disabled")

        self.started = False
        self.stop_requested = False
        for k in self.request_pending:
            self.request_pending[k] = False
            self.request_failed[k] = False
        self.device_setup = None
        self.error = False
        self.state = FSMState.IDLE
        self.previous_state = FSMState.IDLE
        self.cancel_requested = False
        self.acquisition_request = None
        self.configure_completed = False
        self.arm_completed = False
        self.update_status_timer.stop()
        self.device_datalogging_state = None    # Unknown
        self.failure_counter = 0
        self.bytes_received = bytearray()
        self.read_rolling_counter = 0
        self.acquisition_metadata = None
        self.require_status_update = False
        self.setup_completed = False
        self.completion_ratio = None

    def configure_rpvs(self, rpvs: List[RuntimePublishedValue]) -> None:
        self.rpv_map.clear()
        for rpv in rpvs:
            self.rpv_map[rpv.id] = rpv

        self.logger.debug("RPV map configured with %d RPV" % len(self.rpv_map))

    def set_max_response_payload_size(self, max_response_payload_size: int) -> None:
        self.max_response_payload_size = max_response_payload_size

    def start(self) -> None:
        """ Launch polling of data """
        if self.enabled:
            self.started = True

    def is_started(self) -> bool:
        return self.started and self.enabled and not self.stop_requested

    def is_in_error(self) -> bool:
        return self.error

    def fully_stopped(self) -> bool:
        return not self.started and not self.stop_requested

    def stop(self) -> None:
        """ Stop the DataloggingPoller """
        self.logger.debug('Stop requested')
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

    def get_datalogger_state(self) -> Optional[device_datalogging.DataloggerState]:
        """Return the last datalogger state read"""
        return self.device_datalogging_state

    def get_device_setup(self) -> Optional[device_datalogging.DataloggingSetup]:
        """Return the datalogging setup structure if available. Contains buffer size, encoding and limits """
        return self.device_setup

    def get_completion_ratio(self) -> Optional[float]:
        """Returns a value between 0 and 1 indicating how far the acquisition is frm being completed once the trigger event has been launched"""
        return self.completion_ratio

    def mark_active_acquisition_failed_if_any(self, detail: str = "") -> None:
        """Mark the currently processed acquisition request as completed with failure. Will call the completing callback with success=False"""
        if self.acquisition_request is not None:
            self.acquisition_request.completion_callback(False, detail, None, None)
            self.acquisition_request = None

    def mark_active_acquisition_success(self, data: bytes, acquisition_meta: device_datalogging.AcquisitionMetadata) -> None:
        """Mark the currently processed acquisition request as completed with success. Will call the completing callback with success=True"""
        if self.acquisition_request is not None:
            if self.device_setup is None:
                self.acquisition_request.completion_callback(False, "Device configuration is not available", None, None)
                self.logger.error("Cannot mark acquisition successfully completed as no device setup is available")
            else:
                try:
                    deinterleaved_data = extract_signal_from_data(
                        data=data,
                        config=self.acquisition_request.config,
                        rpv_map=self.rpv_map,
                        encoding=self.device_setup.encoding)
                    self.acquisition_request.completion_callback(True, "", deinterleaved_data, acquisition_meta)
                except Exception as e:
                    self.logger.error("Failed to parse data received from device datalogging acquisition. %s" % str(e))
                    self.logger.debug(traceback.format_exc())
                    self.acquisition_request.completion_callback(False, "Data received from the device cannot be parsed", None, None)

            self.acquisition_request = None

    def request_acquisition(self, loop_id: int, config: device_datalogging.Configuration, callback: DeviceAcquisitionRequestCompletionCallback) -> None:
        """Request a new datalogging acquisition. Will interrupt any other request and will be processed as soon as possible """
        if not self.max_response_payload_size:
            raise ValueError("Maximum response payload size must be defined first")

        if not self.is_ready_to_receive_new_request():
            if not self.started:
                raise RuntimeError("Datalogging poller is not started")

            raise RuntimeError("Not ready to receive a new acquisition request")

        assert self.device_setup is not None    # Will be set if is_ready_to_receive_new_request() returns True
        if len(config.get_signals()) > self.device_setup.max_signal_count:
            raise ValueError("Too many signals in configuration. Maximum = %d" % self.device_setup.max_signal_count)

        if self.acquisition_request is not None:
            raise RuntimeError("Cannot request for a new acquisition while one is being acquired")

        self.acquisition_request = AcquisitionRequest(
            loop_id=loop_id,
            config=config,
            completion_callback=callback
        )

    def cancel_acquisition_request(self) -> None:
        """Request the state machine to cancel the active request and go through a device datalogger reset"""
        if self.acquisition_request is not None:
            self.cancel_requested = True
            self.logger.debug("Cancel requested")

    def cancel_in_progress(self) -> bool:
        """Tells if a cancel as been requested and is still processing"""
        return self.cancel_requested

    def request_in_progress(self) -> bool:
        return self.acquisition_request is not None

    def is_ready_to_receive_new_request(self) -> bool:
        """Tells if request_acquisition() can be called. """
        return self.started and self.setup_completed and not self.error and not self.cancel_requested and not self.stop_requested

    def process(self) -> None:
        """To be called periodically to make the process move forward"""
        # Handle conditions that prevent the DataloggingPoller to function
        if not self.started or not self.enabled:
            self.set_standby()
            return
        elif self.stop_requested:
            self.mark_active_acquisition_failed_if_any("Datalogging has been asked to stop")
            if not self.has_any_request_pending():
                self.logger.debug("Stop completed. Going standby")
                self.set_standby()

            return
        elif self.error:    # only way out is a reset
            self.mark_active_acquisition_failed_if_any("Datalogging module made an error")
            return

        # Now check if it is time to fetch the datalogger status
        if self.state in [FSMState.WAIT_FOR_DATA]:  # Fast update when waiting for trigger
            self.update_status_timer.set_timeout(self.UPDATE_STATUS_INTERVAL_ACQUIRING)
        else:   # Slow update otherwise
            self.update_status_timer.set_timeout(self.UPDATE_STATUS_INTERVAL_IDLE)

        if not self.request_pending[DatalogSubfn.GetStatus]:
            if self.require_status_update or self.update_status_timer.is_timed_out():
                self.dispatch(self.protocol.datalogging_get_status())
                self.update_status_timer.stop()

        try:
            state_entry = self.previous_state != self.state
            next_state = self.state

            if self.state == FSMState.IDLE:
                self.mark_active_acquisition_failed_if_any("Datalogging state machine is being reset")
                self.device_setup = None
                self.setup_completed = False
                if self.update_status_timer.is_stopped():
                    self.update_status_timer.start()
                next_state = FSMState.GET_SETUP

            elif self.state == FSMState.GET_SETUP:
                # We request the device for its datalogging feature configuration (or "setup" to keep vocabulary distinct)
                if state_entry:
                    self.request_failed[DatalogSubfn.GetSetup] = False

                if self.request_failed[DatalogSubfn.GetSetup] or self.device_datalogging_state == device_datalogging.DataloggerState.ERROR:
                    next_state = FSMState.REQUEST_RESET

                elif self.device_setup is None:   # Set by callback
                    if not self.request_pending[DatalogSubfn.GetSetup]:
                        self.dispatch(self.protocol.datalogging_get_setup())
                else:
                    next_state = FSMState.WAIT_FOR_REQUEST  # No need to clear the first time.
                    self.logger.debug("Datalogging setup received. %s" % (self.device_setup.__dict__))

            elif self.state == FSMState.REQUEST_RESET:
                if state_entry:
                    msg = "Datalogger has been reset"
                    if self.cancel_requested:
                        msg = "Acquisition got canceled"
                    self.mark_active_acquisition_failed_if_any(msg)
                    self.reset_completed = False
                    self.request_failed[DatalogSubfn.ResetDatalogger] = False
                    if self.request_pending[DatalogSubfn.ResetDatalogger]:
                        self.logger.error("More than one reset request were stacked. Should not happen")

                if not self.reset_completed:
                    if self.request_failed[DatalogSubfn.ResetDatalogger]:
                        next_state = FSMState.IDLE

                    elif not self.request_pending[DatalogSubfn.ResetDatalogger]:
                        self.dispatch(self.protocol.datalogging_reset_datalogger())
                else:
                    self.cancel_requested = False
                    next_state = FSMState.WAIT_FOR_REQUEST

            elif self.state == FSMState.WAIT_FOR_REQUEST:
                if state_entry:
                    self.setup_completed = True
                    self.require_status_update = True

                # No need to ask the device for a reset. But we need to tell the user of the completion failure
                if self.cancel_requested:
                    self.mark_active_acquisition_failed_if_any("Acquisition got canceled")
                    self.cancel_requested = False

                elif self.require_status_update == False:  # Avoid loop between WAIT_REQUEST and REQUEST_RESET
                    if self.device_datalogging_state == device_datalogging.DataloggerState.ERROR:
                        next_state = FSMState.REQUEST_RESET

                    elif not self.request_pending[DatalogSubfn.ConfigureDatalog]:
                        if self.acquisition_request is not None:   # Acquisition request pushed by DataloggingManager.
                            # Validation token associated with acquisition by the device.
                            self.actual_config_id = (self.actual_config_id + 1) & 0xFFFF
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

                if self.cancel_requested:
                    if not self.request_pending[DatalogSubfn.ConfigureDatalog]:
                        next_state = FSMState.REQUEST_RESET

                elif self.request_failed[DatalogSubfn.ConfigureDatalog] or self.device_datalogging_state == device_datalogging.DataloggerState.ERROR:
                    next_state = FSMState.REQUEST_RESET

                elif self.configure_completed:  # Set by callback
                    self.configure_completed = False
                    assert self.request_pending[DatalogSubfn.ConfigureDatalog] == False
                    self.dispatch(self.protocol.datalogging_arm_trigger())
                    next_state = FSMState.ARMING

            elif self.state == FSMState.ARMING:  # We arm as soon as configuration phase is complete
                if state_entry:
                    self.arm_completed = False

                # New request interrupts the previous one. Callback already called at this point. (done directly in request_acquisition())
                if self.cancel_requested:
                    if not self.request_pending[DatalogSubfn.ArmTrigger]:
                        next_state = FSMState.REQUEST_RESET

                elif self.request_failed[DatalogSubfn.ArmTrigger] or self.device_datalogging_state == device_datalogging.DataloggerState.ERROR:
                    next_state = FSMState.REQUEST_RESET

                elif self.arm_completed:    # Set by callback
                    assert self.request_pending[DatalogSubfn.ArmTrigger] == False
                    next_state = FSMState.WAIT_FOR_DATA

            elif self.state == FSMState.WAIT_FOR_DATA:  # Here we wait for the device to acquire data, it can be long if the trigger condition is never met
                if state_entry:
                    # Since the moving forward condition is based on the device state, we need it to be up-to-date.
                    self.require_status_update = True

                if self.cancel_requested:   # New request interrupts the previous one
                    next_state = FSMState.REQUEST_RESET

                elif self.device_datalogging_state == device_datalogging.DataloggerState.ERROR:
                    next_state = FSMState.REQUEST_RESET

                elif self.require_status_update == False:   # Set by GetStatus callback
                    if self.device_datalogging_state is None:
                        raise RuntimeError("Datalogger state is None even after being updated")

                    if self.device_datalogging_state == device_datalogging.DataloggerState.ACQUISITION_COMPLETED:   # We have data!
                        next_state = FSMState.READ_METADATA

            elif self.state == FSMState.READ_METADATA:  # First, we check how much data we need to read so we can split the requests in small chunks
                # Starting from here, we have data. It's beneficial to be resilient to communication problems to reduce chances of important data loss
                if state_entry:
                    self.acquisition_metadata = None
                    self.failure_counter = 0
                    self.request_failed[DatalogSubfn.GetAcquisitionMetadata] = False

                if self.device_datalogging_state == device_datalogging.DataloggerState.ERROR:
                    next_state = FSMState.REQUEST_RESET

                elif self.acquisition_metadata is not None:   # Set by success callback
                    assert self.request_pending[DatalogSubfn.GetAcquisitionMetadata] == False
                    if self.acquisition_metadata.config_id != self.actual_config_id:
                        self.logger.error("Data acquired is not the one that was expected. Config ID mismatch. Expected %d, Gotten %d" %
                                          (self.actual_config_id, self.acquisition_metadata.config_id))
                        next_state = FSMState.REQUEST_RESET
                    else:
                        next_state = FSMState.RETRIEVING_DATA

                elif self.request_failed[DatalogSubfn.GetAcquisitionMetadata]:   # Set by failure callback
                    self.request_failed[DatalogSubfn.GetAcquisitionMetadata] = False
                    self.failure_counter += 1    # Bit of fault tolerance to increase chances of keeping the data.
                    if self.failure_counter >= self.MAX_FAILURE_WHILE_READING:
                        self.logger.error("Too many communication error. Giving up reading the acquisition")
                        next_state = FSMState.REQUEST_RESET

                elif not self.request_pending[DatalogSubfn.GetAcquisitionMetadata]:  # Set by callback
                    self.dispatch(self.protocol.datalogging_get_acquisition_metadata())

            elif self.state == FSMState.RETRIEVING_DATA:    # We read the data buffer here. Multiple message exchange will happen
                if state_entry:
                    self.request_failed[DatalogSubfn.ReadAcquisition] = False
                    self.failure_counter = 0
                    self.read_rolling_counter = 0
                    self.received_data_chunk = None
                    self.bytes_received = bytearray()

                if self.cancel_requested:   # New request interrupts the previous one
                    if not self.request_pending[DatalogSubfn.ReadAcquisition]:
                        self.must_send_read_data_request = False
                        next_state = FSMState.REQUEST_RESET

                elif self.device_datalogging_state == device_datalogging.DataloggerState.ERROR:
                    next_state = FSMState.REQUEST_RESET

                elif self.request_failed[DatalogSubfn.ReadAcquisition]:   # Set by failure callback
                    self.request_failed[DatalogSubfn.ReadAcquisition] = False
                    self.failure_counter += 1
                    if self.failure_counter >= self.MAX_FAILURE_WHILE_READING:  # Bit of fault tolerance to increase chances of keeping the data.
                        self.logger.error("Too many communication error. Giving up reading the acquisition")
                        next_state = FSMState.REQUEST_RESET

                elif self.received_data_chunk is not None:  # Set by success callback. We got a data chunk.
                    assert self.max_response_payload_size is not None
                    assert self.acquisition_metadata is not None
                    assert self.device_setup is not None

                    if self.received_data_chunk.acquisition_id != self.acquisition_metadata.acquisition_id:
                        self.logger.error("Data acquired is not the one that was expected. Acquisition ID mismatch. Expected %d, Gotten %d" %
                                          (self.acquisition_metadata.acquisition_id, self.received_data_chunk.acquisition_id))
                        next_state = FSMState.REQUEST_RESET

                    elif self.received_data_chunk.rolling_counter != self.read_rolling_counter:
                        self.logger.error("Rolling counter mismatch. Expected %d, gotten %d" %
                                          (self.read_rolling_counter, self.received_data_chunk.rolling_counter))
                        next_state = FSMState.REQUEST_RESET

                    else:   # Safety fields are valid, we can process that chunk of data.
                        self.bytes_received += self.received_data_chunk.data

                        if self.received_data_chunk.finished:   # Last chunk
                            assert self.received_data_chunk.crc is not None  # Enforced by protocol

                            computed_crc = crc32(self.bytes_received)
                            if self.received_data_chunk.crc != computed_crc:
                                self.logger.error("CRC mismatch for acquisition. Expected 0x%08x, gotten 0x%08x" %
                                                  (computed_crc, self.received_data_chunk.crc))
                                next_state = FSMState.REQUEST_RESET
                            else:
                                next_state = FSMState.DATA_RETRIEVAL_FINISHED_SUCCESS
                        else:   # Still more chunk to go
                            # Request another chunk
                            if not self.request_pending[DatalogSubfn.ReadAcquisition]:
                                self.read_rolling_counter = (self.read_rolling_counter + 1) & 0xFF
                                self.logger.debug("Increasing rolling counter: %d" % self.read_rolling_counter)
                                read_request = self.protocol.datalogging_read_acquisition(
                                    data_read=len(self.bytes_received),
                                    encoding=self.device_setup.encoding,
                                    tx_buffer_size=self.max_response_payload_size,
                                    total_size=self.acquisition_metadata.data_size
                                )
                                self.dispatch(read_request)
                    self.received_data_chunk = None
                elif len(self.bytes_received) == 0:
                    # We launch the first request here.
                    assert self.max_response_payload_size is not None
                    assert self.acquisition_metadata is not None
                    assert self.device_setup is not None
                    if not self.request_pending[DatalogSubfn.ReadAcquisition]:
                        read_request = self.protocol.datalogging_read_acquisition(
                            data_read=len(self.bytes_received),
                            encoding=self.device_setup.encoding,
                            tx_buffer_size=self.max_response_payload_size,
                            total_size=self.acquisition_metadata.data_size
                        )
                        self.dispatch(read_request)

            elif self.state == FSMState.DATA_RETRIEVAL_FINISHED_SUCCESS:
                # Here, retrieving data is finished. It can have succeeded or failed, bit it is finished.
                if state_entry:
                    assert self.request_pending[DatalogSubfn.ReadAcquisition] == False
                    assert self.acquisition_metadata is not None
                    self.logger.debug("Successfully read the acquisition. Calling callback with success=True")
                    self.mark_active_acquisition_success(self.bytes_received, self.acquisition_metadata)

                next_state = FSMState.REQUEST_RESET  # Make sure to restart in a known state. Reset even if everything was fine
            else:
                raise RuntimeError('Unknown FSM state %s' % str(self.state))

            self.previous_state = self.state
            if next_state != self.state:
                device_state_name = self.device_datalogging_state if self.device_datalogging_state is not None else "<None>"
                self.logger.debug("Moving state from %s to %s. Last device status reading is %s" %
                                  (self.state.name, next_state.name, device_state_name))
            self.state = next_state
        except Exception as e:
            self.error = True
            self.logger.critical("State machine error: %s" % (str(e)))
            self.logger.debug(traceback.format_exc())

    def dispatch(self, req: Request) -> None:
        """Sends a request to the request dispatcher and assign the corrects completion callbacks"""
        subfn = DatalogSubfn(req.subfn)
        if self.request_pending[subfn]:    # We don't stack request (even if we could)
            raise RuntimeError(
                "Dispatched a request of subfunction %s before having received the previous response of the same subfunction" % subfn.name)

        self.dispatcher.register_request(
            req,
            SuccessCallback(self.success_callback),
            FailureCallback(self.failure_callback),
            priority=self.request_priority)
        self.request_pending[subfn] = True
        self.request_failed[subfn] = False

    def success_callback(self, request: Request, response: Response, params: Any = None) -> None:
        """Called when a request completes and succeeds"""
        self.logger.debug("Success callback. Request=%s. Response Code=%s, Params=%s" % (request, response.code, params))

        subfunction = DatalogSubfn(response.subfn)

        if response.code == ResponseCode.OK:
            try:
                if subfunction == DatalogSubfn.GetStatus:
                    self.process_get_status_success(response)
                elif subfunction == DatalogSubfn.GetSetup:
                    self.process_get_setup_success(response)
                elif subfunction == DatalogSubfn.ConfigureDatalog:
                    self.process_configure_success(response)
                elif subfunction == DatalogSubfn.ArmTrigger:
                    self.process_arm_success(response)
                elif subfunction == DatalogSubfn.GetAcquisitionMetadata:
                    self.process_get_acq_metadata_success(response)
                elif subfunction == DatalogSubfn.ReadAcquisition:
                    self.process_read_acquisition_success(response)
                elif subfunction == DatalogSubfn.ResetDatalogger:
                    self.process_reset_datalogger_success(response)

            except Exception as e:
                self.error = True
                self.logger.error('Cannot process response. %s' % (str(e)))
                self.logger.debug(traceback.format_exc())
        else:
            self.request_failed[subfunction] = True
            self.logger.error('Request got Nacked. %s' % response.code)

        self.completed(request)

    def failure_callback(self, request: Request, params: Any = None) -> None:
        """Callback called by the request dispatcher when a request fails to complete"""
        self.logger.debug("Failure callback. Request=%s. Params=%s" % (request, params))
        subfn = DatalogSubfn(request.subfn)
        self.request_failed[subfn] = True

        self.completed(request)

    def completed(self, request: Request) -> None:
        """ Common code between success and failure"""
        subfn = DatalogSubfn(request.subfn)
        if subfn == DatalogSubfn.GetStatus:
            self.update_status_timer.start()
        self.request_pending[subfn] = False

    def process_get_status_success(self, response: Response) -> None:
        """Process the response to GetStatus when the device returns OK code"""
        response_data = cast(protocol_typing.Response.DatalogControl.GetStatus, self.protocol.parse_response(response))

        datalogging_state_name = self.device_datalogging_state if self.device_datalogging_state is not None else "<None>"
        if self.device_datalogging_state != response_data['state']:
            self.logger.debug("Device datalogging status changed from %s to %s" % (datalogging_state_name, response_data['state'].name))
        self.device_datalogging_state = response_data['state']
        self.completion_ratio = None
        if response_data['byte_counter_since_trigger'] != 0 and response_data['remaining_byte_from_trigger_to_complete'] != 0:
            self.completion_ratio = response_data['byte_counter_since_trigger'] / response_data['remaining_byte_from_trigger_to_complete']
            self.completion_ratio = min(max(self.completion_ratio, 0), 1)

        self.require_status_update = False

    def process_get_setup_success(self, response: Response) -> None:
        """Process the response to GetSetup when the device returns OK code"""
        if self.state != FSMState.GET_SETUP:
            raise RuntimeError('Received a GetSetup response when none was asked')

        response_data = cast(protocol_typing.Response.DatalogControl.GetSetup, self.protocol.parse_response(response))
        self.device_setup = device_datalogging.DataloggingSetup(
            buffer_size=response_data['buffer_size'],
            encoding=response_data['encoding'],
            max_signal_count=response_data['max_signal_count']
        )

    def process_configure_success(self, response: Response) -> None:
        """Process the response to Configure when the device returns OK code"""
        if self.state != FSMState.CONFIGURING:
            raise RuntimeError('Received a Configure response when none was asked')

        self.configure_completed = True

    def process_arm_success(self, response: Response) -> None:
        """Process the response to ArmTrigger when the device returns OK code"""
        if self.state != FSMState.ARMING:
            raise RuntimeError('Received a ArmTrigger response when none was asked')

        self.arm_completed = True

    def process_get_acq_metadata_success(self, response: Response) -> None:
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

    def process_read_acquisition_success(self, response: Response) -> None:
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

    def process_reset_datalogger_success(self, response: Response) -> None:
        """Process the response to ResetDatalogger when the device returns OK code"""
        if self.state != FSMState.REQUEST_RESET:
            raise RuntimeError('Received a ResetDatalogger response when none was asked')

        self.reset_completed = True

    def has_any_request_pending(self) -> bool:
        for k in self.request_pending:
            if self.request_pending[k]:
                return True
        return False
