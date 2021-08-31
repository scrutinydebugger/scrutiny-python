class Heartbeat(Command):
    _cmd_id = 4

    class Subfunction(Enum):
        Ping = 1
        Pong = 2