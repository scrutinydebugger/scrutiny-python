import time
import logging
import binascii

from scrutiny.server.protocol import ResponseCode

class DeviceSearcher:
    DISCOVER_INTERVAL = 0.5
    DEVICE_GONE_DELAY = 3

    def __init__(self, protocol, dispatcher):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self.protocol = protocol
        self.reset()

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def reset(self):
        self.pending = False
        self.last_request_timestamp = None
        self.found_device_timestamp = time.time()
        self.started = False
        self.found_device = None

    def get_found_device(self):
        return self.found_device

    def get_found_device_ascii(self):
        if self.found_device is not None:
            return binascii.hexlify(self.found_device).decode('ascii')

    def process(self):
        if not self.started:
            self.reset()
            return 

        if time.time() - self.found_device_timestamp > self.DEVICE_GONE_DELAY:
            self.found_device = None

        if self.pending == False:
            if self.last_request_timestamp is None or (time.time() - self.last_request_timestamp > self.DISCOVER_INTERVAL):
                self.logger.debug('Registering a Discover request')
                self.dispatcher.register_request(
                    request = self.protocol.comm_discover(),
                    success_callback = self.success_callback,
                    failure_callback = self.failure_callback
                    )
                self.pending=True
                self.last_request_timestamp = time.time()

    def success_callback(self, request, response, response_data, params=None):
        self.logger.debug("Success callback. Request=%s. Response=%s, Params=%s" % (request, response, params))

        if response.code == ResponseCode.OK:
            self.logger.debug("Response data =%s" % (response_data))

            self.found_device_timestamp = time.time()
            self.found_device = response_data['firmware_id']

        self.completed()

    def failure_callback(self, request, params=None):
        self.logger.debug("Failure callback. Request=%s. Params=%s" % (request, params))
        self.found_device = None
        self.completed()

    def completed(self):
        self.pending = False     