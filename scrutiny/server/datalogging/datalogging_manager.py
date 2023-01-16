import queue
from enum import Enum
from uuid import uuid4
from dataclasses import dataclass
import logging

import scrutiny.server.datalogging.definitions as datalogging
from scrutiny.server.device.device_handler import DeviceHandler
from scrutiny.server.datastore.datastore_entry import DatastoreEntry
from scrutiny.server.datastore.datastore import Datastore
from scrutiny.server.device.device_info import ExecLoopType, FixedFreqLoop
from scrutiny.server.datalogging.acquisition import deinterleave_acquisition_data
from scrutiny.server.datalogging.acquisition import DataloggingAcquisition
from scrutiny.core.basic_types import *

from typing import Optional, List, Dict


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


class AcquisitionRequest:
    rate_identifier: int
    config: datalogging.Configuration
    x_axis: XAxisType
    x_axis_watchable: Optional[DatastoreEntry]
    entries: List[DatastoreEntry]


class DataloggingDeviceSetup:
    buffer_size: int
    encoding: datalogging.Encoding


class DataloggingManager:
    datastore: Datastore
    device_handler: DeviceHandler
    acquisition_request_queue: queue.Queue
    last_device_status: DeviceHandler.ConnectionStatus
    device_status: DeviceHandler.ConnectionStatus
    active_request: Optional[AcquisitionRequest]
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

    def set_disconnected(self):
        self.active_request = None
        self.datalogging_setup = None
        self.rpv_map = None

    def request_acquisition(self, request: AcquisitionRequest) -> None:
        self.acquisition_request_queue.put(request)

    def process(self) -> None:
        self.device_status = self.device_handler.get_connection_status()

        if self.device_status == DeviceHandler.ConnectionStatus.CONNECTED_READY:
            device_info = self.device_handler.get_device_info()
            assert device_info is not None
            assert device_info.supported_feature_map is not None
            assert device_info.runtime_published_values is not None
            if device_info.supported_feature_map['datalogging'] == True:
                if self.last_device_status != DeviceHandler.ConnectionStatus.CONNECTED_READY:   # Just connected
                    pass
                    # request setup
                    # fill self.datalogging_setup

                    self.rpv_map = {}
                    for rpv in device_info.runtime_published_values:
                        self.rpv_map[rpv.id] = rpv

                else:
                    pass
        else:
            self.set_disconnected()

        self.last_device_status = self.device_status

    def receive_acquisition_raw_data(self, raw_data: bytes):
        if self.device_status != DeviceHandler.ConnectionStatus.CONNECTED_READY:
            self.logger.warning("Received acquisition data but device is disconnected")
            return

        if self.active_request is None:
            self.logger.error("Received acquisition data but was not expecting it")
            return

        if self.datalogging_setup is None:
            self.logger.error("Received acquisition data but datalogging format unknown at this point")
            return

        if self.rpv_map is None:
            self.logger.error("Internal Error - RPV map not built")
            return

        deinterleaved_data = deinterleave_acquisition_data(
            data=raw_data,
            config=self.active_request.config,
            rpv_map=self.rpv_map,
            encoding=self.datalogging_setup.encoding
        )

    def get_available_smapling_freq(self) -> Optional[List[DataloggingSamplingRate]]:
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
