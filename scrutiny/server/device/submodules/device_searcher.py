#    device_searcher.py
#        Once enabled, generates DISCOVER requests to find a device at the other end of the
#        communication link.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import time
import logging
import binascii
import traceback

from scrutiny.server.protocol import *
import scrutiny.server.protocol.typing as protocol_typing
from scrutiny.server.device.request_dispatcher import RequestDispatcher, SuccessCallback, FailureCallback

from typing import Optional, Tuple, Any, cast


class DeviceSearcher:
    """
    Generates Discover request in loop and inform the upper layers if a device has been found
    """
    logger: logging.Logger
    dispatcher: RequestDispatcher       # We put the request in here, and we know they'll go out
    protocol: Protocol                  # The actual protocol. Used to build the request payloads
    priority: int                       # Our dispatcher priority
    pending: bool                       # True when a request is out and we are waiting for a response
    last_request_timestamp: Optional[float]     # Time at which we sent the last discover request.
    found_device_timestamp: float               # Time at which we found the last device.
    started: bool       # Generates request only when started. When False, keep silent.
    found_device: Optional[protocol_typing.Response.CommControl.Discover]   # The response data of the last found device

    DISCOVER_INTERVAL: float = 0.5  # Sends a discover message every 0.5 sec
    DEVICE_GONE_DELAY: float = 3    # If no device found for 3 sec, drops any device that was previously found

    def __init__(self, protocol: Protocol, dispatcher: RequestDispatcher, priority: int):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self.protocol = protocol
        self.priority = priority
        self.reset()

    def start(self) -> None:
        """ Enable the search"""
        self.started = True

    def stop(self) -> None:
        """ Stop the search. No more request emitted and state machine will stop"""
        self.logger.debug('Stop requested')
        self.started = False

    def fully_stopped(self) -> bool:
        """Indicates that this submodule is stopped and has no pending state"""
        return self.started == False

    def reset(self) -> None:
        """ Restart the search from the beginning"""
        self.pending = False
        self.last_request_timestamp = None
        self.found_device_timestamp = time.time()
        self.started = False
        self.found_device = None

    def device_found(self) -> bool:
        """Tells if a device was found"""
        return self.found_device is not None

    def get_device_firmware_id(self) -> Optional[bytes]:
        """Get the firmware ID of the found device. None if none was found"""
        if self.found_device is not None:
            return self.found_device['firmware_id']
        return None

    def get_device_firmware_id_ascii(self) -> Optional[str]:
        """Get the firmware ID in ascii format of the found device. None if none was found"""
        firmware_id = self.get_device_firmware_id()
        if firmware_id is not None:
            return binascii.hexlify(firmware_id).decode('ascii')
        return None

    def get_device_display_name(self) -> Optional[str]:
        """Get the display name of the found device. None if none was found"""
        if self.found_device is not None:
            return self.found_device['display_name']
        return None

    def get_device_protocol_version(self) -> Optional[Tuple[int, int]]:
        """Get the protocol version of the found device. None if none was found"""
        if self.found_device is not None:
            return (self.found_device['protocol_major'], self.found_device['protocol_minor'])
        return None

    def process(self) -> None:
        """To be called periodically"""
        if not self.started:
            self.reset()
            return

        # Timeout
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

    def success_callback(self, request: Request, response: Response, params: Any = None) -> None:
        # Called by the dispatcher when a request is completed and succeeded
        self.logger.debug("Success callback. Request=%s. Response Code=%s, Params=%s" % (request, response.code, params))

        if self.started:
            if response.code == ResponseCode.OK:
                try:
                    response_data = cast(protocol_typing.Response.CommControl.Discover, self.protocol.parse_response(response))
                    self.found_device_timestamp = time.time()
                    self.found_device = response_data
                except Exception as e:
                    self.logger.error('Discover request got a response with invalid data.')
                    self.logger.debug(traceback.format_exc())
                    self.found_device = None
            else:
                self.logger.error('Discover request got Nacked. %s' % response.code)
                self.found_device = None

        self.completed()

    def failure_callback(self, request: Request, params: Any = None) -> None:
        # Called by the dispatcher when a request is completed and failed to succeed
        self.logger.debug("Failure callback. Request=%s. Params=%s" % (request, params))
        self.found_device = None
        self.completed()

    def completed(self) -> None:
        self.pending = False
