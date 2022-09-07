#    protocol.py
#        Allow encoding and decoding of data based on the Scrutiny Protocol
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import struct
import logging
import ctypes
import traceback

from .exceptions import *
from .datalog import *
from . import commands as cmd
from . import Request, Response
from scrutiny.core.codecs import Codecs
from scrutiny.core.basic_types import Endianness, RuntimePublishedValue
import scrutiny.server.protocol.typing as protocol_typing

from typing import Union, List, Tuple, Optional, TypedDict, Dict, Any, cast





class Protocol:
    version_major: int
    version_minor: int
    logger: logging.Logger
    rpv_map:Dict[int, RuntimePublishedValue]

    class AddressFormat:

        nbits: int
        nbytes: int
        pack_char: str

        def __init__(self, nbits: int):
            PACK_CHARS = {
                8: 'B',
                16: 'H',
                32: 'L',
                64: 'Q'
            }

            if nbits not in PACK_CHARS:
                raise ValueError('Unsupported address format %s' % nbits)

            self.nbits = nbits
            self.nbytes = int(nbits / 8)
            self.pack_char = PACK_CHARS[nbits]

        def get_address_size_bytes(self) -> int:
            return self.nbytes

        def get_address_size_bits(self) -> int:
            return self.nbits

        def get_pack_char(self) -> str:
            return self.pack_char

    def __init__(self, version_major: int = 1, version_minor: int = 0, address_size_bits: int = 32):
        self.version_major = version_major
        self.version_minor = version_minor
        self.logger = logging.getLogger(self.__class__.__name__)
        self.rpv_map = {}
        self.set_address_size_bits(address_size_bits)    # default 32 bits address

    def set_address_size_bits(self, address_size_bits: int) -> None:
        self.address_format = self.AddressFormat(nbits=address_size_bits)

    def set_address_size_bytes(self, address_size_byte: int) -> None:
        self.address_format = self.AddressFormat(nbits=address_size_byte * 8)

    def get_address_size_bytes(self) -> int:
        return self.address_format.get_address_size_bytes()

    def get_address_size_bits(self) -> int:
        return self.address_format.get_address_size_bits()

    def set_version(self, major: int, minor: int) -> None:
        if not isinstance(major, int) or not isinstance(minor, int):
            raise ValueError('Version major and minor number must be a valid integer.')

        if major == 999 and minor == 123:
            pass  # Special version for unit test

        elif major != 1 or minor != 0:  # For futur
            raise NotImplementedError('Protocol version %d.%d is not supported' % (major, minor))

        if major != self.version_major or minor != self.version_minor:
            self.logger.info('Using protocol version %d.%d' % (major, minor))

        self.version_major = major
        self.version_minor = minor

    def get_version(self):
        return (self.version_major, self.version_minor)

    def configure_rpvs(self, rpvs:List[RuntimePublishedValue]):
        self.rpv_map = {}
        for rpv in rpvs:
            self.rpv_map[rpv.id] = rpv

    def encode_address(self, address: int) -> bytes:
        return struct.pack('>%s' % self.address_format.get_pack_char(), address)

    def decode_address(self, buff: bytes) -> int:
        return struct.unpack('>%s' % self.address_format.get_pack_char(), buff[0:self.get_address_size_bytes()])[0]

    def compute_challenge_16bits(self, challenge: int) -> int:
        return ctypes.c_uint16(~challenge).value

    def compute_challenge_32bits(self, challenge: int) -> int:
        return ctypes.c_uint32(~challenge).value

    def get_protocol_version(self) -> Request:
        return Request(cmd.GetInfo, cmd.GetInfo.Subfunction.GetProtocolVersion, response_payload_size=2)

    def get_software_id(self) -> Request:
        return Request(cmd.GetInfo, cmd.GetInfo.Subfunction.GetSoftwareId, response_payload_size=32)

    def get_supported_features(self) -> Request:
        return Request(cmd.GetInfo, cmd.GetInfo.Subfunction.GetSupportedFeatures, response_payload_size=1)

    def get_special_memory_region_count(self) -> Request:
        return Request(cmd.GetInfo, cmd.GetInfo.Subfunction.GetSpecialMemoryRegionCount, response_payload_size=2)

    def get_special_memory_region_location(self, region_type: Union[int, cmd.GetInfo.MemoryRangeType], region_index: int) -> Request:
        if isinstance(region_type, cmd.GetInfo.MemoryRangeType):
            region_type = region_type.value
        data = struct.pack('BB', region_type, region_index)
        return Request(cmd.GetInfo, cmd.GetInfo.Subfunction.GetSpecialMemoryRegionLocation, data, response_payload_size=2 + self.get_address_size_bytes() * 2)

    def get_rpv_count(self):
        return Request(cmd.GetInfo, cmd.GetInfo.Subfunction.GetRuntimePublishedValuesCount, bytes(), response_payload_size=2)
    
    def get_rpv_definition(self, start:int, count:int):
        return Request(cmd.GetInfo, cmd.GetInfo.Subfunction.GetRuntimePublishedValuesDefinition, struct.pack('>HH', start, count), response_payload_size=3*count)

    def read_memory_request_size_per_block(self):
        return self.get_address_size_bytes() + 2  # Address + 16 bits length

    def read_memory_response_overhead_size_per_block(self):
        return self.get_address_size_bytes() + 2

    def read_single_memory_block(self, address: int, length: int) -> Request:
        block_list = [(address, length)]
        return self.read_memory_blocks(block_list)

    def read_memory_blocks(self, block_list) -> Request:
        data = bytes()
        total_length = 0
        for block in block_list:
            addr = block[0]
            size = block[1]
            total_length += size
            data += self.encode_address(addr) + struct.pack('>H', size)
        return Request(cmd.MemoryControl, cmd.MemoryControl.Subfunction.Read, data, response_payload_size=(self.get_address_size_bytes() + 2) * len(block_list) + total_length)

    def write_single_memory_block(self, address: int, data: bytes, write_mask: Optional[bytes] = None) -> Request:
        if write_mask is None:
            block_list = [(address, data)]
            return self.write_memory_blocks(block_list)
        else:
            block_list_masked = [(address, data, write_mask)]
            return self.write_memory_blocks_masked(block_list_masked)

    def write_memory_blocks(self, block_list: List[Tuple[int, bytes]]) -> Request:
        data = bytes()
        for block in block_list:
            addr = block[0]
            mem_data = block[1]
            data += self.encode_address(addr) + struct.pack('>H', len(mem_data)) + bytes(mem_data)
        return Request(cmd.MemoryControl, cmd.MemoryControl.Subfunction.Write, data, response_payload_size=(self.get_address_size_bytes() + 2) * len(block_list))

    def write_memory_blocks_masked(self, block_list: List[Tuple[int, bytes, bytes]]) -> Request:
        data = bytes()
        for block in block_list:
            addr = block[0]
            mem_data = block[1]
            mask = block[2]
            if len(mem_data) != len(mask):
                raise Exception('Length of mask must match length of data')
            data += self.encode_address(addr) + struct.pack('>H', len(mem_data)) + bytes(mem_data) + bytes(mask)
        return Request(cmd.MemoryControl, cmd.MemoryControl.Subfunction.WriteMasked, data, response_payload_size=(self.get_address_size_bytes() + 2) * len(block_list))

    def read_runtime_published_values(self, ids:Union[int, List[int]]):
        if not isinstance(ids, List):
            ids = [ids]
        
        expected_response_size = 0
        for id in ids:
            if id not in self.rpv_map:
                raise Exception('Unkown RuntimePublishedValue ID %s' % id)
            rpv = self.rpv_map[id]
            typesize = rpv.datatype.get_size_byte()
            assert typesize is not None
            expected_response_size += 2 + typesize
        
        nbids = len(ids)
        data = struct.pack('>'+'H'*nbids, *ids)
        return Request(cmd.MemoryControl, cmd.MemoryControl.Subfunction.ReadRPV, data, response_payload_size=expected_response_size)

    def write_runtime_published_values(self, values:Union[List[Tuple[int, Any]], Tuple[int, Any]]):
        if not isinstance(values, list):
            values = [values]
        
        data = bytes()
        for id, val in values:
            if id not in self.rpv_map:
                raise Exception('Unkown RuntimePublishedValue ID %s' % id)
            rpv = self.rpv_map[id]
            codec = Codecs.get(rpv.datatype, Endianness.Big)
            data += struct.pack('>H', id)
            data += codec.encode(val)
        
        return Request(cmd.MemoryControl, cmd.MemoryControl.Subfunction.WriteRPV, data, response_payload_size=len(values)*3)

    def comm_discover(self) -> Request:
        data = cmd.CommControl.DISCOVER_MAGIC
        return Request(cmd.CommControl, cmd.CommControl.Subfunction.Discover, data, response_payload_size=16)  # 16 minimum

    def comm_heartbeat(self, session_id: int, challenge: int) -> Request:
        return Request(cmd.CommControl, cmd.CommControl.Subfunction.Heartbeat, struct.pack('>LH', session_id, challenge), response_payload_size=6)

    def heartbeat_expected_challenge_response(self, challenge: int) -> int:
        return ~challenge & 0xFFFF

    def comm_get_params(self) -> Request:
        # rx_buffer_size, tx_buffer_size, bitrate, heartbeat_timeout, rx_timeout, address_size
        return Request(cmd.CommControl, cmd.CommControl.Subfunction.GetParams, response_payload_size=2 + 2 + 4 + 4 + 4 + 1)

    def comm_connect(self) -> Request:
        return Request(cmd.CommControl, cmd.CommControl.Subfunction.Connect, cmd.CommControl.CONNECT_MAGIC, response_payload_size=4 + 4)  # Magic + Session id

    def comm_disconnect(self, session_id: int) -> Request:
        return Request(cmd.CommControl, cmd.CommControl.Subfunction.Disconnect, struct.pack('>L', session_id), response_payload_size=0)

    def datalog_get_targets(self) -> Request:
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetAvailableTarget)  # todo : response_payload_size

    def datalog_get_bufsize(self) -> Request:
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetBufferSize)    # todo : response_payload_size

    def datalog_get_sampling_rates(self) -> Request:
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetSamplingRates)  # todo : response_payload_size

    def datalog_configure_log(self, conf: DatalogConfiguration) -> Request:
        if not isinstance(conf, DatalogConfiguration):
            raise ValueError('Given configuration must be an instance of protocol.DatalogConfiguration')

        data = struct.pack('>BfBH', conf.destination, conf.sample_rate, conf.decimation, len(conf.watches))
        for watch in conf.watches:
            data += struct.pack('>LH', watch.address, watch.length)

        data += struct.pack('B', conf.trigger.condition.value)

        for operand in [conf.trigger.operand1, conf.trigger.operand2]:
            if operand.operand_type == DatalogConfiguration.OperandType.CONST:
                data += struct.pack('>Bf', operand.operand_type.value, operand.value)
            elif operand.operand_type == DatalogConfiguration.OperandType.WATCH:
                data += struct.pack('>BLBB', operand.operand_type.value, operand.address, operand.length, operand.interpret_as.value)
            else:
                raise Exception('Unknown operand type %s' % operand.operand_type)

        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ConfigureDatalog, data)   # todo : response_payload_size

    def datalog_get_list_recordings(self) -> Request:
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ListRecordings)   # todo : response_payload_size

    def datalog_read_recording(self, record_id: int) -> Request:
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ReadRecordings, struct.pack('>H', record_id))  # todo : response_payload_size

    def datalog_arm(self) -> Request:
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ArmLog)   # todo : response_payload_size

    def datalog_disarm(self) -> Request:
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.DisarmLog)    # todo : response_payload_size

    def datalog_status(self) -> Request:
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetLogStatus)  # todo : response_payload_size

    def user_command(self, subfn: int, data: bytes = b'') -> Request:
        return Request(cmd.UserCommand, subfn, data)    # todo : response_payload_size

    def parse_request(self, req: Request) -> protocol_typing.RequestData:
        data: protocol_typing.RequestData = cast(protocol_typing.Request.Empty, {})
        subfn: Enum
        valid:bool = True

        try:
            if req.command == cmd.GetInfo:
                
                subfn = cmd.GetInfo.Subfunction(req.subfn)

                if subfn == cmd.GetInfo.Subfunction.GetSpecialMemoryRegionLocation:
                    data = cast(protocol_typing.Request.GetInfo.GetSpecialMemoryRegionLocation, data)
                    region_type, region_index = struct.unpack('BB', req.payload[0:2])
                    data['region_type'] = cmd.GetInfo.MemoryRangeType(region_type)
                    data['region_index'] = region_index
                
                elif subfn == cmd.GetInfo.Subfunction.GetRuntimePublishedValuesDefinition:
                    data = cast(protocol_typing.Request.GetInfo.GetRuntimePublishedValuesDefinition, data)
                    data['start'], data['count'] = struct.unpack('>HH', req.payload[0:4])

            elif req.command == cmd.MemoryControl:
                subfn = cmd.MemoryControl.Subfunction(req.subfn)

                if subfn == cmd.MemoryControl.Subfunction.Read:                     # MemoryControl - Read
                    data = cast(protocol_typing.Request.MemoryControl.Read, data)
                    block_size = (2 + self.get_address_size_bytes())
                    if len(req.payload) % block_size != 0:
                        raise Exception(
                            'Request data length is not a multiple of %d bytes (addres[%d] + length[2])' % (block_size, self.get_address_size_bytes()))
                    nblock = int(len(req.payload) / block_size)
                    data['blocks_to_read'] = []
                    for i in range(nblock):
                        (addr, length) = struct.unpack('>' + self.address_format.get_pack_char() +
                                                       'H', req.payload[(i * block_size + 0):(i * block_size + block_size)])
                        data['blocks_to_read'].append(dict(address=addr, length=length))

                elif subfn == cmd.MemoryControl.Subfunction.Write:                  # MemoryControl - Write
                    data = cast(protocol_typing.Request.MemoryControl.Write, data)
                    data['blocks_to_write'] = []
                    c = self.address_format.get_pack_char()
                    address_length_size = 2 + self.get_address_size_bytes()
                    index = 0
                    while True:
                        if len(req.payload) < index + address_length_size:
                            raise Exception('Invalid request data, missing data')

                        addr, length = struct.unpack('>' + c + 'H', req.payload[(index + 0):(index + address_length_size)])
                        if len(req.payload) < index + address_length_size + length:
                            raise Exception('Data length and encoded length mismatch for address 0x%x' % addr)

                        req_data = req.payload[(index + address_length_size):(index + address_length_size + length)]
                        data['blocks_to_write'].append(dict(address=addr, data=req_data))
                        index += address_length_size + length

                        if index >= len(req.payload):
                            break

                elif subfn == cmd.MemoryControl.Subfunction.WriteMasked:                  # MemoryControl - WriteMasked
                    data = cast(protocol_typing.Request.MemoryControl.Write, data)
                    data['blocks_to_write'] = []
                    c = self.address_format.get_pack_char()
                    address_length_size = 2 + self.get_address_size_bytes()
                    index = 0
                    while True:
                        if len(req.payload) < index + address_length_size:
                            raise Exception('Invalid request data, missing data')

                        addr, length = struct.unpack('>' + c + 'H', req.payload[(index + 0):(index + address_length_size)])
                        if len(req.payload) < index + address_length_size + 2 * length:   # 2x length because of mask
                            raise Exception('Data length and encoded length mismatch for address 0x%x' % addr)

                        req_data = req.payload[(index + address_length_size):(index + address_length_size + length)]
                        req_mask = req.payload[(index + address_length_size + length):(index + address_length_size + 2 * length)]
                        data['blocks_to_write'].append(dict(address=addr, data=req_data, write_mask=req_mask))
                        index += address_length_size + 2 * length

                        if index >= len(req.payload):
                            break
                
                elif subfn == cmd.MemoryControl.Subfunction.ReadRPV:
                    data = cast(protocol_typing.Request.MemoryControl.ReadRPV, data)
                    data['rpvs_id'] = []
                    if len(req.payload) % 2 != 0:
                        raise Exception('Invalid payload length')
                    
                    nbids = len(req.payload)//2
                    for i in range(nbids):
                        id = struct.unpack('>H', req.payload[i*2:i*2+2])[0]
                        data['rpvs_id'].append(id)
                
                elif subfn == cmd.MemoryControl.Subfunction.WriteRPV:
                    data = cast(protocol_typing.Request.MemoryControl.WriteRPV, data)
                    data['rpvs'] = []
                    cursor = 0

                    while cursor < len(req.payload):
                        id = struct.unpack('>H', req.payload[cursor:cursor+2])[0]
                        cursor+=2
                        if id not in self.rpv_map:
                            raise Exception('Request requires to decode RPV with ID %s which is unknown' % id) 
                        
                        rpv = self.rpv_map[id]
                        codec = Codecs.get(rpv.datatype, Endianness.Big)
                        datasize = rpv.datatype.get_size_byte()
                        assert datasize is not None
                        value = codec.decode(req.payload[cursor:cursor+datasize])
                        cursor += datasize
                        data['rpvs'].append(dict(id=id, value=value))

            elif req.command == cmd.DatalogControl:
                subfn = cmd.DatalogControl.Subfunction(req.subfn)

                if subfn == cmd.DatalogControl.Subfunction.ReadRecordings:          # DatalogControl - ReadRecordings
                    data = cast(protocol_typing.Request.DatalogControl.ReadRecordings, data)
                    (data['record_id'],) = struct.unpack('>H', req.payload[0:2])

                elif subfn == cmd.DatalogControl.Subfunction.ConfigureDatalog:      # DatalogControl - ConfigureDatalog
                    data = cast(protocol_typing.Request.DatalogControl.ConfigureDatalog, data)
                    conf = DatalogConfiguration()
                    (conf.destination, conf.sample_rate, conf.decimation, num_watches) = struct.unpack('>BfBH', req.payload[0:8])

                    for i in range(num_watches):
                        pos = 8 + i * 6
                        (addr, length) = struct.unpack('>LH', req.payload[pos:pos + 6])
                        conf.add_watch(addr, length)
                    pos = 8 + num_watches * 6
                    condition_num, = struct.unpack('>B', req.payload[pos:pos + 1])
                    conf.trigger.condition = DatalogConfiguration.TriggerCondition(condition_num)
                    pos += 1
                    operands: List[DatalogConfiguration.Operand] = []
                    for i in range(2):
                        operand_type_num, = struct.unpack('B', req.payload[pos:pos + 1])
                        pos += 1
                        operand_type = DatalogConfiguration.OperandType(operand_type_num)
                        if operand_type == DatalogConfiguration.OperandType.CONST:
                            val, = struct.unpack('>f', req.payload[pos:pos + 4])
                            operands.append(DatalogConfiguration.ConstOperand(val))
                            pos += 4
                        elif operand_type == DatalogConfiguration.OperandType.WATCH:
                            (address, length, interpret_as) = struct.unpack('>LBB', req.payload[pos:pos + 6])
                            operands.append(DatalogConfiguration.WatchOperand(address=address, length=length, interpret_as=interpret_as))
                            pos += 6
                    conf.trigger.operand1 = operands[0]
                    conf.trigger.operand2 = operands[1]
                    data['configuration'] = conf

            elif req.command == cmd.CommControl:
                subfn = cmd.CommControl.Subfunction(req.subfn)

                if subfn == cmd.CommControl.Subfunction.Discover:          # CommControl - Discover
                    data = cast(protocol_typing.Request.CommControl.Discover, data)
                    data['magic'] = req.payload[0:4]

                elif subfn == cmd.CommControl.Subfunction.Connect:          # CommControl - Connect
                    data = cast(protocol_typing.Request.CommControl.Connect, data)
                    data['magic'] = req.payload[0:4]

                elif subfn == cmd.CommControl.Subfunction.Heartbeat:
                    data = cast(protocol_typing.Request.CommControl.Heartbeat, data)
                    data['session_id'], data['challenge'] = struct.unpack('>LH', req.payload[0:8])

                elif subfn == cmd.CommControl.Subfunction.Disconnect:
                    data = cast(protocol_typing.Request.CommControl.Disconnect, data)
                    data['session_id'], = struct.unpack('>L', req.payload[0:4])

        except Exception as e:
            self.logger.error(str(e))
            self.logger.debug(traceback.format_exc())
            valid = False

        if not valid:
            raise InvalidRequestException(req, 'Could not properly decode request payload.')

        return data


# ======================== Response =================

    def respond_not_ok(self, req: Request, code: Union[int, Enum]) -> Response:
        return Response(req.command, req.subfn, Response.ResponseCode(code))

    def respond_protocol_version(self, major: Optional[int] = None, minor: Optional[int] = None) -> Response:
        if major is None:
            major = self.version_major

        if minor is None:
            minor = self.version_minor

        return Response(cmd.GetInfo, cmd.GetInfo.Subfunction.GetProtocolVersion, Response.ResponseCode.OK, bytes([major, minor]))

    def respond_software_id(self, software_id: Union[bytes, List[int], bytearray]) -> Response:
        return Response(cmd.GetInfo, cmd.GetInfo.Subfunction.GetSoftwareId, Response.ResponseCode.OK, bytes(software_id))

    def respond_supported_features(self, memory_write: bool = False, datalog_acquire: bool = False, user_command: bool = False) -> Response:
        bytes1 = 0
        if memory_write:
            bytes1 |= 0x80

        if datalog_acquire:
            bytes1 |= 0x40

        if user_command:
            bytes1 |= 0x20

        return Response(cmd.GetInfo, cmd.GetInfo.Subfunction.GetSupportedFeatures, Response.ResponseCode.OK, bytes([bytes1]))

    def respond_special_memory_region_count(self, readonly: int, forbidden: int) -> Response:
        return Response(cmd.GetInfo, cmd.GetInfo.Subfunction.GetSpecialMemoryRegionCount, Response.ResponseCode.OK, struct.pack('BB', readonly, forbidden))

    def respond_special_memory_region_location(self, region_type: Union[cmd.GetInfo.MemoryRangeType, int], region_index: int, start: int, end: int) -> Response:
        if isinstance(region_type, cmd.GetInfo.MemoryRangeType):
            region_type = region_type.value
        data = struct.pack('BB', region_type, region_index)
        data += self.encode_address(start) + self.encode_address(end)
        return Response(cmd.GetInfo, cmd.GetInfo.Subfunction.GetSpecialMemoryRegionLocation, Response.ResponseCode.OK, data)

    def respond_get_rpv_count(self, count:int):
        return Response(cmd.GetInfo, cmd.GetInfo.Subfunction.GetRuntimePublishedValuesCount, Response.ResponseCode.OK, struct.pack('>H', count))

    def respond_get_rpv_definition(self, rpvs:List[RuntimePublishedValue]):
        payload = bytes()
        
        for rpv in rpvs:
            vtype = rpv.datatype.value
            payload += struct.pack('>HB', rpv.id, vtype)
        
        return Response(cmd.GetInfo, cmd.GetInfo.Subfunction.GetRuntimePublishedValuesDefinition, Response.ResponseCode.OK, payload)

    def respond_comm_discover(self, firmware_id: Union[bytes, List[int], bytearray], display_name: str) -> Response:
        if len(display_name) > 64:
            raise Exception('Display name too long.')

        resp_data = bytes([self.version_major, self.version_minor]) + bytes(firmware_id) + bytes([len(display_name)]) + display_name.encode('utf8')
        return Response(cmd.CommControl, cmd.CommControl.Subfunction.Discover, Response.ResponseCode.OK, resp_data)

    def respond_comm_heartbeat(self, session_id: int, challenge_response: int) -> Response:
        return Response(cmd.CommControl, cmd.CommControl.Subfunction.Heartbeat, Response.ResponseCode.OK, struct.pack('>LH', session_id, challenge_response))

    def respond_comm_get_params(self, max_rx_data_size: int, max_tx_data_size: int, max_bitrate_bps: int, heartbeat_timeout_us: int, rx_timeout_us: int, address_size_byte: int) -> Response:
        data = struct.pack('>HHLLLB', max_rx_data_size, max_tx_data_size, max_bitrate_bps, heartbeat_timeout_us, rx_timeout_us, address_size_byte)
        return Response(cmd.CommControl, cmd.CommControl.Subfunction.GetParams, Response.ResponseCode.OK, data)

    def respond_comm_connect(self, session_id: int) -> Response:
        resp_data = cmd.CommControl.CONNECT_MAGIC + struct.pack('>L', session_id)
        return Response(cmd.CommControl, cmd.CommControl.Subfunction.Connect, Response.ResponseCode.OK, resp_data)

    def respond_comm_disconnect(self) -> Response:
        return Response(cmd.CommControl, cmd.CommControl.Subfunction.Disconnect, Response.ResponseCode.OK)

    def respond_read_single_memory_block(self, address: int, data: bytes) -> Response:
        block_list = [(address, data)]
        return self.respond_read_memory_blocks(block_list)

    def respond_read_memory_blocks(self, block_list: List[Tuple[int, bytes]]) -> Response:
        data = bytes()
        for block in block_list:
            address = block[0]
            memory_data = bytes(block[1])
            data += self.encode_address(address) + struct.pack('>H', len(memory_data)) + memory_data

        return Response(cmd.MemoryControl, cmd.MemoryControl.Subfunction.Read, Response.ResponseCode.OK, data)

    def respond_write_single_memory_block(self, address: int, length: int) -> Response:
        blocks = [(address, length)]
        return self.respond_write_memory_blocks(blocks)

    def respond_write_single_memory_block_masked(self, address: int, length: int) -> Response:
        blocks = [(address, length)]
        return self.respond_write_memory_blocks_masked(blocks)

    def respond_write_memory_blocks(self, blocklist: List[Tuple[int, int]]) -> Response:
        data = bytes()
        for block in blocklist:
            address = block[0]
            length = block[1]
            data += self.encode_address(address) + struct.pack('>H', length)

        return Response(cmd.MemoryControl, cmd.MemoryControl.Subfunction.Write, Response.ResponseCode.OK, data)

    def respond_write_memory_blocks_masked(self, blocklist: List[Tuple[int, int]]) -> Response:
        data = bytes()
        for block in blocklist:
            address = block[0]
            length = block[1]
            data += self.encode_address(address) + struct.pack('>H', length)

        return Response(cmd.MemoryControl, cmd.MemoryControl.Subfunction.WriteMasked, Response.ResponseCode.OK, data)
    
    def respond_read_runtime_published_values(self, vals:Union[Tuple[int, Any], List[Tuple[int, Any]]] ):
        if not isinstance(vals, list):
            vals = [vals]
        
        data = bytes()
        for id, val in vals:
            if id not in self.rpv_map:
                raise Exception('Unkown RuntimePublishedValue ID %s' % id)
            
            rpv = self.rpv_map[id]
            codec = Codecs.get(rpv.datatype, Endianness.Big)
            data += struct.pack('>H', id) + codec.encode(val)
        
        return Response(cmd.MemoryControl, cmd.MemoryControl.Subfunction.ReadRPV, Response.ResponseCode.OK, data)

    def respond_write_runtime_published_values(self, ids:Union[int, List[int]]):
        if not isinstance(ids, list):
            ids = [ids]
        
        data = bytes()
        for id in ids:
            if id not in self.rpv_map:
                raise Exception('Unkown RuntimePublishedValue ID %s' % id)
            rpv = self.rpv_map[id]
            data += struct.pack('>HB', id, rpv.datatype.get_size_byte())
        
        return Response(cmd.MemoryControl, cmd.MemoryControl.Subfunction.WriteRPV, Response.ResponseCode.OK, data)

    def respond_data_get_targets(self, targets: List[DatalogLocation]) -> Response:
        data = bytes()
        for target in targets:
            if not isinstance(target, DatalogLocation):
                raise ValueError('Target must be an instance of DatalogLocation')

            data += struct.pack('BBB', target.target_id, target.location_type.value, len(target.name))
            data += target.name.encode('ascii')

        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetAvailableTarget, Response.ResponseCode.OK, data)

    def respond_datalog_get_bufsize(self, size: int) -> Response:
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetBufferSize, Response.ResponseCode.OK, struct.pack('>L', size))

    def respond_datalog_get_sampling_rates(self, sampling_rates: List[float]) -> Response:
        data = struct.pack('>' + 'f' * len(sampling_rates), *sampling_rates)
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetSamplingRates, Response.ResponseCode.OK, data)

    def respond_datalog_arm(self, record_id: int) -> Response:
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ArmLog, Response.ResponseCode.OK, struct.pack('>H', record_id))

    def respond_datalog_disarm(self) -> Response:
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.DisarmLog, Response.ResponseCode.OK)

    def respond_datalog_status(self, status: Union[LogStatus, int]) -> Response:
        status = LogStatus(status)
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetLogStatus, Response.ResponseCode.OK, struct.pack('B', status.value))

    def respond_datalog_list_recordings(self, recordings: List[RecordInfo]) -> Response:
        data = bytes()
        for record in recordings:
            data += struct.pack('>HBH', record.record_id, record.location_type.value, record.size)
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ListRecordings, Response.ResponseCode.OK, data)

    def respond_read_recording(self, record_id: int, data: bytes) -> Response:
        data = bytes(data)
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ReadRecordings, Response.ResponseCode.OK, struct.pack('>H', record_id) + data)

    def respond_configure_log(self, record_id: int) -> Response:
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ConfigureDatalog, Response.ResponseCode.OK, struct.pack('>H', record_id))

    def respond_user_command(self, subfn: Union[int, Enum], data: bytes = b'') -> Response:
        return Response(cmd.UserCommand, subfn, Response.ResponseCode.OK, data)

    def parse_response(self, response: Response) -> protocol_typing.ResponseData:
        data: protocol_typing.ResponseData = cast(protocol_typing.Response.Empty, {})
        subfn: Enum
        valid:bool = True

        # For now, all commands have no data in negative response. But it could be different in the future.
        # So it might be possible in the furture to move this condition and have a response with
        # a response code different from OK with valid data to decode.
        if response.code == Response.ResponseCode.OK:
            try:
                if response.command == cmd.GetInfo:
                    subfn = cmd.GetInfo.Subfunction(response.subfn)
                    if subfn == cmd.GetInfo.Subfunction.GetProtocolVersion:
                        data = cast(protocol_typing.Response.GetInfo.GetProtocolVersion, data)
                        (data['major'], data['minor']) = struct.unpack('BB', response.payload)
                    elif subfn == cmd.GetInfo.Subfunction.GetSupportedFeatures:
                        data = cast(protocol_typing.Response.GetInfo.GetSupportedFeatures, data)
                        (byte1,) = struct.unpack('B', response.payload)
                        data['memory_write'] = True if (byte1 & 0x80) != 0 else False
                        data['datalog_acquire'] = True if (byte1 & 0x40) != 0 else False
                        data['user_command'] = True if (byte1 & 0x20) != 0 else False

                    elif subfn == cmd.GetInfo.Subfunction.GetSoftwareId:
                        data = cast(protocol_typing.Response.GetInfo.GetSoftwareId, data)
                        data['software_id'] = response.payload

                    elif subfn == cmd.GetInfo.Subfunction.GetSpecialMemoryRegionCount:
                        data = cast(protocol_typing.Response.GetInfo.GetSpecialMemoryRegionCount, data)
                        data['nbr_readonly'], data['nbr_forbidden'] = struct.unpack('BB', response.payload[0:2])

                    elif subfn == cmd.GetInfo.Subfunction.GetSpecialMemoryRegionLocation:
                        data = cast(protocol_typing.Response.GetInfo.GetSpecialMemoryRegionLocation, data)
                        data['region_type'] = cmd.GetInfo.MemoryRangeType(response.payload[0])
                        data['region_index'] = response.payload[1]
                        data['start'] = self.decode_address(response.payload[2:])
                        data['end'] = self.decode_address(response.payload[2 + self.get_address_size_bytes():])
                    
                    elif subfn == cmd.GetInfo.Subfunction.GetRuntimePublishedValuesCount:
                        data = cast(protocol_typing.Response.GetInfo.GetRuntimePublishedValuesCount, data)
                        data['count'], = struct.unpack('>H', response.payload[0:2])
                    
                    elif subfn == cmd.GetInfo.Subfunction.GetRuntimePublishedValuesDefinition:
                        data = cast(protocol_typing.Response.GetInfo.GetRuntimePublishedValuesDefinition, data)
                        n = 3   # 3 bytes per RPV
                        if len(response.payload) % n != 0:
                            raise Exception('Invalid payload length for GetRuntimePublishedValuesDefinition')
                        data['rpvs'] = []

                        nbr_rpv = len(response.payload)//n
                        for i in range(nbr_rpv):
                            vid, typeint,  = struct.unpack('>HB', response.payload[i*n+0:i*n+n])                            
                            data['rpvs'].append(RuntimePublishedValue(id=vid, datatype=typeint))

                elif response.command == cmd.MemoryControl:
                    subfn = cmd.MemoryControl.Subfunction(response.subfn)
                    if subfn == cmd.MemoryControl.Subfunction.Read:
                        data = cast(protocol_typing.Response.MemoryControl.Read, data)
                        data['read_blocks'] = []
                        index = 0
                        addr_size = self.get_address_size_bytes()
                        while True:
                            if len(response.payload[index:]) < addr_size + 2:
                                raise Exception('Incomplete response payload')
                            c = self.address_format.get_pack_char()
                            addr, length = struct.unpack('>' + c + 'H', response.payload[(index + 0):(index + addr_size + 2)])
                            if len(response.payload[(index + addr_size + 2):]) < length:
                                raise Exception('Invalid data length')
                            memory_data = response.payload[(index + addr_size + 2):(index + addr_size + 2 + length)]
                            data['read_blocks'].append(dict(address=addr, data=memory_data))
                            index += addr_size + 2 + length

                            if index == len(response.payload):
                                break

                    elif subfn == cmd.MemoryControl.Subfunction.Write or subfn == cmd.MemoryControl.Subfunction.WriteMasked:
                        data = cast(protocol_typing.Response.MemoryControl.Write, data)
                        data['written_blocks'] = []
                        index = 0
                        addr_size = self.get_address_size_bytes()
                        while True:
                            if len(response.payload[index:]) < addr_size + 2:
                                raise Exception('Incomplete response payload')
                            c = self.address_format.get_pack_char()
                            addr, length = struct.unpack('>' + c + 'H', response.payload[(index + 0):(index + addr_size + 2)])
                            data['written_blocks'].append(dict(address=addr, length=length))
                            index += addr_size + 2

                            if index == len(response.payload):
                                break

                    elif subfn == cmd.MemoryControl.Subfunction.ReadRPV:
                        data = cast(protocol_typing.Response.MemoryControl.ReadRPV, data)
                        data['read_rpv'] = []

                        cursor = 0
                        while cursor < len(response.payload):
                            if len(response.payload)-cursor < 2:
                                raise Exception('Invalid data length')
                            
                            id, = struct.unpack('>H', response.payload[cursor:cursor+2])
                            cursor+=2
                            if id not in self.rpv_map:
                                raise Exception('Unknown RuntimePublishedValue of ID 0x%x', id)
                            rpv = self.rpv_map[id]
                            typesize = rpv.datatype.get_size_byte()
                            assert typesize is not None
                            if len(response.payload)-cursor < typesize:
                                raise Exception('Incomplete data for RPV with ID 0x%x', id)
                            
                            codec = Codecs.get(rpv.datatype, Endianness.Big)
                            val = codec.decode(response.payload[cursor:cursor+typesize])
                            cursor += typesize
                            data['read_rpv'].append(dict(id=id, data=val))

                    elif subfn == cmd.MemoryControl.Subfunction.WriteRPV:
                        data = cast(protocol_typing.Response.MemoryControl.WriteRPV, data)
                        data['written_rpv'] = []
                        cursor = 0
                        while cursor < len(response.payload):
                            if len(response.payload)-cursor < 3:
                                raise Exception('Invalid data length')
                            id, size = struct.unpack('>HB', response.payload[cursor:cursor+3])
                            cursor+=3
                            data['written_rpv'].append(dict(id=id, size=size))

                elif response.command == cmd.DatalogControl:
                    subfn = cmd.DatalogControl.Subfunction(response.subfn)

                    if subfn == cmd.DatalogControl.Subfunction.GetAvailableTarget:
                        data = cast(protocol_typing.Response.DatalogControl.GetAvailableTarget, data)
                        targets = []
                        pos = 0
                        while True:
                            if len(response.payload) < pos + 1:
                                break
                            target_id, location_type_num, target_name_len = struct.unpack('BBB', response.payload[pos:pos + 3])
                            location_type = DatalogLocation.LocationType(location_type_num)
                            pos += 3
                            name = response.payload[pos:pos + target_name_len].decode('ascii')
                            pos += target_name_len
                            targets.append(DatalogLocation(target_id, location_type, name))

                        data['targets'] = targets
                    elif subfn == cmd.DatalogControl.Subfunction.GetBufferSize:
                        data = cast(protocol_typing.Response.DatalogControl.GetBufferSize, data)
                        data['size'], = struct.unpack('>L', response.payload[0:4])

                    elif subfn == cmd.DatalogControl.Subfunction.GetLogStatus:
                        data = cast(protocol_typing.Response.DatalogControl.GetLogStatus, data)
                        data['status'] = LogStatus(int(response.payload[0]))

                    elif subfn == cmd.DatalogControl.Subfunction.ArmLog:
                        data = cast(protocol_typing.Response.DatalogControl.ArmLog, data)
                        data['record_id'], = struct.unpack('>H', response.payload)

                    elif subfn == cmd.DatalogControl.Subfunction.ConfigureDatalog:
                        data = cast(protocol_typing.Response.DatalogControl.ConfigureDatalog, data)
                        data['record_id'], = struct.unpack('>H', response.payload)

                    elif subfn == cmd.DatalogControl.Subfunction.ReadRecordings:
                        data = cast(protocol_typing.Response.DatalogControl.ReadRecordings, data)
                        data['record_id'], = struct.unpack('>H', response.payload[0:2])
                        data['data'] = response.payload[2:]

                    elif subfn == cmd.DatalogControl.Subfunction.ListRecordings:
                        data = cast(protocol_typing.Response.DatalogControl.ListRecordings, data)
                        if len(response.payload) % 5 != 0:
                            raise Exception('Incomplete payload')
                        nrecords = int(len(response.payload) / 5)
                        data['recordings'] = []
                        pos = 0
                        for i in range(nrecords):
                            (record_id, location_type_num, size) = struct.unpack('>HBH', response.payload[pos:pos + 5])
                            location_type = DatalogLocation.LocationType(location_type_num)
                            pos += 5
                            record = RecordInfo(record_id, location_type_num, size)
                            data['recordings'].append(record)

                    elif subfn == cmd.DatalogControl.Subfunction.GetSamplingRates:
                        data = cast(protocol_typing.Response.DatalogControl.GetSamplingRates, data)
                        if len(response.payload) % 4 != 0:
                            raise Exception('Incomplete payload')

                        nrates = int(len(response.payload) / 4)
                        data['sampling_rates'] = list(struct.unpack('>' + 'f' * nrates, response.payload))

                elif response.command == cmd.CommControl:
                    subfn = cmd.CommControl.Subfunction(response.subfn)

                    if subfn == cmd.CommControl.Subfunction.Discover:
                        data = cast(protocol_typing.Response.CommControl.Discover, data)
                        firmware_id_size = 16
                        if len(response.payload) < 1 + 1 + firmware_id_size + 1:    # proto_maj, proto_min + firmware_id + name_length
                            raise Exception('Incomplete payload.')

                        data['protocol_major'] = int(response.payload[0])
                        data['protocol_minor'] = int(response.payload[1])
                        data['firmware_id'] = response.payload[2:2 + firmware_id_size]
                        display_name_length = int(response.payload[2 + firmware_id_size])
                        name_position = 1 + 1 + firmware_id_size + 1
                        if len(response.payload) < name_position + display_name_length:
                            raise Exception('Display name is incomplete according to length provided')

                        data['display_name'] = response.payload[name_position:name_position + display_name_length].decode('utf8')

                    elif subfn == cmd.CommControl.Subfunction.Heartbeat:
                        data = cast(protocol_typing.Response.CommControl.Heartbeat, data)
                        data['session_id'], data['challenge_response'] = struct.unpack('>LH', response.payload[0:6])

                    elif subfn == cmd.CommControl.Subfunction.GetParams:
                        data = cast(protocol_typing.Response.CommControl.GetParams, data)
                        (data['max_rx_data_size'],
                            data['max_tx_data_size'],
                            data['max_bitrate_bps'],
                            data['heartbeat_timeout_us'],
                            data['rx_timeout_us'],
                            data['address_size_byte']
                         ) = struct.unpack('>HHLLLB', response.payload[0:17])

                    elif subfn == cmd.CommControl.Subfunction.Connect:
                        data = cast(protocol_typing.Response.CommControl.Connect, data)
                        data['magic'] = response.payload[0:4]
                        data['session_id'], = struct.unpack('>L', response.payload[4:8])
                
            except Exception as e:
                self.logger.error(str(e))
                self.logger.debug(traceback.format_exc())
                valid = False
                raise

        if not valid:
            raise InvalidResponseException(response, 'Could not properly decode response payload.')

        return data
