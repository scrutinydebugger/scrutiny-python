import struct

from . import commands as cmd
from . import Request, Response
from .exceptions import *
from .datalog_conf import DatalogConfiguration
import logging

class Protocol:
    def __init__(self, version_major=1, version_minor=0):
        self.version_major = version_major
        self.version_minor = version_minor
        self.logger = logging.getLogger('protocol')

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
            data += struct.pack('>LH', watch.address, watch.length)

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

    def parse_request(self, req):
        data = {'valid' : True}
        try:
            if req.command == cmd.MemoryControl:
                subfn = cmd.MemoryControl.Subfunction(req.subfn)
                
                if subfn == cmd.MemoryControl.Subfunction.Read:                     # MemoryControl - Read
                    (data['address'], data['length']) = struct.unpack('>LH', req.payload[0:6])
                
                elif subfn == cmd.MemoryControl.Subfunction.Write:                  # MemoryControl - Write
                    (data['address'],) = struct.unpack('>L', req.payload[0:4])
                    data['data'] = req.payload[4:]

            if req.command == cmd.DatalogControl:
                subfn = cmd.DatalogControl.Subfunction(req.subfn)
                
                if subfn == cmd.DatalogControl.Subfunction.ReadRecordings:          # DatalogControl - ReadRecordings
                    (data['record_id'],) = struct.unpack('>H', req.payload[0:2])
                
                elif subfn == cmd.DatalogControl.Subfunction.ConfigureDatalog:      # DatalogControl - ConfigureDatalog
                    conf = DatalogConfiguration()
                    (conf.destination, conf.sample_rate, conf.decimation, num_watches) = struct.unpack('>BfBH', req.payload[0:8])

                    for i in range(num_watches):
                        pos = 8+i*6
                        (addr, length) = struct.unpack('>LH', req.payload[pos:pos+6])
                        conf.add_watch(addr, length)
                    pos = 8+num_watches*6
                    condition_num, = struct.unpack('>B', req.payload[pos:pos+1])
                    conf.trigger.condition = DatalogConfiguration.TriggerCondition(condition_num)
                    pos +=1
                    operands = []
                    for i in range(2):
                        operand_type_num, = struct.unpack('B', req.payload[pos:pos+1])
                        pos +=1
                        operand_type = DatalogConfiguration.Operand.Type(operand_type_num)
                        if operand_type == DatalogConfiguration.Operand.Type.CONST:
                            val, = struct.unpack('>f', req.payload[pos:pos+4])
                            operands.append(DatalogConfiguration.ConstOperand(val))
                            pos +=4
                        elif operand_type == DatalogConfiguration.Operand.Type.WATCH:
                            (address, length, interpret_as) = struct.unpack('>LBB', req.payload[pos:pos+6])
                            operands.append(DatalogConfiguration.WatchOperand(address=address, length=length, interpret_as=interpret_as))
                            pos +=6
                    conf.trigger.operand1 = operands[0]
                    conf.trigger.operand2 = operands[1]
                    data['configuration'] = conf


        except Exception as e:
            self.logger.error(str(e))
            data['valid'] = False

        if not data['valid']:
            raise InvalidRequestException(req, 'Could not properly decode request payload.')

        return data
