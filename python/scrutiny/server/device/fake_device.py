import threading
import logging
import time
import struct

from scrutiny.server.protocol import Request, Response, Protocol
import scrutiny.server.protocol.commands as cmd
from scrutiny.server.server_tools import Timer


class FakeDevice:
    def __init__(self, to_device_queue, to_server_queue, data_source, software_id=None):
        self.to_device_queue = to_device_queue
        self.to_server_queue = to_server_queue
        self.logger = logging.getLogger(__class__.__name__)
        self.stop_requested = False
        self.request_to_fn_map = {
            cmd.GetInfo         : self.process_get_info,
            cmd.MemoryControl   : self.process_memory_control,
            cmd.CommControl     : self.process_comm_control
        }
        self.data_source = data_source
        if software_id is None:
            software_id = 'fakeSoftwareId'.encode('ascii')
        elif not isinstance(software_id, bytes):
            raise ValueError('software_id must be a bytes object')
        self.software_id = software_id    
        self.protocol = Protocol(1,0)
        self.comm_timer = Timer(None)   # Default never timeout
        self.comm_established = False

    
    def run(self):
        while not self.stop_requested:
            if not self.to_device_queue.empty():
                data = self.to_device_queue.get()
                try:
                    req = Request.from_bytes(data)
                    self.logger.debug('Got request : %s' % (req.__repr__()))
                    response = self.process_request(req)
                    if response:
                        self.logger.debug('Enqueuing a response : %s' % (response.__repr__()))
                        self.to_server_queue.put(response.to_bytes())
                except Exception as e:
                    self.logger.error(str(e))

            if self.comm_timer.is_stopped() or self.comm_timer.is_timed_out():
                self.comm_established = False

            time.sleep(0.01)

    def start(self):
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def stop(self):
        self.stop_requested = True
        self.thread.join()

    def process_request(self, request):
        if self.comm_established == False:
            if request.command != cmd.CommControl:
                return None

        if request.command in self.request_to_fn_map:
            return self.request_to_fn_map[request.command](request)
        else:
            return Response(request.command, request.subfn, Response.ResponseCode.InvalidRequest)

    def get_software_id(self):
        return self.software_id


    def establish_comm(self):
        self.comm_established = True
        self.comm_timer.start()

    def break_comm(self):
        self.comm_established = False
        self.comm_timer.stop()

    def set_comm_timeout(self, timeout):
        self.comm_timer.set_timeout(timeout)

#   =====   Requests handlers =======

    def process_get_info(self, req):
        response =  None
        code = Response.ResponseCode.OK
        self.logger.info("Processing GetInfo request")
        try:
            subfn = cmd.GetInfo.Subfunction(req.subfn)
        except Exception as e:
            self.logger.debug(str(e))
            return Response(req.command, req.subfn, Response.ResponseCode.InvalidRequest)

        if subfn == cmd.GetInfo.Subfunction.GetProtocolVersion:
            response = self.protocol.respond_protocol_version()
        elif subfn == cmd.GetInfo.Subfunction.GetSoftwareId:
            response = self.protocol.respond_software_id(self.get_software_id())
        elif subfn == cmd.GetInfo.Subfunction.GetSupportedFeatures:
            response =  self.protocol.respond_supported_features(memory_read = True, memory_write = True, datalog_acquire = True, user_command = True)
        else:
            code = Response.ResponseCode.InvalidRequest

        if response is None:
            response = Response(req.command, req.subfn, code)

        return response
        

    def process_memory_control(self, req):
        response =  None
        self.logger.info("Processing MemoryControl request")
        code = Response.ResponseCode.OK

        try:
            req_data = self.protocol.parse_request(req)
            subfn = cmd.MemoryControl.Subfunction(req.subfn)
        except Exception as e:
            self.logger.debug(str(e))
            return Response(req.command, req.subfn, Response.ResponseCode.InvalidRequest)

        if subfn == cmd.MemoryControl.Subfunction.Read:
            try:
                data = self.data_source.read(req_data['address'], req_data['length'])
                response = self.protocol.respond_read_memory_block(req_data['address'], data)
            except Exception as e:
                code = Response.ResponseCode.FailureToProceed;
                self.logger.debug(str(e))
       
        elif subfn == cmd.MemoryControl.Subfunction.Write:
            try:
                self.data_source.write(req_data['address'], req_data['data'])
                response = self.protocol.respond_write_memory_block(req_data['address'], len(req_data['data']))
            except Exception as e:
                self.logger.debug(str(e))
                code =  Response.ResponseCode.FailureToProceed;
        else:
            code = Response.ResponseCode.InvalidRequest
    
        if response is None:
            response = Response(req.command, req.subfn, code)

        return response

    def process_comm_control(self, req):
        response =  None
        self.logger.info("Processing CommControl request")
        code = Response.ResponseCode.OK

        try:
            req_data = self.protocol.parse_request(req)
            subfn = cmd.CommControl.Subfunction(req.subfn)
        except Exception as e:
            self.logger.debug(str(e))
            return Response(req.command, req.subfn, Response.ResponseCode.InvalidRequest)

        if subfn == cmd.CommControl.Subfunction.Heartbeat:
            self.comm_timer.start()
            response = self.protocol.respond_comm_heartbeat(req_data['challenge'])
        else:
            code = Response.ResponseCode.InvalidRequest

        if response is None:
            response = Response(req.command, req.subfn, code)

        return response
