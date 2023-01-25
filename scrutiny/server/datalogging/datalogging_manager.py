#    datalogging_manager.py
#        The main server components that manages the datalogging feature at high level
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

import queue
from dataclasses import dataclass
import logging
import math

import scrutiny.server.datalogging.definitions as datalogging
from scrutiny.server.device.device_handler import DeviceHandler, DataloggingReceiveSetupCallback
from scrutiny.server.datastore.datastore_entry import DatastoreEntry, DatastoreAliasEntry, DatastoreRPVEntry, DatastoreVariableEntry
from scrutiny.server.datastore.datastore import Datastore
from scrutiny.server.device.device_info import FixedFreqLoop
from scrutiny.server.datalogging.acquisition import deinterleave_acquisition_data, DataloggingAcquisition
from scrutiny.core.basic_types import *
from scrutiny.server.datalogging.datalogging_storage import DataloggingStorage
from scrutiny.core.typehints import GenericCallback

from typing import Optional, List, Dict, Callable, Tuple


class AcquisitionRequestCompletedCallback(GenericCallback):
    callback: Callable[[bool, Optional[DataloggingAcquisition]], None]


@dataclass
class AcquisitionRequest:
    rate_identifier: int
    decimation: int
    timeout: float
    probe_location: float
    trigger_hold_time: float
    trigger_condition: datalogging.TriggerCondition
    x_axis_type: datalogging.XAxisType
    x_axis_watchable: Optional[DatastoreEntry]
    entries: List[DatastoreEntry]
    completion_callback: AcquisitionRequestCompletedCallback


class DataloggingManager:
    datastore: Datastore
    device_handler: DeviceHandler
    acquisition_request_queue: "queue.Queue[Tuple[AcquisitionRequest, datalogging.Configuration]]"
    last_device_status: DeviceHandler.ConnectionStatus
    device_status: DeviceHandler.ConnectionStatus
    active_request: Optional[AcquisitionRequest]
    active_request_config: datalogging.Configuration
    logger: logging.Logger
    datalogging_setup: Optional[datalogging.DataloggingSetup]
    rpv_map: Optional[Dict[int, RuntimePublishedValue]]

    def __init__(self, datastore: Datastore, device_handler: DeviceHandler):
        self.datastore = datastore
        self.device_handler = device_handler
        self.logger = logging.getLogger(self.__class__.__name__)
        self.acquisition_request_queue = queue.Queue()
        self.last_device_status = DeviceHandler.ConnectionStatus.UNKNOWN
        self.device_status = DeviceHandler.ConnectionStatus.UNKNOWN
        self.active_request = None
        self.datalogging_setup = None
        self.rpv_map = None

        self.device_handler.set_datalogging_callbacks(
            receive_setup=DataloggingReceiveSetupCallback(self.callback_receive_setup),
        )

    def set_disconnected(self):
        self.active_request = None
        self.datalogging_setup = None
        self.rpv_map = None

    def request_acquisition(self, request: AcquisitionRequest) -> None:
        config, signalmap = self.make_device_config_from_request(request)  # Can raise an exception
        self.acquisition_request_queue.put((request, config))
        # todo keep the signalmap for later

    def process(self) -> None:
        self.device_status = self.device_handler.get_connection_status()

        if self.device_status == DeviceHandler.ConnectionStatus.CONNECTED_READY:
            device_info = self.device_handler.get_device_info()
            assert device_info is not None
            assert device_info.supported_feature_map is not None
            assert device_info.runtime_published_values is not None
            if device_info.supported_feature_map['datalogging'] == True:
                if self.last_device_status != DeviceHandler.ConnectionStatus.CONNECTED_READY:   # Just connected
                    self.rpv_map = {}
                    for rpv in device_info.runtime_published_values:
                        self.rpv_map[rpv.id] = rpv
                else:
                    self.process_connected_ready()
        else:
            self.set_disconnected()

        self.last_device_status = self.device_status

    def process_connected_ready(self):
        if self.active_request is None:
            if not self.acquisition_request_queue.empty():
                self.active_request, self.active_request_config = self.acquisition_request_queue.get()
                self.device_handler.request_datalogging_acquisition(
                    loop_id=self.active_request.rate_identifier,
                    config=self.active_request_config,
                )

    def callback_receive_setup(self, setup: datalogging.DataloggingSetup):
        self.datalogging_setup = setup

    @classmethod
    def make_device_config_from_request(self, request: AcquisitionRequest) -> Tuple[datalogging.Configuration, Dict[DatastoreEntry, int]]:
        config = datalogging.Configuration()
        # Each of the assignation below can trigger an exception if out of bound
        config.decimation = request.decimation
        config.timeout = request.timeout
        config.probe_location = request.probe_location
        config.trigger_hold_time = request.trigger_hold_time
        config.trigger_condition = request.trigger_condition

        entry2signal_map: Dict[DatastoreEntry, int] = {}

        all_entries = request.entries.copy()

        if request.x_axis_type == datalogging.XAxisType.Signal:
            if not isinstance(request.x_axis_watchable, DatastoreEntry):
                raise ValueError("X Axis must have a watchable entry")
            all_entries.append(request.x_axis_watchable)

        signal_count = 0
        for entry in all_entries:
            if isinstance(entry, DatastoreAliasEntry):
                entry_to_log = entry.refentry
            else:
                entry_to_log = entry

            if entry_to_log not in entry2signal_map:
                config.add_signal(self.make_signal_from_watchable(entry_to_log))
                signal_index = signal_count
                signal_count += 1
            else:
                signal_index = entry2signal_map[entry_to_log]
            entry2signal_map[entry_to_log] = signal_index
            entry2signal_map[entry] = signal_index

        # Purposely add time at the end
        if request.x_axis_type == datalogging.XAxisType.MeasuredTime:
            config.add_signal(datalogging.TimeLoggableSignal())

        return (config, entry2signal_map)

    @classmethod
    def make_signal_from_watchable(cls, watchable: DatastoreEntry) -> datalogging.LoggableSignal:
        if isinstance(watchable, DatastoreAliasEntry):
            watchable = watchable.refentry

        signal: datalogging.LoggableSignal
        if isinstance(watchable, DatastoreVariableEntry):
            if watchable.is_bitfield():
                bitoffset = watchable.get_bitoffset()
                bitsize = watchable.get_bitsize()
                assert bitoffset is not None
                assert bitsize is not None

                if watchable.variable_def.endianness == Endianness.Little:
                    address = watchable.get_address() + bitoffset // 8
                    size = math.ceil(bitsize / 8)
                else:
                    address = (watchable.get_address() + watchable.get_data_type().get_size_byte()) - bitoffset // 8
                    size = math.ceil(bitsize / 8)

                signal = datalogging.MemoryLoggableSignal(address, size)
            else:
                signal = datalogging.MemoryLoggableSignal(watchable.get_address(), watchable.get_size())
        elif isinstance(watchable, DatastoreRPVEntry):
            signal = datalogging.RPVLoggableSignal(watchable.get_rpv().id)
        else:
            raise ValueError('Cannot make a loggable signal out of this watchable %s' % (watchable.display_path))
        return signal

    @classmethod
    def make_operand_from_watchable(cls, watchable: DatastoreEntry) -> datalogging.Operand:
        if isinstance(watchable, DatastoreAliasEntry):
            watchable = watchable.refentry

        operand: datalogging.Operand
        if isinstance(watchable, DatastoreVariableEntry):
            if watchable.is_bitfield():
                bitoffset = watchable.get_bitoffset()
                bitsize = watchable.get_bitsize()
                assert bitoffset is not None
                assert bitsize is not None

                operand = datalogging.VarBitOperand(
                    watchable.get_address(),
                    watchable.get_data_type(),
                    bitoffset,
                    bitsize)
            else:
                operand = datalogging.VarOperand(watchable.get_address(), watchable.get_data_type())
        elif isinstance(watchable, DatastoreRPVEntry):
            operand = datalogging.RPVOperand(watchable.get_rpv().id)
        else:
            raise ValueError('Cannot make a Operand out of this watchable %s' % (watchable.display_path))

        return operand

    def receive_acquisition_raw_data(self, request: AcquisitionRequest, raw_data: bytes):
        if self.device_status != DeviceHandler.ConnectionStatus.CONNECTED_READY:
            self.logger.warning("Received acquisition data but device is disconnected")
            return

        if self.active_request is None:
            self.logger.error("Received acquisition data but was not expecting it. No active acquisition request")
            return

        if self.active_request_config is None:
            self.logger.error("Received acquisition data but was not expecting it. No active config")
            return

        if self.datalogging_setup is None:
            self.logger.error("Received acquisition data but datalogging format unknown at this point")
            return

        if self.rpv_map is None:
            self.logger.error("Internal Error - RPV map not built")
            return

        deinterleaved_data = deinterleave_acquisition_data(
            data=raw_data,
            config=self.active_request_config,
            rpv_map=self.rpv_map,
            encoding=self.datalogging_setup.encoding
        )

    def get_available_sampling_freq(self) -> Optional[List[datalogging.SamplingRate]]:
        output: List[datalogging.SamplingRate] = []

        if self.device_status == DeviceHandler.ConnectionStatus.CONNECTED_READY:
            device_info = self.device_handler.get_device_info()
            if device_info is not None:
                if device_info.loops is not None:
                    for i in range(len(device_info.loops)):
                        loop = device_info.loops[i]
                        if loop.support_datalogging:
                            rate = datalogging.SamplingRate(
                                name=loop.get_name(),
                                rate_type=loop.get_loop_type(),
                                device_identifier=i,
                                frequency=None
                            )
                            if isinstance(loop, FixedFreqLoop):
                                rate.frequency = loop.get_frequency()
                            output.append(rate)
        return output
