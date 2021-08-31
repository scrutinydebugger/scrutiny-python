
class GetInfo(Command):
    _cmd_id = 1

    class Subfunction(Enum):
        GetProtocolVersion = 1
        GetSoftwareId = 2
        GetSupportedFeatures = 3


def make_request()