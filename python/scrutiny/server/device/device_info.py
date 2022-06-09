#    device_info.py
#        All the information that can be extracted from the device through the Scrutiny protocol
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

from typing import Dict, List


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
        'readonly_memory_regions'
    )

    device_id: str
    display_name: str
    max_tx_data_size: int
    max_rx_data_size: int
    max_bitrate_bps: int
    rx_timeout_us: int
    heartbeat_timeout_us: int
    address_size_bits: int
    protocol_major: int
    protocol_minor: int
    supported_feature_map: Dict[str, bool]
    forbidden_memory_regions: List[Dict[str, int]]
    readonly_memory_regions: List[Dict[str, int]]

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
