from queue import Queue
from scrutiny.server.protocol import Request, Response
from scrutiny.server.server_tools import Timer
from enum import Enum
from copy import copy
import logging
import struct
from binascii import hexlify

class CommHandler:
    class RxData:
        __slots__ = ('data_buffer', 'length', 'length_bytes_received')

        def __init__(self):
            self.clear()

        def clear(self):
            self.length = None
            self.length_bytes_received = 0
            self.data_buffer = bytes()


    DEFAULT_PARAMS = {
        'response_timeout' : 1
    }

    SUPPORTED_PARAMS = ['response_timeout']

    def __init__(self, params={}):
        self.active_request = None
        self.received_response = None
        self.to_device_queue = Queue()
        self.link = None
        self.params = copy(self.DEFAULT_PARAMS)
        self.params.update(params)

        for param in self.params:
            if param not in self.SUPPORTED_PARAMS:
                raise ValueError('Unsupported parameter %s' % param)

        self.response_timer = Timer(self.params['response_timeout'])
        self.rx_data = self.RxData() # Contains the response data while we read it.
        self.logger = logging.getLogger(self.__class__.__name__)
        self.opened = False

    def open(self, link):
        self.link = link
        self.reset()
        try:
            self.link.initialize()
            self.opened = True
        except Exception as e:
            self.logger.error("Cannot connect to device. " + str(e))
            self.opened = False

    def close(self):
        if self.link is not None:
            self.link.destroy()
            self.link = None
        self.reset()
        self.opened = False

    def is_open(self):
        return self.opened

    def process(self):
        if self.link is None:
            self.reset()
            return
        
        self.link.process()
        self.process_rx()

    def process_rx(self):
        # If we haven't got a response or we know we won't get one. Mark the request as timed out
        if self.waiting_response() and (self.response_timer.is_timed_out() or not self.link.operational()):
            self.reset_rx()
            self.timed_out = True
        
        data = self.link.read()
        if data is None or len(data) == 0:
            return

        self.logger.debug('Received : %s' % (hexlify(data).decode('ascii')))
        
        if self.response_available() or not self.waiting_response():
            self.logger.debug('Received unwanted data: ' + hexlify(data).decode('ascii'))
            return  # Purposely discard data if we are not expecting any

        self.rx_data.data_buffer += data

        if len(self.rx_data.data_buffer) >= 5:
            if self.rx_data.length is None:
                self.rx_data.length, = struct.unpack('>H', self.rx_data.data_buffer[3:5])

        if self.rx_data.length is not None:
            expected_bytes_count = self.rx_data.length + 9
            if len(self.rx_data.data_buffer) >= expected_bytes_count :
                self.rx_data.data_buffer = self.rx_data.data_buffer[0:expected_bytes_count]

                try:
                    self.received_response = Response.from_bytes(self.rx_data.data_buffer)
                    self.rx_data.clear()
                    self.response_timer.stop()
                except Exception as e:
                    self.logger.error("Received malformed message. "  + str(e))
                    self.reset_rx();

    def response_available(self):
        return (self.received_response is not None)

    def has_timed_out(self):
        return self.timed_out

    def clear_timeout(self):
        self.timed_out = False

    def get_response(self):
        if self.received_response is None:
            raise Exception('No response to read')

        response = self.received_response   # Make a copy of the response to return before clearing everything
        self.reset_rx()

        return response

    def reset_rx(self):
        self.active_request = None
        self.received_response = None
        self.response_timer.stop()
        self.rx_data.clear()

    def send_request(self, request):
        if self.active_request is not None:
            raise Exception('Waiting for a response')

        self.active_request = request
        data = request.to_bytes()
        self.logger.debug("Sending : %s" % (hexlify(data).decode('ascii')))
        self.link.write(data)
        self.response_timer.start()
        self.timed_out = False

    def waiting_response(self):
        return (self.active_request is not None)

    def reset(self):
        self.reset_rx()
        self.clear_timeout()
