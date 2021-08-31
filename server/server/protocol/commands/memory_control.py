
class MemoryControl(Command):
    _cmd_id = 3

    class Subfunction(Enum):
        Read = 1
        Write = 2
