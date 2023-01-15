import time
import logging
import traceback

from scrutiny.server.protocol import *
from scrutiny.server.device.request_dispatcher import RequestDispatcher, SuccessCallback, FailureCallback
import scrutiny.server.datalogging.definitions as datalogging
import scrutiny.server.protocol.typing as protocol_typing
import scrutiny.server.protocol.commands as cmd

from typing import Optional, Any, cast


class DataloggingPoller:
    class DeviceSetup:
        encoding: datalogging.Encoding
        buffer_size: int

    logger: logging.Logger
    dispatcher: RequestDispatcher       # We put the request in here, and we know they'll go out
    protocol: Protocol                  # The actual protocol. Used to build the request payloads
    request_priority: int               # Our dispatcher priority
    stop_requested: bool    # Requested to stop polling
    request_pending: bool   # True when we are waiting for a request to complete
    started: bool           # Indicate if enabled or not
    device_setup: Optional["DataloggingPoller.DeviceSetup"]
    error: bool
    enabled: bool

    def __init__(self, protocol: Protocol, dispatcher: RequestDispatcher, request_priority: int):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self.protocol = protocol
        self.request_priority = request_priority
        self.enabled = True
        self.set_standby()

    def set_standby(self):
        """Put back the datalogging poller to its startup state"""
        self.started = False
        self.stop_requested = False
        self.request_pending = False
        self.device_setup = None
        self.error = False

    def start(self) -> None:
        """ Launch polling of data """
        if self.enabled:
            self.started = True

    def stop(self) -> None:
        """ Stop the poller """
        self.stop_requested = True

    def disable(self) -> None:
        self.enabled = False
        self.stop()

    def enable(self) -> None:
        self.enabled = True

    def process(self) -> None:
        """To be called periodically to make the process move forward"""
        if not self.started:
            self.set_standby()
            return
        elif self.stop_requested and not self.request_pending:
            self.started = False
            self.set_standby()
            return
        elif self.error or not self.enabled:
            return

        if not self.request_pending:
            if self.device_setup is None:
                self.dispatch(self.protocol.datalogging_get_setup())
            else:
                pass

    def dispatch(self, req: Request) -> None:
        """Sends a request to the request dispatcher and assign the corrects completion callbacks"""
        self.dispatcher.register_request(
            req,
            SuccessCallback(self.success_callback),
            FailureCallback(self.failure_callback),
            priority=self.request_priority)
        self.request_pending = True

    def success_callback(self, request: Request, response: Response, params: Any = None) -> None:
        """Called when a request completes and succeeds"""
        self.logger.debug("Success callback. Request=%s. Response Code=%s, Params=%s" % (request, response.code, params))
        response_data: protocol_typing.ResponseData

        if response.code == ResponseCode.OK:
            try:
                subfunction = cmd.DatalogControl.Subfunction(response.subfn)
                if subfunction == cmd.DatalogControl.Subfunction.GetSetup:
                    response_data = cast(protocol_typing.Response.DatalogControl.GetSetup, self.protocol.parse_response(response))
                    self.device_setup = DataloggingPoller.DeviceSetup()
                    self.device_setup.buffer_size = response_data['buffer_size']
                    self.device_setup.encoding = response_data['encoding']

            except:
                self.error = True
                self.logger.error('Response data is invalid')
                self.logger.debug(traceback.format_exc())
        else:
            self.error = True
            self.logger.error('Request got Nacked. %s' % response.code)

        self.completed()

    def failure_callback(self, request: Request, params: Any = None) -> None:
        """Callback called by the request dispatcher when a request fails to complete"""

        self.completed()

    def completed(self) -> None:
        """ Common code between success and failure"""
        self.request_pending = False
