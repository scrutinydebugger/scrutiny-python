import struct

from . import commands as cmd
from . import Request, Response
from .exceptions import *
from .datalog import *
import logging
import ctypes

class Protocol:

    class AddressFormat:
        def __init__(self, nbits):
            PACK_CHARS = {
                8 : 'B',
                16 : 'H',
                32 : 'L',
                64 : 'Q'
            }

            if nbits not in PACK_CHARS:
                raise ValueError('Unsupported address format %s' % nbits)

            self.nbits = nbits
            self.nbytes = int(nbits/8)
            self.pack_char = PACK_CHARS[nbits]

        def get_address_size(self):
            return self.nbytes

        def get_pack_char(self):
            return self.pack_char


    def __init__(self, version_major=1, version_minor=0, address_size = 32):
        self.version_major = version_major
        self.version_minor = version_minor
        self.logger = logging.getLogger('protocol')
        self.set_address_size(address_size)    # default 32 bits address

    def set_address_size(self, address_size):
        self.address_format = self.AddressFormat(address_size)

    def encode_address(self, address):
        return struct.pack('>%s' % self.address_format.get_pack_char(),  address)

    def compute_challenge_16bits(self, challenge):
        return ctypes.c_uint16(~challenge).value

    def compute_challenge_32bits(self, challenge):
        return ctypes.c_uint32(~challenge).value

    def get_protocol_version(self):
        return Request(cmd.GetInfo, cmd.GetInfo.Subfunction.GetProtocolVersion)

    def get_software_id(self):
        return Request(cmd.GetInfo, cmd.GetInfo.Subfunction.GetSoftwareId)

    def get_supported_features(self):
        return Request(cmd.GetInfo, cmd.GetInfo.Subfunction.GetSupportedFeatures)

    def read_single_memory_block(self, address, length):
        block_list = [(address, length)]
        return self.read_memory_blocks(block_list)

    def read_memory_blocks(self, block_list):
        data = bytes()
        for block in block_list:
            addr = block[0]
            size = block[1]
            data += self.encode_address(addr) + struct.pack('>H', size)
        return Request(cmd.MemoryControl, cmd.MemoryControl.Subfunction.Read, data)

    def write_single_memory_block(self, address, data):
        block_list = [(address, data)]
        return self.write_memory_blocks(block_list)

    def write_memory_blocks(self, block_list):
        data = bytes()
        for block in block_list:
            addr = block[0]
            mem_data = block[1]
            data += self.encode_address(addr) + struct.pack('>H', len(mem_data)) + bytes(mem_data)
        return Request(cmd.MemoryControl, cmd.MemoryControl.Subfunction.Write, data)

    def comm_discover(self, challenge):
        data = cmd.CommControl.DISCOVER_MAGIC + struct.pack('>L', challenge)
        return Request(cmd.CommControl, cmd.CommControl.Subfunction.Discover, data) 

    def comm_heartbeat(self, session_id, challenge):
        return Request(cmd.CommControl, cmd.CommControl.Subfunction.Heartbeat, struct.pack('>LH', session_id, challenge))
   
    def comm_get_params(self):
        return Request(cmd.CommControl, cmd.CommControl.Subfunction.GetParams)

    def comm_connect(self):
        return Request(cmd.CommControl, cmd.CommControl.Subfunction.Connect, cmd.CommControl.CONNECT_MAGIC)
    
    def comm_disconnect(self, session_id):
        return Request(cmd.CommControl, cmd.CommControl.Subfunction.Disconnect, struct.pack('>L', session_id))

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


    def parse_request(self, req):
        data = {'valid' : True}
        try:
            if req.command == cmd.MemoryControl:
                subfn = cmd.MemoryControl.Subfunction(req.subfn)
                
                if subfn == cmd.MemoryControl.Subfunction.Read:                     # MemoryControl - Read
                    block_size = (2 + self.address_format.get_address_size())
                    if len(req.payload) % block_size  !=0:
                        raise Exception('Request data length is not a multiple of %d bytes (addres[%d] + length[2])' % (block_size, self.address_format.get_address_size()))
                    nblock = int(len(req.payload)/block_size)
                    data['blocks']=[]
                    for i in range(nblock):
                        (addr, length) = struct.unpack('>' + self.address_format.get_pack_char() + 'H', req.payload[(i*block_size+0):(i*block_size+block_size)])
                        data['blocks'].append(dict(address=addr, length=length))
                
                elif subfn == cmd.MemoryControl.Subfunction.Write:                  # MemoryControl - Write
                    data['blocks'] = []
                    c = self.address_format.get_pack_char()
                    address_length_size = 2 + self.address_format.get_address_size()
                    index = 0
                    while True:
                        if len(req.payload) < index + address_length_size:
                            raise Exception('Invalid request data, missing data')

                        addr, length = struct.unpack('>'+c+'H', req.payload[(index+0):(index+address_length_size)])
                        if len(req.payload) < index + address_length_size + length:
                            raise Exception('Data length and encoded length mismatch for address 0x%x' % addr)

                        req_data = req.payload[(index+address_length_size):(index+address_length_size+length)]
                        data['blocks'].append(dict(address = addr, data = req_data))
                        index += address_length_size+length

                        if index >= len(req.payload):
                            break;

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
           
            elif req.command == cmd.CommControl:
                subfn = cmd.CommControl.Subfunction(req.subfn)
            
                if subfn == cmd.CommControl.Subfunction.Discover:          # CommControl - Discover
                    data['magic'] = req.payload[0:4]
                    data['challenge'], = struct.unpack('>L', req.payload[4:8])
                
                elif subfn == cmd.CommControl.Subfunction.Heartbeat: 
                    data['session_id'], data['challenge'] = struct.unpack('>LH', req.payload[0:8])

                elif subfn == cmd.CommControl.Subfunction.Disconnect: 
                    data['session_id'] = struct.unpack('>L', req.payload[0:4])

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

    def respond_supported_features(self, memory_read=False, memory_write=False, datalog_acquire=False, user_command=False):
        bytes1 = 0
        if memory_read:
            bytes1 |= 0x80

        if memory_write:
            bytes1 |= 0x40
        
        if datalog_acquire:
            bytes1 |= 0x20

        if user_command:
            bytes1 |= 0x10
        
        return Response(cmd.GetInfo, cmd.GetInfo.Subfunction.GetSupportedFeatures, Response.ResponseCode.OK, bytes([bytes1]))
  
    def respond_comm_discover(self, challenge_response):
        resp_data = cmd.CommControl.DISCOVER_MAGIC+struct.pack('>L', challenge_response)
        return Response(cmd.CommControl, cmd.CommControl.Subfunction.Discover, Response.ResponseCode.OK, resp_data)

    def respond_comm_heartbeat(self, session_id, challenge_response):
        return Response(cmd.CommControl, cmd.CommControl.Subfunction.Heartbeat, Response.ResponseCode.OK, struct.pack('>LH', session_id, challenge_response))

    def respond_comm_get_params(self, max_data_size, max_bitrate, heartbeat_timeout, rx_timeout):
        data = struct.pack('>HLLL', max_data_size, max_bitrate, heartbeat_timeout, rx_timeout)
        return Response(cmd.CommControl, cmd.CommControl.Subfunction.GetParams, Response.ResponseCode.OK, data)

    def respond_comm_connect(self, session_id):
        resp_data = cmd.CommControl.CONNECT_MAGIC + struct.pack('>L', session_id)
        return Response(cmd.CommControl, cmd.CommControl.Subfunction.Connect, Response.ResponseCode.OK, resp_data)
   
    def respond_comm_disconnect(self):
        return Response(cmd.CommControl, cmd.CommControl.Subfunction.Disconnect, Response.ResponseCode.OK)

    def respond_read_single_memory_block(self, address, data):
        block_list = [(address, data)]
        return self.respond_read_memory_blocks(block_list)

    def respond_read_memory_blocks(self, block_list):
        data = bytes()
        for block in block_list:
            address = block[0]
            memory_data = bytes(block[1])
            data += self.encode_address(address) + struct.pack('>H', len(memory_data)) + memory_data

        return Response(cmd.MemoryControl, cmd.MemoryControl.Subfunction.Read, Response.ResponseCode.OK, data)

    def respond_write_single_memory_block(self, address, length):
        blocks = [(address, length)]
        return self.respond_write_memory_blocks(blocks)

    def respond_write_memory_blocks(self, blocklist):
        data = bytes()
        for block in blocklist:
            address = block[0]
            length = block[1]
            data += self.encode_address(address) + struct.pack('>H', length)

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
                    data['user_command']       = True if (byte1 & 0x10) != 0 else False  

                elif subfn == cmd.GetInfo.Subfunction.GetSoftwareId:
                    data['software_id'] = response.payload

            elif response.command == cmd.MemoryControl:
                subfn = cmd.MemoryControl.Subfunction(response.subfn)
                if subfn == cmd.MemoryControl.Subfunction.Read:
                    data['blocks']=[]
                    index=0
                    addr_size = self.address_format.get_address_size()
                    while True:
                        if len(response.payload[index:]) < addr_size+2:
                            raise Exception('Incomplete response payload')
                        c = self.address_format.get_pack_char()
                        addr, length = struct.unpack('>'+c+'H', response.payload[(index+0):(index+addr_size+2)])
                        if len(response.payload[(index+addr_size+2):]) < length:
                            raise Exception('Invalid data length')
                        memory_data = response.payload[(index+addr_size+2):(index+addr_size+2+length)]
                        data['blocks'].append(dict(address=addr, data=memory_data))
                        index += addr_size+2+length

                        if index == len(response.payload):
                            break

                elif subfn == cmd.MemoryControl.Subfunction.Write:
                    data['blocks'] = []
                    index=0
                    addr_size = self.address_format.get_address_size()
                    while True:
                        if len(response.payload[index:]) < addr_size+2:
                            raise Exception('Incomplete response payload')
                        c = self.address_format.get_pack_char()
                        addr, length = struct.unpack('>'+c+'H', response.payload[(index+0):(index+addr_size+2)])
                        data['blocks'].append(dict(address=addr, length=length))
                        index += addr_size+2

                        if index == len(response.payload):
                            break

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

            elif response.command == cmd.CommControl:
                subfn = cmd.CommControl.Subfunction(response.subfn)

                if subfn == cmd.CommControl.Subfunction.Discover:
                    data['magic'] =  response.payload[0:4]
                    data['challenge_response'], = struct.unpack('>L', response.payload[4:8])
                elif subfn == cmd.CommControl.Subfunction.Heartbeat:      
                    data['session_id'], data['challenge_response'] = struct.unpack('>LH', response.payload[0:6])
                elif subfn == cmd.CommControl.Subfunction.GetParams:
                    data['max_data_size'], data['max_bitrate'], data['heartbeat_timeout'], data['rx_timeout'] = struct.unpack('>HLLL', response.payload[0:14])
                elif subfn == cmd.CommControl.Subfunction.Connect:      
                    data['magic'] =  response.payload[0:4]
                    data['session_id'], = struct.unpack('>L', response.payload[4:8])


        except Exception as e:
            self.logger.error(str(e))
            data['valid'] = False
            raise

        if not data['valid']:
            raise InvalidResponseException(response, 'Could not properly decode response payload.')

        return data
