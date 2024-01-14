#    datalogging_manager.py
#        The main server components that manages the datalogging feature at high level
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import queue
import logging
import math
from dataclasses import dataclass
from uuid import uuid4
from datetime import datetime
import traceback
import enum

import scrutiny.server.datalogging.definitions.api as api_datalogging
import scrutiny.server.datalogging.definitions.device as device_datalogging
from scrutiny.server.device.device_handler import DeviceHandler, DeviceAcquisitionRequestCompletionCallback
from scrutiny.server.datastore.datastore_entry import DatastoreEntry, DatastoreAliasEntry, DatastoreRPVEntry, DatastoreVariableEntry
from scrutiny.server.datastore.datastore import Datastore
from scrutiny.server.device.device_info import FixedFreqLoop, ExecLoopType
from scrutiny.core.basic_types import *
from scrutiny.server.datalogging.datalogging_storage import DataloggingStorage
from scrutiny.core.sfd_storage import SFDStorage
from scrutiny.core.codecs import Codecs
from scrutiny.core.datalogging import DataloggingAcquisition, DataSeries, AxisDefinition

from typing import Optional, List, Dict, Tuple, cast


class FsmState(enum.Enum):
    INIT = enum.auto()
    WAIT_DEVICE_CONNECTED = enum.auto()
    WAIT_DATALOGGING_READY = enum.auto()
    DEVICE_CONNECTED_WITH_DATALOGGING = enum.auto()
    DEVICE_CONNECTED_NO_DATALOGGING = enum.auto()
    CLEAR_ERROR = enum.auto()
    SHUTDOWN_WAIT_REQ_PROCESSED = enum.auto()
    SHUTDOWN_CLEAR_PENDING_REQUEST = enum.auto()


@dataclass
class DeviceSideAcquisitionRequest:
    api_request: api_datalogging.AcquisitionRequest
    device_config: device_datalogging.Configuration
    entry_signal_map: Dict[DatastoreEntry, int]
    callback: api_datalogging.APIAcquisitionRequestCompletionCallback


class DataloggingManager:
    datastore: Datastore    # Reference to the server datastore
    device_handler: DeviceHandler   # Reference to the device handler
    acquisition_request_queue: "queue.Queue[DeviceSideAcquisitionRequest]"  # The queue in which acquisition requests are put in by the API
    active_request: Optional[DeviceSideAcquisitionRequest]  # The acquisition request being actively processed. None when no request is processed
    logger: logging.Logger  # Logger
    state: FsmState
    previous_state: FsmState

    TIME_PRECISION_DIGIT = 9    # Device precision is 1e-7. 9 digits is more than enough.

    def __init__(self, datastore: Datastore, device_handler: DeviceHandler):
        self.datastore = datastore
        self.device_handler = device_handler
        self.logger = logging.getLogger(self.__class__.__name__)
        self.acquisition_request_queue = queue.Queue()
        self.active_request = None
        self.state = FsmState.INIT
        self.previous_state = FsmState.INIT
        DataloggingStorage.initialize()

    def is_valid_sample_rate_id(self, identifier: int) -> bool:
        """Tells if the given sample rate identifier refers to a valid datalogging sample rate"""
        for rate in self.get_available_sampling_rates():
            if rate.device_identifier == identifier:
                return True

        return False

    def is_ready_for_request(self) -> bool:
        """Tells if the device is in a state where datalogging request can be accepted"""
        device_connected = self.device_handler.get_connection_status() == DeviceHandler.ConnectionStatus.CONNECTED_READY
        device_handler_ready = self.device_handler.is_ready_for_datalogging_acquisition_request()
        return device_connected and device_handler_ready  # device_handler_ready should be enough. Check device_connected because of paranoia

    def request_acquisition(self, request: api_datalogging.AcquisitionRequest, callback: api_datalogging.APIAcquisitionRequestCompletionCallback) -> None:
        """Interface for the API to push a request for a new acquisition"""
        # Converts right away to device side acquisition because we want exception to be raised as early as possible for quick feedback to user
        config, entry_signal_map = self.make_device_config_from_request(request)  # Can raise an exception

        sampling_rate = self.get_sampling_rate(request.rate_identifier)
        if sampling_rate.rate_type == ExecLoopType.VARIABLE_FREQ and request.x_axis_type == api_datalogging.XAxisType.IdealTime:
            raise ValueError("Cannot use Ideal Time on variable sampling rate")

        if self.device_handler.get_connection_status() != DeviceHandler.ConnectionStatus.CONNECTED_READY:
            raise RuntimeError("No device connected")

        self.acquisition_request_queue.put(DeviceSideAcquisitionRequest(
            api_request=request,
            device_config=config,
            entry_signal_map=entry_signal_map,
            callback=callback), block=False)

    def acquisition_complete_callback(self, success: bool, detail_msg: str, data: Optional[List[List[bytes]]], metadata: Optional[device_datalogging.AcquisitionMetadata]) -> None:
        """Callback called by the device handler when the acquisition finally gets triggered and data has finished downloaded."""
        if self.active_request is None:
            self.logger.error("Received acquisition data but was not expecting it. No active acquisition request")
            return

        acquisition: Optional[DataloggingAcquisition] = None
        try:
            if success:  # The device succeeded to complete the acquisition and fetch the data
                self.logger.info("New datalogging acquisition ready")
                assert data is not None
                assert metadata is not None

                device_info = self.device_handler.get_device_info()
                if device_info is None or device_info.device_id is None:
                    self.logger.error('Gotten an acquisition but the device information is not available')
                    self.active_request.callback(False, "Internal error", None)   # Inform the API of the failure
                    return

                # Make sure all signal data have the same length.
                nb_points: Optional[int] = None
                for signal_data in data:
                    if nb_points is None:
                        nb_points = len(signal_data)
                    else:
                        if nb_points != len(signal_data):
                            raise ValueError('Non-matching data length received in new acquisition')

                if nb_points is None:
                    raise ValueError('Cannot determine the number of points in the acquisitions')

                firmware_name: Optional[str] = None
                if SFDStorage.is_installed(device_info.device_id):
                    sfd_metadata = SFDStorage.get_metadata(device_info.device_id)
                    if 'project_name' in sfd_metadata:
                        firmware_name = sfd_metadata["project_name"]
                        if 'version' in sfd_metadata:
                            firmware_name += " V%s" % sfd_metadata["version"]
                # Crate the acquisition
                acquisition = DataloggingAcquisition(
                    name=self.active_request.api_request.name,
                    reference_id=uuid4().hex,
                    firmware_id=device_info.device_id,
                    acq_time=datetime.now(),
                    firmware_name=firmware_name
                )

                # Now converts binary data into meaningful value using the datastore entries and add to acquisition object
                for signal in self.active_request.api_request.signals:
                    parsed_data = self.read_active_request_data_from_raw_data(signal, data)  # Parse binary data
                    ds = DataSeries(
                        data=parsed_data,
                        logged_element=signal.entry.display_path
                    )
                    if signal.name:
                        ds.name = signal.name
                    acquisition.add_data(ds, signal.axis)

                # Add the X-Axis. Either use a measured signal or use a generated one of the user wants IdealTime
                xaxis = DataSeries()
                if self.active_request.api_request.x_axis_type == api_datalogging.XAxisType.Indexed:
                    xaxis.set_data([i for i in range(nb_points)])
                    xaxis.name = 'Index'
                    xaxis.logged_element = 'Index'
                elif self.active_request.api_request.x_axis_type == api_datalogging.XAxisType.IdealTime:
                    # Ideal time : Generate a time X-Axis based on the sampling rate. Assume the device is running the loop at a reliable fixed rate
                    sampling_rate = self.get_sampling_rate(self.active_request.api_request.rate_identifier)
                    if sampling_rate.frequency is None:
                        raise ValueError('Ideal time X-Axis is not possible with variable frequency loops')
                    timestep = 1 / sampling_rate.frequency
                    timestep *= self.active_request.api_request.decimation
                    xaxis.set_data([round(i * timestep, self.TIME_PRECISION_DIGIT) for i in range(nb_points)])
                    xaxis.name = 'Time (ideal)'
                    xaxis.logged_element = 'Time (ideal)'
                elif self.active_request.api_request.x_axis_type == api_datalogging.XAxisType.MeasuredTime:
                    # Measured time is appended at the end of the signal list. See make_device_config_from_request
                    time_data = data[-1]
                    if (len(time_data)) < 1:
                        raise ValueError('Bad measured time')
                    time_codec = Codecs.get(EmbeddedDataType.uint32, endianness=Endianness.Big)
                    first_sample = time_codec.decode(time_data[0])
                    xaxis.set_data([(time_codec.decode(sample) - first_sample) * 1e-7 for sample in time_data])
                    xaxis.name = 'Time (measured)'
                    xaxis.logged_element = 'Time (measured)'
                elif self.active_request.api_request.x_axis_type == api_datalogging.XAxisType.Signal:
                    # Any other signal. Use the data as is.
                    xaxis_signal = self.active_request.api_request.x_axis_signal
                    assert xaxis_signal is not None
                    if xaxis_signal.name is None:
                        xaxis_signal = api_datalogging.SignalDefinition(name='X-Axis', entry=xaxis_signal.entry)
                    assert xaxis_signal.name is not None
                    parsed_data = self.read_active_request_data_from_raw_data(xaxis_signal, data)
                    xaxis.set_data(parsed_data)
                    xaxis.name = xaxis_signal.name
                    xaxis.logged_element = xaxis_signal.entry.get_display_path()
                else:
                    raise ValueError('Impossible X-Axis type')

                if len(xaxis) != nb_points:
                    raise ValueError("Failed to find a matching xaxis dataseries")

                acquisition.set_xdata(xaxis)
                # -1 because index is 0 based.   -1 because we have the number of points AFTER the trigger, excluding the trigger.  So total of -2
                trigger_index = max(0, min(metadata.number_of_points - metadata.points_after_trigger, metadata.number_of_points - 2))
                acquisition.set_trigger_index(trigger_index)
                DataloggingStorage.save(acquisition)
            else:
                # acquisition will be None here
                self.logger.info("Failed to acquire acquisition. " + str(detail_msg))
        except Exception as e:
            acquisition = None  # Checked later to call the callback
            self.logger.error('Error while processing datalogging acquisition: %s' % str(e))
            self.logger.debug(traceback.format_exc())

        # Inform the API about the acquisition being processed.
        err: Optional[Exception] = None
        try:
            if acquisition is None:
                if self.device_handler.get_connection_status() != DeviceHandler.ConnectionStatus.CONNECTED_READY:
                    detail_msg = "Device disconnected"  # Override of error message for user convenience
                self.active_request.callback(False, detail_msg, None)   # Inform the API of the failure
                self.logger.debug("Informing API of failure to get the datalogging acquisition")
            else:
                self.active_request.callback(True, detail_msg, acquisition)
                self.logger.debug("Informing API of success in getting the datalogging acquisition")
        except Exception as e:
            err = e

        self.active_request = None
        if err:
            raise err

    def read_active_request_data_from_raw_data(self, signal: api_datalogging.SignalDefinition, data: List[List[bytes]]) -> List[float]:
        """Converts a List of binary blocks into a list of numeric values (64 bits float) using the datastore definitions generated by the debug symbols."""
        assert self.active_request is not None
        loggable_id = self.active_request.entry_signal_map[signal.entry]
        signal_data = data[loggable_id]
        parsed_signal_data = []
        for data_chunk in signal_data:
            parsed_signal_data.append(float(signal.entry.decode(data_chunk)))

        return parsed_signal_data

    def process(self) -> None:
        """Function th ebe called periodically"""
        device_status = self.device_handler.get_connection_status()

        state_entry = (self.state != self.previous_state)
        next_state = self.state

        # =========== INIT =========
        if self.state == FsmState.INIT:
            self.active_request = None
            next_state = FsmState.WAIT_DEVICE_CONNECTED

        # =========== WAIT_DEVICE_CONNECTED =========
        elif self.state == FsmState.WAIT_DEVICE_CONNECTED:
            if device_status == DeviceHandler.ConnectionStatus.CONNECTED_READY:
                device_info = self.device_handler.get_device_info()
                assert device_info is not None
                assert device_info.supported_feature_map is not None
                if device_info.supported_feature_map['datalogging'] == True:
                    next_state = FsmState.WAIT_DATALOGGING_READY
                else:
                    next_state = FsmState.DEVICE_CONNECTED_NO_DATALOGGING

        # =========== WAIT_DATALOGGING_READY =========
        elif self.state == FsmState.WAIT_DATALOGGING_READY:
            if self.device_handler.datalogging_in_error():
                next_state = FsmState.CLEAR_ERROR
            elif device_status != DeviceHandler.ConnectionStatus.CONNECTED_READY:
                next_state = FsmState.SHUTDOWN_WAIT_REQ_PROCESSED
            elif self.device_handler.is_ready_for_datalogging_acquisition_request():
                next_state = FsmState.DEVICE_CONNECTED_WITH_DATALOGGING

        # =========== DEVICE_CONNECTED_WITH_DATALOGGING =========
        elif self.state == FsmState.DEVICE_CONNECTED_WITH_DATALOGGING:
            if self.device_handler.datalogging_in_error():
                next_state = FsmState.CLEAR_ERROR
            elif device_status != DeviceHandler.ConnectionStatus.CONNECTED_READY:
                next_state = FsmState.SHUTDOWN_WAIT_REQ_PROCESSED
            elif self.active_request is not None and not self.device_handler.datalogging_request_in_progress():
                next_state = FsmState.SHUTDOWN_WAIT_REQ_PROCESSED
                # Request will be nacked in SHUTDOWN_WAIT_REQ_PROCESSED state
            else:
                if not self.acquisition_request_queue.empty():  # A request to be processed pending in the queue
                    if self.active_request is None:  # No request being processed
                        if self.device_handler.is_ready_for_datalogging_acquisition_request():
                            self.active_request = self.acquisition_request_queue.get()
                            # We rely on the device handler to call our callback regardless
                            # of what will happen. Success, failure, error, external reset.
                            self.device_handler.request_datalogging_acquisition(
                                loop_id=self.active_request.api_request.rate_identifier,
                                config=self.active_request.device_config,
                                callback=DeviceAcquisitionRequestCompletionCallback(self.acquisition_complete_callback)
                            )
                        else:
                            # Cause of not ready:
                            # - not started : Device status will not be CONNECTED_READY, will exit cleanly
                            # - setup not completed : not possible as we waited on this before going here
                            # - error : Condition for that, will go to CLEAR_ERROR
                            # - cancel_requested : We wait until cancel is completed and active_request is set to None by the callback
                            # - stop_requested : Only happens if the device is not CONNECTED_READY. Will cleanly exit
                            pass
                    else:
                        if not self.device_handler.datalogging_cancel_in_progress():
                            self.logger.debug("Interrupting previous request with new one.")
                            self.device_handler.cancel_datalogging_acquisition()

        # =========== DEVICE_CONNECTED_NO_DATALOGGING =========
        elif self.state == FsmState.DEVICE_CONNECTED_NO_DATALOGGING:
            if self.device_handler.datalogging_in_error():
                next_state = FsmState.CLEAR_ERROR
            elif device_status != DeviceHandler.ConnectionStatus.CONNECTED_READY:
                next_state = FsmState.SHUTDOWN_WAIT_REQ_PROCESSED

        # =========== CLEAR_ERROR =========
        elif self.state == FsmState.CLEAR_ERROR:
            self.logger.error("Resetting device handler datalogging module")
            self.device_handler.reset_datalogging()
            next_state = FsmState.SHUTDOWN_WAIT_REQ_PROCESSED

        # =========== SHUTDOWN_WAIT_REQ_PROCESSED =========
        elif self.state == FsmState.SHUTDOWN_WAIT_REQ_PROCESSED:
            if self.device_handler.datalogging_in_error():
                next_state = FsmState.CLEAR_ERROR
            elif self.active_request is None:
                next_state = FsmState.SHUTDOWN_CLEAR_PENDING_REQUEST
            elif not self.device_handler.datalogging_request_in_progress():
                self.logger.error("Datalogging request pending, but the device handler is not processing it.")
                self.active_request.callback(False, "Datalogger is being reset", None)
                next_state = FsmState.SHUTDOWN_CLEAR_PENDING_REQUEST
            else:
                if not self.device_handler.datalogging_cancel_in_progress():
                    self.device_handler.cancel_datalogging_acquisition()    # Should trigger the callback and set active_Request to None

        # =========== SHUTDOWN_CLEAR_PENDING_REQUEST =========
        elif self.state == FsmState.SHUTDOWN_CLEAR_PENDING_REQUEST:
            while not self.acquisition_request_queue.empty():
                req = self.acquisition_request_queue.get()
                req.callback(False, "Device is not available", None)   # Not executed
            next_state = FsmState.INIT
        else:
            self.logger.error("Unknown FSM state %s" % self.state)
            next_state = FsmState.INIT

        if next_state != self.state:
            self.logger.debug("Moving FSM from %s to %s" % (self.state.name, next_state.name))

        self.previous_state = self.state
        self.state = next_state

    @classmethod
    def api_trigger_condition_to_device_trigger_condition(cls, api_cond: api_datalogging.TriggerCondition) -> device_datalogging.TriggerCondition:
        """Converts a TriggerCondition in the API format to the device format"""
        device_operands: List[device_datalogging.Operand] = []
        for api_operand in api_cond.operands:
            if api_operand.type == api_datalogging.TriggerConditionOperandType.LITERAL:
                if not isinstance(api_operand.value, (int, float)):
                    raise ValueError("Literal operands must be int or float")
                device_operands.append(device_datalogging.LiteralOperand(api_operand.value))
            elif api_operand.type == api_datalogging.TriggerConditionOperandType.WATCHABLE:
                if not isinstance(api_operand.value, DatastoreEntry):
                    raise ValueError("Watchable operand must have a datastore entry as value")

                device_operands.append(cls.make_device_operand_from_watchable(api_operand.value))
            else:
                raise ValueError("Unsupported operand type %s" % str(api_operand.type))

        device_cond = device_datalogging.TriggerCondition(api_cond.condition_id, *device_operands)

        return device_cond

    @classmethod
    def make_device_config_from_request(self, 
                                        request: api_datalogging.AcquisitionRequest
                                        ) -> Tuple[device_datalogging.Configuration, Dict[DatastoreEntry, int]]:
        """Converts a Configuration from the API format to the device format"""
        config = device_datalogging.Configuration()
        # Each of the assignation below can trigger an exception if out of bound
        config.decimation = request.decimation
        config.timeout = request.timeout
        config.probe_location = request.probe_location
        config.trigger_hold_time = request.trigger_hold_time
        config.trigger_condition = self.api_trigger_condition_to_device_trigger_condition(request.trigger_condition)

        entry2signal_map: Dict[DatastoreEntry, int] = {}

        # Generate a list of LoggableSignal for that the device handler can manage (converts datastore entries into address/size and RPVs).
        all_signals: List[api_datalogging.SignalDefinition] = cast(List[api_datalogging.SignalDefinition], request.signals.copy())

        if request.x_axis_type == api_datalogging.XAxisType.Signal:
            if not isinstance(request.x_axis_signal, api_datalogging.SignalDefinition):
                raise ValueError("X Axis must have a signal definition")
            all_signals.append(request.x_axis_signal)

        for signal in all_signals:
            entry_to_log: DatastoreEntry
            if isinstance(signal.entry, DatastoreAliasEntry):
                entry_to_log = signal.entry.refentry
            else:
                entry_to_log = signal.entry

            if entry_to_log not in entry2signal_map:
                config.add_signal(self.make_signal_from_watchable(entry_to_log))
                signal_index = len(config.get_signals()) - 1
            else:
                signal_index = entry2signal_map[entry_to_log]
            entry2signal_map[entry_to_log] = signal_index   # Remember what signal comes from what datastore entry
            entry2signal_map[signal.entry] = signal_index   # Remember what signal comes from what datastore entry

        # Purposely add time at the end. It wi
        if request.x_axis_type == api_datalogging.XAxisType.MeasuredTime:
            config.add_signal(device_datalogging.TimeLoggableSignal())

        return (config, entry2signal_map)

    @classmethod
    def make_signal_from_watchable(cls, watchable: DatastoreEntry) -> device_datalogging.LoggableSignal:
        """Makes the definitions of a loggable signal from a datastore watchable entry"""
        if isinstance(watchable, DatastoreAliasEntry):
            watchable = watchable.refentry

        signal: device_datalogging.LoggableSignal
        if isinstance(watchable, DatastoreVariableEntry):
            if watchable.is_bitfield():
                bitoffset = watchable.get_bitoffset()
                bitsize = watchable.get_bitsize()
                assert bitoffset is not None
                assert bitsize is not None

                size = math.ceil(bitsize / 8)
                if watchable.variable_def.endianness == Endianness.Little:
                    address = watchable.get_address() + bitoffset // 8
                else:
                    address = (watchable.get_address() + watchable.get_data_type().get_size_byte()) - bitoffset // 8

                signal = device_datalogging.MemoryLoggableSignal(address, size)
            else:
                signal = device_datalogging.MemoryLoggableSignal(watchable.get_address(), watchable.get_size())
        elif isinstance(watchable, DatastoreRPVEntry):
            signal = device_datalogging.RPVLoggableSignal(watchable.get_rpv().id)
        else:
            raise ValueError('Cannot make a loggable signal out of this watchable %s' % (watchable.display_path))
        return signal

    @classmethod
    def make_device_operand_from_watchable(cls, watchable: DatastoreEntry) -> device_datalogging.Operand:
        """Makes a datalogging trigger condition operand from a datastore watchable entry"""

        if isinstance(watchable, DatastoreAliasEntry):
            watchable = watchable.refentry

        operand: device_datalogging.Operand
        if isinstance(watchable, DatastoreVariableEntry):
            if watchable.is_bitfield():
                bitoffset = watchable.get_bitoffset()
                bitsize = watchable.get_bitsize()
                assert bitoffset is not None
                assert bitsize is not None

                operand = device_datalogging.VarBitOperand(
                    watchable.get_address(),
                    watchable.get_data_type(),
                    bitoffset,
                    bitsize)
            else:
                operand = device_datalogging.VarOperand(watchable.get_address(), watchable.get_data_type())
        elif isinstance(watchable, DatastoreRPVEntry):
            operand = device_datalogging.RPVOperand(watchable.get_rpv().id)
        else:
            raise ValueError('Cannot make a Operand out of this watchable %s' % (watchable.display_path))

        return operand

    def get_device_setup(self) -> Optional[device_datalogging.DataloggingSetup]:
        """Reads the datalogging configuration gotten from the device. May not be available"""
        return self.device_handler.get_datalogging_setup()

    def get_sampling_rate(self, identifier: int) -> api_datalogging.SamplingRate:
        """Get the sampling rate identified by the given identifier. The identifier is known to the device."""
        sampling_rates = self.get_available_sampling_rates()
        candidate: Optional[api_datalogging.SamplingRate] = None
        for sr in sampling_rates:
            if sr.device_identifier == identifier:
                candidate = sr
                break
        if candidate is None:
            raise ValueError("Cannot find requested sampling rate")
        return candidate

    def get_available_sampling_rates(self) -> List[api_datalogging.SamplingRate]:
        """Get all sampling rates available on the actually connected device """
        output: List[api_datalogging.SamplingRate] = []
        device_status = self.device_handler.get_connection_status()
        if device_status == DeviceHandler.ConnectionStatus.CONNECTED_READY:
            device_info = self.device_handler.get_device_info()
            if device_info is not None:
                if device_info.loops is not None:
                    for i in range(len(device_info.loops)):
                        loop = device_info.loops[i]
                        frequency: Optional[float] = None
                        if isinstance(loop, FixedFreqLoop):
                            frequency = loop.get_frequency()
                        if loop.support_datalogging:
                            rate = api_datalogging.SamplingRate(
                                name=loop.get_name(),
                                rate_type=loop.get_loop_type(),
                                device_identifier=i,
                                frequency=frequency
                            )

                            output.append(rate)
        return output
