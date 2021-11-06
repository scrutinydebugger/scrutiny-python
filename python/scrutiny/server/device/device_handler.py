import copy
import queue
import time
import logging
from enum import Enum

from scrutiny.server.protocol.comm_handler import CommHandler
from scrutiny.server.protocol import Protocol, ResponseCode

from scrutiny.server.device.device_searcher import DeviceSearcher
from scrutiny.server.device.request_dispatcher import RequestDispatcher



class DeviceHandler:
    DEFAULT_COMM_PARAMS = {
            'response_timeout' : 1.0    # If a response take more than this delay to be received after a request is sent, drop the response.
        }

    class FsmState(Enum):
        DISCOVERING = 0
        CONNECTING = 1
        POLLING_INFO = 2

    def __init__(self, config, datastore):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self.datastore = datastore
        self.dispatcher = RequestDispatcher()
        self.protocol = Protocol(1,0)
        self.device_searcher = DeviceSearcher(self.protocol, self.dispatcher)

        comm_handler_params = copy.copy(self.DEFAULT_COMM_PARAMS)
        if 'comm_response_timeout' in self.config:
            comm_handler_params['response_timeout'] = self.config['comm_response_timeout']
        self.comm_handler = CommHandler(comm_handler_params)

       # self.fsm_state = self.FsmState.DISCOVERING
        self.active_request_record = None
        self.device_was_found = False

    def init_comm(self):
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

    def stop_comm(self):
        if self.comm_handler is not None:
            self.comm_handler.close()

    def refresh_vars(self):
        pass

    def process(self):
        self.device_searcher.start()
        self.device_searcher.process()
        if self.device_searcher.get_found_device() is not None:
            if not self.device_was_found:
                self.logger.info('Found a device - %s' % self.device_searcher.get_found_device())
        else:
            if self.device_was_found:
                self.logger.info('Device is gone')
        self.device_was_found = self.device_searcher.get_found_device() is not None

        self.handle_comm()  # Make sure request and response are being exchanged with the device
        self.do_state_machine()


    def do_state_machine(self):
        pass
       # if self.fsm_state == self.FsmState.DISCOVERING:
       #     pass



       # elif self.fsm_state == self.FsmState.CONNECTING:
       #     pass




        

    def handle_comm(self):
        self.comm_handler.process()     # Process reception

        if not self.comm_handler.is_open():
            return
        
        if self.active_request_record is None:
            record = self.dispatcher.next()
            if record is not None:
                self.active_request_record = record
                self.comm_handler.send_request(record.request)
        else:
            if self.comm_handler.has_timed_out():
                self.comm_handler.clear_timeout()
                self.active_request_record.complete(success=False)

            elif self.comm_handler.waiting_response():
                if self.comm_handler.response_available():
                    response = self.comm_handler.get_response()
                    try:
                        data = self.protocol.parse_response(response)
                        self.active_request_record.complete(success=True, response=response, response_data=data)
                    except Exception as e:
                        self.logger.error("Invalid response received. %s" % str(e))
                        self.active_request_record.complete(success=False)


            else: # should never happen
                self.comm_handler.reset() 
                self.active_request_record.complete(success=False)

            if self.active_request_record.is_completed():
                self.active_request_record = None

        self.comm_handler.process()  # Process new transmission now.

