#    device_searcher.py
#        Once enbled, generates DISCOVER requests to find a device at the other end of the
#        communication link.
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import time
import logging
import binascii

from scrutiny.server.protocol import *
from scrutiny.server.device.device_info import DeviceInfo
from scrutiny.server.device.request_dispatcher import RequestDispatcher, SuccessCallback, FailureCallback

from typing import Optional, Tuple, Any


class DeviceSearcher:
    logger: logging.Logger
    dispatcher: RequestDispatcher
    protocol: Protocol
    priority: int
    pending: bool
    last_request_timestamp: Optional[float]
    found_device_timestamp: float
    started: bool
    found_device: Optional[ResponseData]

    DISCOVER_INTERVAL: float = 0.5
    DEVICE_GONE_DELAY: float = 3

    def __init__(self, protocol: Protocol, dispatcher: RequestDispatcher, priority: int):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self.protocol = protocol
        self.priority = priority
        self.reset()

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False

    def reset(self) -> None:
        self.pending = False
        self.last_request_timestamp = None
        self.found_device_timestamp = time.time()
        self.started = False
        self.found_device = None

    def device_found(self) -> bool:
        return self.found_device is not None

    def get_device_firmware_id(self) -> Optional[bytes]:
        if self.found_device is not None:
            return self.found_device['firmware_id']
        return None

    def get_device_firmware_id_ascii(self) -> Optional[str]:
        firmware_id = self.get_device_firmware_id()
        if firmware_id is not None:
            return binascii.hexlify(firmware_id).decode('ascii')
        return None

    def get_device_display_name(self) -> Optional[str]:
        if self.found_device is not None:
            return self.found_device['display_name']
        return None

    def get_device_protocol_version(self) -> Optional[Tuple[int, int]]:
        if self.found_device is not None:
            return (self.found_device['protocol_major'], self.found_device['protocol_minor'])
        return None

    def process(self) -> None:
        if not self.started:
            self.reset()
            return

        if time.time() - self.found_device_timestamp > self.DEVICE_GONE_DELAY:
            self.found_device = None

        if self.pending == False:
            if self.last_request_timestamp is None or (time.time() - self.last_request_timestamp > self.DISCOVER_INTERVAL):
                self.logger.debug('Registering a Discover request')
                self.dispatcher.register_request(
                    request=self.protocol.comm_discover(),
                    success_callback=SuccessCallback(self.success_callback),
                    failure_callback=FailureCallback(self.failure_callback),
                    priority=self.priority
                )
                self.pending = True
                self.last_request_timestamp = time.time()

    def success_callback(self, request: Request, response: Response, params: Any = None):
        self.logger.debug("Success callback. Request=%s. Response Code=%s, Params=%s" % (request, response.code, params))

        if response.code == ResponseCode.OK:
            response_data = self.protocol.parse_response(response)
            if response_data['valid']:
                self.found_device_timestamp = time.time()
                self.found_device = response_data
            else:
                self.logger.error('Discover request got a response with invalid data.')
                self.found_device = None
        else:
            self.logger.error('Discover request got Nacked. %s' % response.code)
            self.found_device = None

        self.completed()

    def failure_callback(self, request: Request, params: Any = None):
        self.logger.debug("Failure callback. Request=%s. Params=%s" % (request, params))
        self.found_device = None
        self.completed()

    def completed(self):
        self.pending = False
