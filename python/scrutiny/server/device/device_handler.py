import copy
import queue
import time
import logging

from scrutiny.server.protocol.comm_handler import CommHandler
from scrutiny.server.protocol import Protocol

class RequestRecord:
    __slots__ = ('request', 'success_callback', 'failure_callback', 'succes_params', 'failure_params')

class RequestDispatcher:

    def __init__(self):
        self.request_queue = queue.Queue()

    def register_request(self, request, success_callback, succes_params, failure_callback, failure_params):
        record = RequestRecord()
        record.request = request
        record.success_callback = success_callback
        record.succes_params = succes_params
        record.failure_callback = failure_callback
        record.failure_params = failure_params

        self.request_queue.put(record)

    def pop(self):
        if not self.request_queue.empty():
            return self.request_queue.get()


class DeviceHandler:
    DEFAULT_COMM_PARAMS = {
            'response_timeout' : 1.0    # If a response take more than this delay to be received after a request is sent, drop the response.
        }

    def __init__(self, config, datastore):
        self.config = config
        self.datastore = datastore
        self.dispatcher = RequestDispatcher()
        self.active_request_record = None

        comm_handler_params = copy.copy(self.DEFAULT_COMM_PARAMS)

        if 'comm_response_timeout' in self.config:
            comm_handler_params['response_timeout'] = self.config['comm_response_timeout']

        self.comm_handler = CommHandler(comm_handler_params)
        self.connected = False
        self.protocol = Protocol(1,0)
        self.t1 = time.time()
        self.logger = logging.getLogger(self.__class__.__name__)

    def connect(self):
        if self.config['link_type'] == 'none':
            return

        if self.config['link_type'] == 'memdump':
            from .links.fake_device_memdump import FakeDeviceMemdump
            device_link = FakeDeviceMemdump(self.config['link_config'])
        elif self.config['link_type'] == 'subprocess':
            from .links.subprocess_link import SubprocessLink
            device_link = SubprocessLink(self.config['link_config'])
        elif self.config['link_type'] == 'udp':
            from .links.udp_link import UdpLink
            device_link = UdpLink(self.config['link_config'])
        else:
            raise ValueError('Unknown link type %s' % self.config['link_type'])

        self.comm_handler.open(device_link)
        self.connected = True

    def disconnect(self):
        if self.comm_handler is not None:
            self.comm_handler.close()
        self.connected = False

    def refresh_vars(self):
        pass

    def process(self):
        self.handle_comm()  # Make sure request and response are being exchanged with the device

        if time.time() - self.t1 > 0.5:
            self.dispatcher.register_request(
                request = self.protocol.comm_discover(0x12345678),
                success_callback = self.success_test,
                succes_params = 'SUCCESS!',
                failure_callback = self.failure_test,
                failure_params = "FAILURE!!"
                )

            self.t1 = time.time()


    def success_test(self, response, params):
        self.logger.debug("Success callback. Response=%s, Params=%s" % (response, params))

    def failure_test(self, params):
        self.logger.debug("Failure callback. Params=%s" % (params))
        

    def handle_comm(self):
        self.comm_handler.process() 

        if self.comm_handler.is_open():
            if self.active_request_record is None:
                record = self.dispatcher.pop()
                if record is not None:
                    self.active_request_record = record
                    self.comm_handler.send_request(record.request)
            else:
                if self.comm_handler.has_timed_out():
                    self.comm_handler.clear_timeout()
                    self.active_request_record.failure_callback(self.active_request_record.failure_params)
                    self.active_request_record = None
                
                elif not self.comm_handler.waiting_response(): # Should never happen.
                    self.comm_handler.reset() 
                    self.active_request_record.failure_callback(self.active_request_record.failure_params)
                    self.active_request_record = None

            if self.comm_handler.waiting_response():
                if self.comm_handler.response_available():
                    response = self.comm_handler.get_response()
                    self.active_request_record.success_callback(response, self.active_request_record.succes_params)
                    self.active_request_record = None

        self.comm_handler.process() 

