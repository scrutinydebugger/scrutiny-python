import struct

from . import commands as cmd
from . import Request, Response


class Protocol:
    def __init__(self, version_major=1, version_minor=0):
        self.version_major = version_major
        self.version_minor = version_minor

    def get_protocol_version(self):
        return Request(cmd.GetInfo, cmd.GetInfo.Subfunction.GetProtocolVersion)

    def get_software_id(self):
        return Request(cmd.GetInfo, cmd.GetInfo.Subfunction.GetSoftwareId)

    def get_supported_features(self):
        return Request(cmd.GetInfo, cmd.GetInfo.Subfunction.GetSupportedFeatures)

    def read_memory_block(self, address, length):
        data = struct.pack('>LH', address, length)
        return Request(cmd.MemoryControl, cmd.MemoryControl.Subfunction.Read, data)

    def write_memory_block(self, address, data):
        data = struct.pack('>L', address) + bytes(data)
        return Request(cmd.MemoryControl, cmd.MemoryControl.Subfunction.Write, data)
