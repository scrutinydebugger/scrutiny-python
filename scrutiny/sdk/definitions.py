__all__ = [
    'ServerState',
    'DeviceState',
    'WatchableType',
    'ValueStatus',
    'DeviceLinkState'
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


class ValueStatus(enum.Enum):
    Valid = 1
    NeverSet = 2
    ServerGone = 3


class DeviceLinkState(enum.Enum):
    NA = 0
    Disconnected = 1
    Connecting = 2
    ConnectedReady = 3
