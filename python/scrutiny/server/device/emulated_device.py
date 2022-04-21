#    emulated_device.py
#        Emulate a device that is compiled with the C++ lib.
#        For unit testing purpose
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

from scrutiny.server.device.links.dummy_link import DummyLink, ThreadSafeDummyLink
import threading
import time
import logging
from scrutiny.server.protocol import Protocol, Request, Response, ResponseCode
import scrutiny.server.protocol.commands as cmd
import random
import traceback


class RequestLogRecord:
    __slots__ = ('request', 'response')

    def __init__(self, request, response):
        self.request = request
        self.response = response


class EmulatedDevice:
    def __init__(self, link):
        if not isinstance(link, DummyLink) and not isinstance(link, ThreadSafeDummyLink):
            raise ValueError('EmulatedDevice expects a DummyLink object')
        self.logger = logging.getLogger(self.__class__.__name__)
        self.link = link    # Preopened link.
        self.firmware_id = bytes([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15])
        self.request_history = []
        self.protocol = Protocol(1, 0)

        self.comm_enabled = True
        self.connected = False
        self.request_shutdown = False
        self.thread_started_event = threading.Event()
        self.thread = None

        self.max_rx_data_size = 128        # Rx buffer size max. Server should make sure the request won't overflow
        self.max_tx_data_size = 128        # Tx buffer size max. Server should make sure the response won't overflow
        self.max_bitrate_bps = 100000    # Maximum bitrate supported by the device. Will gently ask the server to not go faster than that
        self.heartbeat_timeout_us = 3000000   # Will destroy session if no heartbeat is received at this rate (microseconds)
        self.rx_timeout_us = 50000     # For byte chunk reassembly (microseconds)
        self.address_size_bits = 32

        self.supported_features = {
            'memory_read': False,
            'memory_write': False,
            'datalog_acquire': False,
            'user_command': False
        }

        self.forbidden_regions = [
            {'start': 0x100, 'end': 0x1FF},
            {'start': 0x1000, 'end': 0x100FF}]

        self.readonly_regions = [
            {'start': 0x200, 'end': 0x2FF},
            {'start': 0x800, 'end': 0x8FF},
            {'start': 0x900, 'end': 0x9FF}]

    def thread_task(self):
        self.thread_started_event.set()
        while not self.request_shutdown:
            request = None
            try:
                request = self.read()
            except Exception as e:
                self.logger.error('Error decoding request. %s' % str(e))

            if request is not None:
                response = None
                self.logger.debug('Received a request : %s' % request)
                try:
                    response = self.process_request(request)
                    if response is not None:
                        self.logger.debug('Responding %s' % response)
                        self.send(response)
                except Exception as e:
                    self.logger.error('Exception while processing Request %s. Error is : %s' % (str(request), str(e)))
                    self.logger.debug(traceback.format_exc())

                self.request_history.append(RequestLogRecord(request=request, response=response))

            time.sleep(0.01)

    def process_request(self, req):
        response = None
        if req.size() > self.max_rx_data_size:
            self.logger.error("Request doesn't fit buffer. Dropping %s" % req)
            return  # drop

        data = self.protocol.parse_request(req)
        if data['valid'] == False:
            self.logger.error('Invalid request data')
            return

        if not self.connected:
            # We only respond to DISCOVER and CONNECT request while not session is active
            must_process = req.command == cmd.CommControl and (
                req.subfn == cmd.CommControl.Subfunction.Discover.value or req.subfn == cmd.CommControl.Subfunction.Connect.value)
            if not must_process:
                self.logger.warning('Received a request while no session was active. %s' % req)
                return

        if req.command == cmd.CommControl:
            response = self.process_comm_control(req, data)
        elif req.command == cmd.GetInfo:
            response = self.process_get_info(req, data)
        elif req.command == cmd.DummyCommand:
            response = self.process_dummy_cmd(req, data)
        else:
            self.logger.error('Unsupported command : %s' % str(req.command.__name__))

        return response

    # ===== [CommControl] ======
    def process_comm_control(self, req, data):
        response = None
        subfunction = cmd.CommControl.Subfunction(req.subfn)
        if subfunction == cmd.CommControl.Subfunction.Discover:
            if data['magic'] == cmd.CommControl.DISCOVER_MAGIC:
                response = self.protocol.respond_comm_discover(self.firmware_id, 'EmulatedDevice')
            else:
                self.logger.error('Received as Discover request with invalid payload')

        elif subfunction == cmd.CommControl.Subfunction.Connect:
            if data['magic'] == cmd.CommControl.CONNECT_MAGIC:
                if not self.connected:
                    self.initiate_session()
                    response = self.protocol.respond_comm_connect(self.session_id)
                else:
                    response = Response(cmd.CommControl, subfunction, ResponseCode.Busy)
            else:
                self.logger.error('Received as Connect request with invalid payload')

        elif subfunction == cmd.CommControl.Subfunction.Heartbeat:
            if data['session_id'] == self.session_id:
                challenge_response = self.protocol.heartbeat_expected_challenge_response(data['challenge'])
                response = self.protocol.respond_comm_heartbeat(self.session_id, challenge_response)
            else:
                self.logger.warning('Received a Heartbeat request for session ID 0x%08X, but my active session ID is 0x%08X' %
                                    (data['session_id'], self.session_id))
                response = Response(cmd.CommControl, subfunction, ResponseCode.InvalidRequest)

        elif subfunction == cmd.CommControl.Subfunction.Disconnect:
            if data['session_id'] == self.session_id:
                self.destroy_session()
                response = self.protocol.respond_comm_disconnect()
            else:
                self.logger.warning('Received a Disconnect request for session ID 0x%08X, but my active session ID is 0x%08X' %
                                    (data['session_id'], self.session_id))
                response = Response(cmd.CommControl, subfunction, ResponseCode.InvalidRequest)

        elif subfunction == cmd.CommControl.Subfunction.GetParams:
            response = self.protocol.respond_comm_get_params(
                max_rx_data_size=self.max_rx_data_size,
                max_tx_data_size=self.max_tx_data_size,
                max_bitrate_bps=self.max_bitrate_bps,
                heartbeat_timeout_us=self.heartbeat_timeout_us,
                rx_timeout_us=self.rx_timeout_us,
                address_size_byte=int(self.address_size_bits / 8)
            )

        else:
            self.logger.error('Unsupported subfunction %s for command : %s' % (subfunction, req.command.__name__))

        return response

    # ===== [GetInfo] ======
    def process_get_info(self, req, data):
        response = None
        subfunction = cmd.GetInfo.Subfunction(req.subfn)
        if subfunction == cmd.GetInfo.Subfunction.GetProtocolVersion:
            response = self.protocol.respond_protocol_version(self.protocol.version_major, self.protocol.version_minor)

        elif subfunction == cmd.GetInfo.Subfunction.GetSupportedFeatures:
            response = self.protocol.respond_supported_features(**self.supported_features)

        elif subfunction == cmd.GetInfo.Subfunction.GetSpecialMemoryRegionCount:
            response = self.protocol.respond_special_memory_region_count(len(self.readonly_regions), len(self.forbidden_regions))

        elif subfunction == cmd.GetInfo.Subfunction.GetSpecialMemoryRegionLocation:
            if data['region_type'] == cmd.GetInfo.MemoryRangeType.ReadOnly:
                region_list = self.readonly_regions
            elif data['region_type'] == cmd.GetInfo.MemoryRangeType.Forbidden:
                region_list = self.forbidden_regions
            else:
                return Response(req.command, subfunction, ResponseCode.InvalidRequest)

            if data['region_index'] >= len(region_list):
                return Response(req.command, subfunction, ResponseCode.Overflow)

            region = region_list[data['region_index']]
            response = self.protocol.respond_special_memory_region_location(data['region_type'], data['region_index'], region['start'], region['end'])

        else:
            self.logger.error('Unsupported subfunction "%s" for command : "%s"' % (subfunction, req.command.__name__))

        return response

    def process_dummy_cmd(self, req, data):
        return Response(cmd.DummyCommand, subfn=req.subfn, code=ResponseCode.OK, payload=b'\xAA' * 32)

    def start(self):
        self.logger.debug('Starting thread')
        self.request_shutdown = False
        self.thread_started_event.clear()
        self.thread = threading.Thread(target=self.thread_task)
        self.thread.start()
        self.thread_started_event.wait()
        self.logger.debug('Thread started')

    def stop(self):
        if self.thread is not None:
            self.logger.debug('Stopping thread')
            self.request_shutdown = True
            self.thread.join()
            self.logger.debug('Thread stopped')
            self.thread = None

    def initiate_session(self):
        self.session_id = random.randrange(0, 0xFFFFFFFF)
        self.connected = True
        self.logger.info('Initiating session. SessionID = 0x%08x', self.session_id)

    def destroy_session(self):
        self.logger.info('Destroying session. SessionID = 0x%08x', self.session_id)
        self.session_id = None
        self.connected = False

    def get_firmware_id(self):
        return self.firmware_id

    def is_connected(self):
        return self.connected

    def force_connect(self):
        self.connected = True

    def force_disconnect(self):
        self.connected = False

    def disable_comm(self):
        self.comm_enabled = False

    def enable_comm(self):
        self.comm_enabled = True

    def clear_request_history(self):
        self.request_history = []

    def get_request_history(self):
        return self.request_history

    def send(self, response):
        if self.comm_enabled:
            self.link.emulate_device_write(response.to_bytes())

    def read(self):
        data = self.link.emulate_device_read()
        if len(data) > 0 and self.comm_enabled:
            return Request.from_bytes(data)
