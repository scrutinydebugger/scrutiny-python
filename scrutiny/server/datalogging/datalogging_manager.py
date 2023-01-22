#    datalogging_manager.py
#        The main server components that manages the datalogging feature at high level
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

import queue
from enum import Enum
from uuid import uuid4
from dataclasses import dataclass
import logging

import scrutiny.server.datalogging.definitions as datalogging
from scrutiny.server.device.device_handler import DeviceHandler, DataloggingReceiveSetupCallback
from scrutiny.server.datastore.datastore_entry import DatastoreEntry, DatastoreAliasEntry, DatastoreRPVEntry, DatastoreVariableEntry
from scrutiny.server.datastore.datastore import Datastore
from scrutiny.server.device.device_info import ExecLoopType, FixedFreqLoop
from scrutiny.server.datalogging.acquisition import deinterleave_acquisition_data, DataloggingAcquisition
from scrutiny.core.basic_types import *
from scrutiny.server.datalogging.datalogging_storage import DataloggingStorage
from scrutiny.core.typehints import GenericCallback

from typing import Optional, List, Dict, Callable, Tuple


class XAxisType(Enum):
    IdealTime = 0,
    MeasuredTime = 1,
    Signal = 2


@dataclass
class DataloggingSamplingRate:
    name: str
    frequency: Optional[float]
    rate_type: ExecLoopType
    device_identifier: int


class AcquisitionRequestCompletedCallback(GenericCallback):
    callback: Callable[[bool, Optional[DataloggingAcquisition]], None]


class AcquisitionRequest:
    rate_identifier: int
    decimation: int
    timeout: float
    probe_location: float
    trigger_hold_time: float
    trigger_condition: datalogging.TriggerCondition
    x_axis: XAxisType
    x_axis_watchable: Optional[DatastoreEntry]
    entries: List[DatastoreEntry]
    completion_callback: AcquisitionRequestCompletedCallback


@dataclass
class DataloggingDeviceSetup:
    buffer_size: int
    encoding: datalogging.Encoding


class DataloggingManager:
    datastore: Datastore
    device_handler: DeviceHandler
    acquisition_request_queue: "queue.Queue[Tuple[AcquisitionRequest, datalogging.Configuration]]"
    last_device_status: DeviceHandler.ConnectionStatus
    device_status: DeviceHandler.ConnectionStatus
    active_request: Optional[AcquisitionRequest]
    active_request_config: datalogging.Configuration
    logger: logging.Logger
    datalogging_setup: Optional[DataloggingDeviceSetup]
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
        config = self.make_device_config_from_request(request)  # Can raise an exception
        self.acquisition_request_queue.put((request, config))

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

    def callback_receive_setup(self, buffer_size: int, encoding: datalogging.Encoding):
        self.datalogging_setup = DataloggingDeviceSetup(
            buffer_size=buffer_size,
            encoding=encoding
        )

    def make_device_config_from_request(self, request: AcquisitionRequest) -> datalogging.Configuration:
        config = datalogging.Configuration()
        # Each of the assignation below can trigger an exception if out of bound
        config.decimation = request.decimation
        config.timeout = request.timeout
        config.probe_location = request.probe_location
        config.trigger_hold_time = request.trigger_hold_time
        config.trigger_condition = request.trigger_condition

        if request.x_axis == XAxisType.MeasuredTime:
            config.add_signal(datalogging.TimeLoggableSignal())
        elif request.x_axis == XAxisType.Signal:
            if request.x_axis_watchable is None:
                raise ValueError("X Axis must have a watchable")

            config.add_signal(self.make_signal_from_watchable(request.x_axis_watchable))

        for entry in request.entries:
            config.add_signal(self.make_signal_from_watchable(entry))

        return config

    def make_signal_from_watchable(self, watchable: DatastoreEntry) -> datalogging.LoggableSignal:
        if isinstance(watchable, DatastoreAliasEntry):
            watchable = watchable.refentry

        signal: datalogging.LoggableSignal
        if isinstance(watchable, DatastoreVariableEntry):
            signal = datalogging.MemoryLoggableSignal(watchable.get_address(), watchable.get_size())
        elif isinstance(watchable, DatastoreRPVEntry):
            signal = datalogging.RPVLoggableSignal(watchable.get_rpv().id)
        else:
            raise ValueError('Cannot make a loggable signal out of this watchable %s' % (watchable.display_path))
        return signal

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

    def get_available_sampling_freq(self) -> Optional[List[DataloggingSamplingRate]]:
        output: List[DataloggingSamplingRate] = []

        if self.device_status == DeviceHandler.ConnectionStatus.CONNECTED_READY:
            device_info = self.device_handler.get_device_info()
            if device_info is not None:
                if device_info.loops is not None:
                    for i in range(len(device_info.loops)):
                        loop = device_info.loops[i]
                        if loop.support_datalogging:
                            rate = DataloggingSamplingRate(
                                name=loop.get_name(),
                                rate_type=loop.get_loop_type(),
                                device_identifier=i,
                                frequency=None
                            )
                            if isinstance(loop, FixedFreqLoop):
                                rate.frequency = loop.get_frequency()
                            output.append(rate)
        return output