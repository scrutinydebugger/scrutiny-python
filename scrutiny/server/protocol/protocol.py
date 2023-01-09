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
from enum import Enum

from .exceptions import *
from . import commands as cmd
from . import Request, Response
from scrutiny.core.codecs import *
from scrutiny.core.basic_types import Endianness, RuntimePublishedValue
import scrutiny.server.protocol.typing as protocol_typing
import scrutiny.server.datalogging.definitions as datalogging


from typing import Union, List, Tuple, Optional, Dict, Any, cast


class Protocol:
    version_major: int
    version_minor: int
    logger: logging.Logger
    rpv_map: Dict[int, RuntimePublishedValue]

    class AddressFormat:

        nbits: int
        nbytes: int
        pack_char: str
        mask: int

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
            self.mask = int((1 << nbits) - 1)

        def get_address_size_bytes(self) -> int:
            return self.nbytes

        def get_address_size_bits(self) -> int:
            return self.nbits

        def get_pack_char(self) -> str:
            return self.pack_char

        def get_address_mask(self):
            return self.mask

        def encode_address(self, address: int) -> bytes:
            address &= self.get_address_mask()
            return struct.pack('>%s' % self.get_pack_char(), address)

        def decode_address(self, buff: bytes) -> int:
            return struct.unpack('>%s' % self.get_pack_char(), buff[0:self.get_address_size_bytes()])[0]

    def __init__(self, version_major: int = 1, version_minor: int = 0, address_size_bits: int = 32):
        self.version_major = version_major
        self.version_minor = version_minor
        self.logger = logging.getLogger(self.__class__.__name__)
        self.rpv_map = {}
        self.set_address_size_bits(address_size_bits)    # default 32 bits address

    def set_address_size_bits(self, address_size_bits: int) -> None:
        self.address_format = self.AddressFormat(nbits=address_size_bits)

    def set_address_size_bytes(self, address_size_byte: int) -> None:
        self.set_address_size_bits(address_size_byte * 8)

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

    def get_version(self) -> Tuple[int, int]:
        return (self.version_major, self.version_minor)

    def configure_rpvs(self, rpvs: List[RuntimePublishedValue]) -> None:
        self.rpv_map = {}
        for rpv in rpvs:
            self.rpv_map[rpv.id] = rpv

    def encode_address(self, address: int) -> bytes:
        return self.address_format.encode_address(address)

    def decode_address(self, buff: bytes) -> int:
        return self.address_format.decode_address(buff)

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

    def get_rpv_definition(self, start: int, count: int):
        return Request(cmd.GetInfo, cmd.GetInfo.Subfunction.GetRuntimePublishedValuesDefinition, struct.pack('>HH', start, count), response_payload_size=3 * count)

    def get_rpv_definition_req_size(self) -> int:
        return 4

    def get_rpv_definition_response_size_per_rpv(self) -> int:
        return 3

    def read_rpv_request_size_per_rpv(self) -> int:
        return 2

    def read_rpv_request_required_size(self, rpvs: List[RuntimePublishedValue]) -> int:
        return self.read_rpv_request_size_per_rpv() * len(rpvs)

    def read_rpv_response_required_size(self, rpvs: List[RuntimePublishedValue]) -> int:
        sum = 0
        for rpv in rpvs:
            sum += 2 + rpv.datatype.get_size_byte()
        return sum

    def write_rpv_request_required_size(self, rpvs: List[RuntimePublishedValue]) -> int:
        sum = 0
        for rpv in rpvs:
            sum += 2 + rpv.datatype.get_size_byte()
        return sum

    def write_rpv_response_required_size(self, rpvs: List[RuntimePublishedValue]) -> int:
        return self.get_rpv_definition_response_size_per_rpv() * len(rpvs)

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

    def read_runtime_published_values(self, ids: Union[int, List[int]]):
        if not isinstance(ids, List):
            ids = [ids]

        expected_response_size = 0
        for id in ids:
            if id not in self.rpv_map:
                raise Exception('Unknown RuntimePublishedValue ID 0x%x' % id)
            rpv = self.rpv_map[id]
            typesize = rpv.datatype.get_size_byte()
            assert typesize is not None
            expected_response_size += 2 + typesize

        nbids = len(ids)
        data = struct.pack('>' + 'H' * nbids, *ids)
        return Request(cmd.MemoryControl, cmd.MemoryControl.Subfunction.ReadRPV, data, response_payload_size=expected_response_size)

    def write_runtime_published_values(self, values: Union[List[Tuple[int, Encodable]], Tuple[int, Encodable]]):
        if not isinstance(values, list):
            values = [values]

        data = bytes()
        for id, val in values:
            if id not in self.rpv_map:
                raise Exception('Unknown RuntimePublishedValue ID %s' % id)
            rpv = self.rpv_map[id]
            codec = Codecs.get(rpv.datatype, Endianness.Big)
            data += struct.pack('>H', id)
            data += codec.encode(val)

        return Request(cmd.MemoryControl, cmd.MemoryControl.Subfunction.WriteRPV, data, response_payload_size=len(values) * 3)

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

    def datalogging_get_setup(self) -> Request:
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetSetup, response_payload_size=5)

    def datalogging_configure(self, loop_id: int, config_id: int, config: datalogging.Configuration) -> Request:
        data = struct.pack('>BHHBLBLB',
                           loop_id,
                           config_id,
                           config.decimation,
                           int(round(config.probe_location * 255)),
                           int(round(config.timeout * 1e7)),
                           config.trigger_condition.value,
                           int(round(config.trigger_hold_time * 1e7)),
                           len(config.trigger_condition_operands)
                           )

        for operand in config.trigger_condition_operands:
            operand_type = operand.get_type()
            data += struct.pack('B', operand_type.value)
            if operand_type == datalogging.OperandType.Literal:
                operand = cast(datalogging.LiteralOperand, operand)
                data += struct.pack('>f', operand.literal)
            elif operand_type == datalogging.OperandType.RPV:
                operand = cast(datalogging.RPVOperand, operand)
                data += struct.pack('>H', operand.rpv.id)
            elif operand_type == datalogging.OperandType.Var:
                operand = cast(datalogging.VarOperand, operand)
                data += struct.pack('>B', operand.var.get_type())
                data += self.encode_address(operand.var.get_address())
            elif operand_type == datalogging.OperandType.VarBit:
                operand = cast(datalogging.VarBitOperand, operand)
                data += struct.pack('>B', operand.varbit.get_type())
                data += self.encode_address(operand.varbit.get_address())
                data += struct.pack('>BB', operand.varbit.get_bitoffset(), operand.varbit.get_bitsize())
            else:
                raise ValueError("Unknown operand type")

        data += struct.pack('>B', len(config.loggable_signals))

        for signal in config.loggable_signals:
            signal_type = signal.get_type()
            data += struct.pack('>B', len(signal_type.value))

            if signal_type == datalogging.LoggableSignalType.MEMORY:
                signal = cast(datalogging.MemoryLoggableSignal, signal)
                data += self.encode_address(signal.address)
                data += struct.pack('>B', signal.size)

            elif signal_type == datalogging.LoggableSignalType.MEMORY:
                signal = cast(datalogging.RPVLoggableSignal, signal)
                data += struct.pack('>H', signal.rpv.id)

            elif signal_type == datalogging.LoggableSignalType.MEMORY:
                signal = cast(datalogging.TimeLoggableSignal, signal)
                # nothing to encode!
            else:
                raise ValueError("Unknown signal type")

        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ConfigureDatalog, response_payload_size=0)

    def datalogging_arm_trigger(self) -> Request:
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ArmTrigger, response_payload_size=0)

    def datalogging_disarm_trigger(self) -> Request:
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.DisarmTrigger, response_payload_size=0)

    def datalogging_get_status(self) -> Request:
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetStatus, response_payload_size=1)

    def datalogging_get_acquisition_metadata(self) -> Request:
        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetAcquisitionMetadata, response_payload_size=14)

    def datalogging_read_acquisition(self, data_read: int, total_size: int, tx_buffer_size: int, encoding: datalogging.Encoding) -> Request:
        payload_max_size = tx_buffer_size
        remaining_count = total_size - data_read

        if payload_max_size - 8 < 0:
            raise ValueError('Negative max payload size. tx_buffer_size=%d', (tx_buffer_size))

        if remaining_count < 0:
            raise ValueError('Negative remaining data. total_size=%d, data_read=%d', (total_size, data_read))

        expected_response_payload_size = 0
        if encoding == datalogging.Encoding.RAW:
            if remaining_count < payload_max_size - 8:    # Last block
                expected_response_payload_size = remaining_count + 8
            else:
                expected_response_payload_size = payload_max_size
        else:
            raise ValueError('Unsupported encoding')

        return Request(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ReadAcquisition, response_payload_size=expected_response_payload_size)

    def user_command(self, subfn: int, data: bytes = b'') -> Request:
        return Request(cmd.UserCommand, subfn, data)    # todo : response_payload_size

    def parse_request(self, req: Request) -> protocol_typing.RequestData:
        data: protocol_typing.RequestData = cast(protocol_typing.Request.Empty, {})
        subfn: Enum
        valid: bool = True

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
                    data = cast(protocol_typing.Request.MemoryControl.WriteMasked, data)
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

                    nbids = len(req.payload) // 2
                    for i in range(nbids):
                        id = struct.unpack('>H', req.payload[i * 2:i * 2 + 2])[0]
                        data['rpvs_id'].append(id)

                elif subfn == cmd.MemoryControl.Subfunction.WriteRPV:
                    data = cast(protocol_typing.Request.MemoryControl.WriteRPV, data)
                    data['rpvs'] = []
                    cursor = 0

                    while cursor < len(req.payload):
                        id = struct.unpack('>H', req.payload[cursor:cursor + 2])[0]
                        cursor += 2
                        if id not in self.rpv_map:
                            raise Exception('Request requires to decode RPV with ID %s which is unknown' % id)

                        rpv = self.rpv_map[id]
                        codec = Codecs.get(rpv.datatype, Endianness.Big)
                        datasize = rpv.datatype.get_size_byte()
                        assert datasize is not None
                        value = codec.decode(req.payload[cursor:cursor + datasize])
                        cursor += datasize
                        data['rpvs'].append(dict(id=id, value=value))

            elif req.command == cmd.DatalogControl:
                subfn = cmd.DatalogControl.Subfunction(req.subfn)

                # TODO

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

    def respond_supported_features(self, memory_read: bool = False, memory_write: bool = False, datalogging: bool = False, user_command: bool = False, _64bits: bool = False) -> Response:
        bytes1 = 0
        if memory_read:
            bytes1 |= 0x80

        if memory_write:
            bytes1 |= 0x40

        if datalogging:
            bytes1 |= 0x20

        if user_command:
            bytes1 |= 0x10

        if _64bits:
            bytes1 |= 0x08

        return Response(cmd.GetInfo, cmd.GetInfo.Subfunction.GetSupportedFeatures, Response.ResponseCode.OK, bytes([bytes1]))

    def respond_special_memory_region_count(self, readonly: int, forbidden: int) -> Response:
        return Response(cmd.GetInfo, cmd.GetInfo.Subfunction.GetSpecialMemoryRegionCount, Response.ResponseCode.OK, struct.pack('BB', readonly, forbidden))

    def respond_special_memory_region_location(self, region_type: Union[cmd.GetInfo.MemoryRangeType, int], region_index: int, start: int, end: int) -> Response:
        if isinstance(region_type, cmd.GetInfo.MemoryRangeType):
            region_type = region_type.value
        data = struct.pack('BB', region_type, region_index)
        data += self.encode_address(start) + self.encode_address(end)
        return Response(cmd.GetInfo, cmd.GetInfo.Subfunction.GetSpecialMemoryRegionLocation, Response.ResponseCode.OK, data)

    def respond_get_rpv_count(self, count: int):
        return Response(cmd.GetInfo, cmd.GetInfo.Subfunction.GetRuntimePublishedValuesCount, Response.ResponseCode.OK, struct.pack('>H', count))

    def respond_get_rpv_definition(self, rpvs: List[RuntimePublishedValue]):
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

    def respond_read_runtime_published_values(self, vals: Union[Tuple[int, Any], List[Tuple[int, Any]]]):
        if not isinstance(vals, list):
            vals = [vals]

        data = bytes()
        for id, val in vals:
            if id not in self.rpv_map:
                raise Exception('Unknown RuntimePublishedValue ID %s' % id)

            rpv = self.rpv_map[id]
            codec = Codecs.get(rpv.datatype, Endianness.Big)
            data += struct.pack('>H', id) + codec.encode(val)

        return Response(cmd.MemoryControl, cmd.MemoryControl.Subfunction.ReadRPV, Response.ResponseCode.OK, data)

    def respond_write_runtime_published_values(self, ids: Union[int, List[int]]):
        if not isinstance(ids, list):
            ids = [ids]

        data = bytes()
        for id in ids:
            if id not in self.rpv_map:
                raise Exception('Unknown RuntimePublishedValue ID %s' % id)
            rpv = self.rpv_map[id]
            data += struct.pack('>HB', id, rpv.datatype.get_size_byte())

        return Response(cmd.MemoryControl, cmd.MemoryControl.Subfunction.WriteRPV, Response.ResponseCode.OK, data)

    def respond_datalogging_get_setup(self, buffer_size: int, encoding: datalogging.Encoding) -> Response:
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetSetup, Response.ResponseCode.OK, struct.pack('>LB', buffer_size, encoding.value))

    def respond_datalogging_configure(self) -> Response:
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ConfigureDatalog, Response.ResponseCode.OK)

    def respond_datalogging_arm_trigger(self) -> Response:
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ArmTrigger, Response.ResponseCode.OK)

    def respond_datalogging_disarm_trigger(self) -> Response:
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.DisarmTrigger, Response.ResponseCode.OK)

    def respond_datalogging_get_status(self, status: Union[datalogging.DataloggerStatus, int]) -> Response:
        status = datalogging.DataloggerStatus(status)
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetStatus, Response.ResponseCode.OK, struct.pack('B', status.value))

    def respond_datalogging_get_acquisition_metadata(self, acquisition_id: int, config_id: int, nb_points: int, datasize: int, points_after_trigger: int) -> Response:
        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.GetStatus, Response.ResponseCode.OK,
                        struct.pack('>HHLLL', acquisition_id, config_id, nb_points, datasize, points_after_trigger))

    def respond_datalogging_read_acquisition(self, finished: bool, rolling_counter: int, acquisition_id: int, data: bytes, crc: Optional[int] = None) -> Response:
        if not finished and crc is not None:
            raise ValueError("CRC must be given only for the final data chunk")

        if finished and crc is None:
            raise ValueError("Missing CRC for last data chunk")

        payload = struct.pack('>BBH', finished, rolling_counter, acquisition_id) + data
        if finished:
            payload += struct.pack('>L', crc)

        return Response(cmd.DatalogControl, cmd.DatalogControl.Subfunction.ReadAcquisition, Response.ResponseCode.OK, payload)

    def respond_user_command(self, subfn: Union[int, Enum], data: bytes = b'') -> Response:
        return Response(cmd.UserCommand, subfn, Response.ResponseCode.OK, data)

    def parse_response(self, response: Response) -> protocol_typing.ResponseData:
        """Parse a response payload into a meaningful data structure"""
        data: protocol_typing.ResponseData = cast(protocol_typing.Response.Empty, {})
        subfn: Enum
        valid: bool = True

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
                        data['memory_read'] = True if (byte1 & 0x80) != 0 else False
                        data['memory_write'] = True if (byte1 & 0x40) != 0 else False
                        data['datalogging'] = True if (byte1 & 0x20) != 0 else False
                        data['user_command'] = True if (byte1 & 0x10) != 0 else False
                        data['_64bits'] = True if (byte1 & 0x08) != 0 else False

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

                        nbr_rpv = len(response.payload) // n
                        for i in range(nbr_rpv):
                            vid, typeint, = struct.unpack('>HB', response.payload[i * n + 0:i * n + n])
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
                            if len(response.payload) - cursor < 2:
                                raise Exception('Invalid data length')

                            id, = struct.unpack('>H', response.payload[cursor:cursor + 2])
                            cursor += 2
                            if id not in self.rpv_map:
                                raise Exception('Unknown RuntimePublishedValue of ID 0x%x', id)
                            rpv = self.rpv_map[id]
                            typesize = rpv.datatype.get_size_byte()
                            assert typesize is not None
                            if len(response.payload) - cursor < typesize:
                                raise Exception('Incomplete data for RPV with ID 0x%x', id)

                            codec = Codecs.get(rpv.datatype, Endianness.Big)
                            val = codec.decode(response.payload[cursor:cursor + typesize])
                            cursor += typesize
                            data['read_rpv'].append(dict(id=id, data=val))

                    elif subfn == cmd.MemoryControl.Subfunction.WriteRPV:
                        data = cast(protocol_typing.Response.MemoryControl.WriteRPV, data)
                        data['written_rpv'] = []
                        cursor = 0
                        while cursor < len(response.payload):
                            if len(response.payload) - cursor < 3:
                                raise Exception('Invalid data length')
                            id, size = struct.unpack('>HB', response.payload[cursor:cursor + 3])
                            cursor += 3
                            data['written_rpv'].append(dict(id=id, size=size))

                elif response.command == cmd.DatalogControl:
                    subfn = cmd.DatalogControl.Subfunction(response.subfn)

                    pass

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
