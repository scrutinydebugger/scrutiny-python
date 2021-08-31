import threading
import logging
import time
import struct

from scrutiny.server.protocol import Request, Response
import scrutiny.server.protocol.commands as cmd
from scrutiny.core.memdump import Memdump

class FakeDevice:
    def __init__(self, to_device_queue, to_server_queue, config='unittest'):
        self.to_device_queue = to_device_queue
        self.to_server_queue = to_server_queue
        self.logger = logging.getLogger(__class__.__name__)
        self.stop_requested = False
        self.request_to_fn_map = {
            cmd.GetInfo         : self.process_get_info,
            cmd.MemoryControl   : self.process_memory_control
        }
        self.config = config
        self.memory = self.make_memory()

    def make_memory(self):
        if self.config == 'unittest':
            memory = Memdump()
            memory.write(0, bytes(range(256)))
            memory.write(1000, bytes(range(256)))
            memory.write(2000, bytes(range(256)))
        else:
            raise NotImplementedError('Cannot make memory for this config')

        return memory

    
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

            time.sleep(0.01)

    def start(self):
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def stop(self):
        self.stop_requested = True
        self.thread.join()

    def process_request(self, request):
        if request.command in self.request_to_fn_map:
            return self.request_to_fn_map[request.command](request)
        else:
            raise NotImplementedError('This device does not support this command')

    def get_software_id(self):
        if self.config == 'unittest':
            return 'fakeDeviceSoftware'
        raise NotImplementedError('No software ID for config %s' % self.config)

    def process_get_info(self, req):
        response =  None
        self.logger.info("Processing GetInfo request")
        subfn = cmd.GetInfo.Subfunction(req.subfn)
        if subfn == cmd.GetInfo.Subfunction.GetProtocolVersion:
            data = bytes([1,0])
        elif subfn == cmd.GetInfo.Subfunction.GetSoftwareId:
            data = self.get_software_id().encode('ascii')
        elif subfn == cmd.GetInfo.Subfunction.GetSupportedFeatures:
            data = bytes([0xF0])
        else:
            raise NotImplementedError('Unsuported subfunction %d' % subfn.value)

        response = Response(cmd.GetInfo, subfn, Response.ResponseCode.OK, data)
        return response

    def process_memory_control(self, req):
        response =  None
        self.logger.info("Processing MemoryControl request")
        subfn = cmd.MemoryControl.Subfunction(req.subfn)

        addr, length = struct.unpack('>LH', req.payload)    # Todo, abstract that

        if subfn == cmd.MemoryControl.Subfunction.Read:
            data = self.memory.read(addr, length)

        response = Response(cmd.MemoryControl, subfn, Response.ResponseCode.OK, data)
        return response