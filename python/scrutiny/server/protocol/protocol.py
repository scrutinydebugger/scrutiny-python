import struct

from . import commands as cmd
from . import Request, Response
from .exceptions import *
from .datalog import *
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

    def datalog_get_list_recordings(self):
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ListRecordings) 

    def datalog_read_recording(self, record_id):
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ReadRecordings, struct.pack('>H', record_id))

    def datalog_arm(self):
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ArmLog) 

    def datalog_disarm(self):
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.DisarmLog) 

    def datalog_status(self):
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetLogStatus) 

    def user_command(self, subfn, data=b''):
        return Request(cmd.UserCommand, subfn, data) 

    def comm_discover(self, challenge):
        data = cmd.EstablishComm.MAGIC + struct.pack('>L', challenge)
        return Request(cmd.EstablishComm, cmd.EstablishComm.Subfunction.Discover, data) 

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

            elif req.command == cmd.DatalogControl:
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
           
            elif req.command == cmd.EstablishComm:
                subfn = cmd.EstablishComm.Subfunction(req.subfn)
            
                if subfn == cmd.EstablishComm.Subfunction.Discover:          # EstablishComm - Discover
                    data['magic'] = req.payload[0:4]
                    data['challenge'], = struct.unpack('>L', req.payload[4:8])


        except Exception as e:
            self.logger.error(str(e))
            data['valid'] = False

        if not data['valid']:
            raise InvalidRequestException(req, 'Could not properly decode request payload.')

        return data


# ======================== Response =================

    def respond_not_ok(self, req, code):
        return Response(req.Command, req.subfn, Response.ResponseCode(code))

    def respond_protocol_version(self, major=None, minor=None):
        if major is None:
            major = self.version_major

        if minor is None:
            minor = self.version_minor

        return Response(cmd.GetInfo, cmd.GetInfo.Subfunction.GetProtocolVersion, Response.ResponseCode.OK, bytes([major, minor]))

    def respond_software_id(self, software_id):
        return Response(cmd.GetInfo, cmd.GetInfo.Subfunction.GetSoftwareId, Response.ResponseCode.OK, bytes(software_id))

    def respond_supported_features(self, memory_read=False, memory_write=False, datalog_acquire=False, user_func=False):
        bytes1 = 0
        if memory_read:
            bytes1 |= 0x80

        if memory_write:
            bytes1 |= 0x40
        
        if datalog_acquire:
            bytes1 |= 0x20

        if user_func:
            bytes1 |= 0x10
        
        return Response(cmd.GetInfo, cmd.GetInfo.Subfunction.GetSupportedFeatures, Response.ResponseCode.OK, bytes([bytes1]))

    def pong(self):
        return Response(cmd.Heartbeat, cmd.Heartbeat.Subfunction.Pong, Response.ResponseCode.OK)

    def respond_read_memory_block(self, address, memory_data):
        data = struct.pack('>L', address) + bytes(memory_data)
        return Response(cmd.MemoryControl, cmd.MemoryControl.Subfunction.Read, Response.ResponseCode.OK, data)

    def respond_write_memory_block(self, address, length):
        data = struct.pack('>LH', address, length)
        return Response(cmd.MemoryControl, cmd.MemoryControl.Subfunction.Write, Response.ResponseCode.OK, data)


    def respond_data_get_targets(self, targets):
        data = bytes()
        for target in targets:
            if not isinstance(target, DatalogLocation):
                raise ValueError('Target must be an instance of DatalogLocation')

            data += struct.pack('BBB', target.target_id, target.location_type.value, len(target.name))
            data += target.name.encode('ascii')

        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetAvailableTarget, Response.ResponseCode.OK, data)

    def respond_datalog_get_bufsize(self, size):
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetBufferSize, Response.ResponseCode.OK, struct.pack('>L', size))

    def respond_datalog_get_sampling_rates(self, sampling_rates):
        data = struct.pack('>'+'f'*len(sampling_rates), *sampling_rates)
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetSamplingRates, Response.ResponseCode.OK, data)

    def respond_datalog_arm(self, record_id):
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ArmLog, Response.ResponseCode.OK, struct.pack('>H', record_id))

    def respond_datalog_disarm(self ):
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.DisarmLog, Response.ResponseCode.OK)

    def respond_datalog_status(self, status):
        status = LogStatus(status)
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetLogStatus, Response.ResponseCode.OK, struct.pack('B', status.value))
    
    def respond_datalog_list_recordings(self, recordings):
        data = bytes()
        for record in recordings:
            data += struct.pack('>HBH', record.record_id, record.location_type.value, record.size)
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ListRecordings, Response.ResponseCode.OK, data)

    def respond_read_recording(self, record_id, data):
        data = bytes(data)
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ReadRecordings, Response.ResponseCode.OK, struct.pack('>H', record_id) + data)

    def respond_configure_log(self, record_id):
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ConfigureDatalog, Response.ResponseCode.OK, struct.pack('>H', record_id))

    def respond_user_command(self, subfn, data=b''):
        return Response(cmd.UserCommand, subfn, Response.ResponseCode.OK, data)
  
    def respond_comm_discover(self, challenge_echo):
        resp_data = cmd.EstablishComm.MAGIC+struct.pack('>L', challenge_echo)
        return Response(cmd.EstablishComm, cmd.EstablishComm.Subfunction.Discover, Response.ResponseCode.OK, resp_data)

    def parse_response(self, response):
        data = {'valid' : True}
        if response.code != Response.ResponseCode.OK:
            raise InvalidResponseException(response, 'Response has response code different from OK. Payload data cannot be considered valid')

        try:
            if response.command == cmd.GetInfo:
                subfn = cmd.GetInfo.Subfunction(response.subfn)
                if subfn == cmd.GetInfo.Subfunction.GetProtocolVersion:
                    (data['major'], data['minor']) = struct.unpack('BB', response.payload)
                elif subfn == cmd.GetInfo.Subfunction.GetSupportedFeatures:
                    (byte1,) = struct.unpack('B', response.payload)
                    data['memory_read']     = True if (byte1 & 0x80) != 0 else False
                    data['memory_write']    = True if (byte1 & 0x40) != 0 else False
                    data['datalog_acquire'] = True if (byte1 & 0x20) != 0 else False
                    data['user_func']       = True if (byte1 & 0x10) != 0 else False  

                elif subfn == cmd.GetInfo.Subfunction.GetSoftwareId:
                    data['software_id'] = response.payload

            elif response.command == cmd.MemoryControl:
                subfn = cmd.MemoryControl.Subfunction(response.subfn)

                if subfn == cmd.MemoryControl.Subfunction.Read:
                    data['address'], = struct.unpack('>L', response.payload[0:4])
                    data['data'] =  bytes(response.payload[4:])

                elif subfn == cmd.MemoryControl.Subfunction.Write:
                    data['address'], data['length'] = struct.unpack('>LH', response.payload[0:6])

            elif response.command == cmd.DatalogControl:
                subfn = cmd.DatalogControl.Subfunction(response.subfn)

                if subfn == cmd.DatalogControl.Subfunction.GetAvailableTarget:
                    targets = []
                    pos = 0
                    while True:
                        if len(response.payload) < pos+1:
                            break
                        target_id, location_type_num, target_name_len = struct.unpack('BBB', response.payload[pos:pos+3])
                        location_type = DatalogLocation.Type(location_type_num)
                        pos +=3
                        name = response.payload[pos:pos+target_name_len].decode('ascii')
                        pos += target_name_len
                        targets.append(DatalogLocation(target_id, location_type, name))

                    data['targets'] = targets
                elif subfn == cmd.DatalogControl.Subfunction.GetBufferSize:
                    data['size'], = struct.unpack('>L', response.payload[0:4])

                elif subfn == cmd.DatalogControl.Subfunction.GetLogStatus:
                    data['status'] = LogStatus(int(response.payload[0]))

                elif subfn == cmd.DatalogControl.Subfunction.ArmLog:
                    data['record_id'], = struct.unpack('>H', response.payload)

                elif subfn == cmd.DatalogControl.Subfunction.ConfigureDatalog:
                    data['record_id'], = struct.unpack('>H', response.payload)

                elif subfn == cmd.DatalogControl.Subfunction.ReadRecordings:
                    data['record_id'], = struct.unpack('>H', response.payload[0:2])
                    data['data'] = response.payload[2:]

                elif subfn == cmd.DatalogControl.Subfunction.ListRecordings:
                    if len(response.payload) % 5 != 0:
                        raise Exception('Incomplete payload')
                    nrecords = int(len(response.payload)/5)
                    data['recordings'] = []
                    pos=0
                    for i in range(nrecords):
                        (record_id, location_type_num, size) = struct.unpack('>HBH', response.payload[pos:pos+5])
                        location_type = DatalogLocation.Type(location_type_num)
                        pos+=5
                        record = RecordInfo(record_id, location_type_num, size)
                        data['recordings'].append(record)
                        
                elif subfn == cmd.DatalogControl.Subfunction.GetSamplingRates:
                    if len(response.payload) % 4 != 0:
                        raise Exception('Incomplete payload')

                    nrates = int(len(response.payload)/4)
                    data['sampling_rates'] = list(struct.unpack('>'+'f'*nrates, response.payload))

            elif response.command == cmd.EstablishComm:
                subfn = cmd.EstablishComm.Subfunction(response.subfn)

                if subfn == cmd.EstablishComm.Subfunction.Discover:
                    data['magic'] =  response.payload[0:4]
                    data['challenge_echo'], = struct.unpack('>L', response.payload[4:8])


        except Exception as e:
            self.logger.error(str(e))
            data['valid'] = False
            raise

        if not data['valid']:
            raise InvalidResponseException(response, 'Could not properly decode response payload.')

        return data
