import struct

from . import commands as cmd
from . import Request, Response
from .datalog_conf import DatalogConfiguration


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

    def ping(self):
        return Request(cmd.Heartbeat, cmd.Heartbeat.Subfunction.Ping)

    def pong(self):
        return Request(cmd.Heartbeat, cmd.Heartbeat.Subfunction.Pong)

    def datalog_get_targets(self):
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetAvailableTarget) 

    def datalog_get_bufsize(self):
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetBufferSize) 

    def datalog_get_sampling_rates(self):
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetSamplingRates) 

    def datalog_configure_log(self, conf):
        if not isinstance(conf, DatalogConfiguration):
            raise ValueError('Given configuration must be an instance of protocol.DatalogConfiguration')

        data = struct.pack('>BfBH', conf.destination, conf.sample_rate, conf.decimation, len(conf.watches))
        for watch in conf.watches:
            data += struct.pack('>LH', watch.addr, watch.length)

        data += struct.pack('B', conf.trigger.condition.value)

        for operand in [conf.trigger.operand1, conf.trigger.operand2]:
            if operand.type == DatalogConfiguration.Operand.Type.CONST:
                data += struct.pack('>Bf', operand.type.value, operand.value)
            elif operand.type == DatalogConfiguration.Operand.Type.WATCH:
                data += struct.pack('>BLBB', operand.type.value, operand.address, operand.length, operand.interpret_as.value)
            else:
                raise Exception('Unknown operand type %s' % operand.type)

        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ConfigureDatalog, data) 

    def datalog_get_list_recording(self):
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ListRecordings) 

    def datalog_read_recording(self, record_id):
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ReadRecordings, struct.pack('>H', record_id))

    def datalog_arm(self):
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ArmLog) 

    def datalog_disarm(self):
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.DisarmLog) 

    def datalog_status(self):
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetLogStatus) 
