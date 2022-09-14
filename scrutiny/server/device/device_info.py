#    device_info.py
#        All the information that can be extracted from the device through the Scrutiny protocol
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

from typing import TypedDict, List, Optional
from scrutiny.core.basic_types import *


class MemoryRegion(TypedDict):
    start: int
    end: int


class SupportedFeatureMap(TypedDict):
    memory_write: bool
    datalog_acquire: bool
    user_command: bool


class DeviceInfo:
    __slots__ = (
        'device_id',
        'display_name',
        'max_tx_data_size',
        'max_rx_data_size',
        'max_bitrate_bps',
        'rx_timeout_us',
        'heartbeat_timeout_us',
        'address_size_bits',
        'protocol_major',
        'protocol_minor',
        'supported_feature_map',
        'forbidden_memory_regions',
        'readonly_memory_regions',
        'runtime_published_values'
    )

    device_id: Optional[str]
    display_name: Optional[str]
    max_tx_data_size: Optional[int]
    max_rx_data_size: Optional[int]
    max_bitrate_bps: Optional[int]
    rx_timeout_us: Optional[int]
    heartbeat_timeout_us: Optional[int]
    address_size_bits: Optional[int]
    protocol_major: Optional[int]
    protocol_minor: Optional[int]
    supported_feature_map: Optional[SupportedFeatureMap]
    forbidden_memory_regions: Optional[List[MemoryRegion]]
    readonly_memory_regions: Optional[List[MemoryRegion]]
    runtime_published_values: Optional[List[RuntimePublishedValue]]

    def get_attributes(self):
        return self.__slots__

    def __init__(self):
        self.clear()

    def all_ready(self) -> bool:
        ready = True
        for attr in self.__slots__:
            if getattr(self, attr) is None:
                ready = False
                break
        return ready

    def clear(self) -> None:
        for attr in self.__slots__:
            setattr(self, attr, None)

    def __str__(self):
        dict_out = {}
        for attr in self.__slots__:
            dict_out[attr] = getattr(self, attr)
        return str(dict_out)
