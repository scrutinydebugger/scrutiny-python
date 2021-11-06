import time
import logging

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

    def device_found(self):
        return self.found_device

    def process(self):
        if not self.started:
            self.reset()
            return 

        if time.time() - self.found_device_timestamp > self.DEVICE_GONE_DELAY:
            self.found_device = False

        if self.pending == False:
            if self.last_request_timestamp is None or (time.time() - self.last_request_timestamp > self.DISCOVER_INTERVAL):
                self.logger.debug('Registering a Discover request')
                self.dispatcher.register_request(
                    request = self.protocol.comm_discover(0x12345678),
                    success_callback = self.success,
                    failure_callback = self.failure
                    )
                self.pending=True
                self.last_request_timestamp = time.time()

    def success(self, request, response, params=None):
        self.logger.debug("Success callback. Request=%s. Response=%s, Params=%s" % (request, response, params))

        if response.code == ResponseCode.OK:
            data = self.protocol.parse_response(response)
            self.logger.debug("Response data =%s" % (data))

            self.found_device_timestamp = time.time()
            self.found_device = True

        self.completed()

    def failure(self, request, params=None):
        self.logger.debug("Failure callback. Request=%s. Params=%s" % (request, params))
        self.completed()

    def completed(self):
        self.pending = False     