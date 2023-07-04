__all__ = [
    'ServerState',
    'DeviceState',
    'WatchableType'
]

import enum


class ServerState(enum.Enum):
    Disconnected = 0
    Connecting = 1
    Connected = 2
    Error = -1


class DeviceState(enum.Enum):
    Disconnected = 0
    Connecting = 1
    Connected = 2


class WatchableType(enum.Enum):
    NA = 0
    Variable = 1
    RuntimePulishedValue = 2
    Alias = 3
