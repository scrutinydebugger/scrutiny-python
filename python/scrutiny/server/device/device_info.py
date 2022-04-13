class DeviceInfo:
    __slots__ = (
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

    def __init__(self):
        self.clear()

    def all_ready(self):
        ready = True
        for attr in self.__slots__:
            if getattr(self, attr) is None:
                ready = False
                break
        return ready

    def clear(self):
        for attr in self.__slots__:
            setattr(self, attr, None)

    def __str__(self):
        dict_out  = {}
        for attr in self.__slots__:
            dict_out[attr] = getattr(self, attr)
        return str(dict_out)
