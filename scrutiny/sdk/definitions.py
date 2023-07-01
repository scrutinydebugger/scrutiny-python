import enum


class ServerState(enum.Enum):
    Disconnected = enum.auto()
    Connecting = enum.auto()
    Connected = enum.auto()
    Error = enum.auto()


class DeviceState(enum.Enum):
    Disconnected = enum.auto()
    Connecting = enum.auto()
    Connected = enum.auto()

