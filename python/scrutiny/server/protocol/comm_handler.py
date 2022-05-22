#    comm_handler.py
#        The CommHandler task is to convert Requests and Response from or to a stream of bytes.
#        
#        This class manage send requests, wait for response, indicates if a response timeout
#        occured and decodes bytes.
#        It manages the low level part of the communication protocol with the device
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

from queue import Queue
from scrutiny.server.protocol import Request, Response
from scrutiny.server.tools import Timer
from enum import Enum
from copy import copy
import logging
import struct
from binascii import hexlify
import time
from scrutiny.server.tools import Throttler
from scrutiny.server.device.links import AbstractLink

from typing import Union, TypedDict, Optional


class CommHandler:
    """
    This class is the bridge between the application and the communication channel with the device.
    It exchange bytes with the device and exchanges request/response with the upper layer.
    The link object abstract the communication channel.
    """

    class Params(TypedDict):
        response_timeout: int

    class RxData:
        __slots__ = ('data_buffer', 'length', 'length_bytes_received')

        data_buffer: bytes
        length: int
        length_bytes_received: int

        def __init__(self):
            self.clear()

        def clear(self):
            self.length = None
            self.length_bytes_received = 0
            self.data_buffer = bytes()

    DEFAULT_PARAMS: "CommHandler.Params" = {
        'response_timeout': 1
    }

    active_request: Optional[Request]
    received_response: Optional[Response]
    link: Optional[AbstractLink]
    params: "CommHandler.Params"
    response_timer: Timer
    rx_data: "CommHandler.RxData"
    logger: logging.Logger
    opened: bool
    throttler: Throttler
    rx_bitcount: int
    tx_bitcount: int
    bitcount_time: float
    timed_out: bool
    pending_request: Optional[Request]

    def __init__(self, params={}):
        self.active_request = None      # Contains the request object that has been sent to the device. When None, no request sent and we are standby
        self.received_response = None   # Indicates that a response has been received.
        self.link = None                # Abstracted communication channel that implements  initialize, destroy, write, read
        self.params = copy(self.DEFAULT_PARAMS)
        self.params.update(params)

        self.response_timer = Timer(self.params['response_timeout'])    # Timer for response timeout management
        self.rx_data = self.RxData()    # Contains the response data while we read it.
        self.logger = logging.getLogger(self.__class__.__name__)
        self.opened = False     # True when communication channel is active and working.
        self.reset_bitrate_monitor()
        self.throttler = Throttler()

    def enable_throttling(self, bitrate: float) -> None:
        self.throttler.set_bitrate(bitrate)
        self.throttler.enable()

    def disable_throttling(self) -> None:
        self.throttler.disable()

    def is_throttling_enabled(self) -> bool:
        return self.throttler.is_enabled()

    def get_throttling_bitrate(self) -> float:
        return self.throttler.get_bitrate()

    def reset_bitrate_monitor(self) -> None:
        self.rx_bitcount = 0
        self.tx_bitcount = 0
        self.bitcount_time = time.time()

    def get_link(self) -> Optional[AbstractLink]:
        return self.link

    def open(self, link: AbstractLink) -> None:
        """
            Try to open the communication channel with the device.
        """
        self.link = link
        self.reset()
        try:
            self.link.initialize()
            self.opened = True
        except Exception as e:
            self.logger.error("Cannot connect to device. " + str(e))
            self.opened = False

    def close(self) -> None:
        """
            Close the communication channel with the device
        """
        if self.link is not None:
            self.link.destroy()
            self.link = None
        self.reset()
        self.opened = False

    def is_open(self) -> bool:
        return self.opened

    def process(self) -> None:
        """
        To be called periodically
        """
        if self.link is None:
            self.reset()
            return

        self.link.process()  # Process the link handling
        self.throttler.process()
        self.process_rx()   # Treat response reception
        self.process_tx()   # Handle throttling

    def process_rx(self) -> None:
        if self.link is None:
            self.reset()
            return

        # If we haven't got a response or we know we won't get one. Mark the request as timed out
        if self.waiting_response() and (self.response_timer.is_timed_out() or not self.link.operational()):
            self.reset_rx()
            self.timed_out = True

        data: Optional[bytes] = self.link.read()
        if data is None or len(data) == 0:
            return  # No data, exit.

        datasize_bits = len(data) * 8
        self.throttler.consume_bandwidth(datasize_bits)
        self.rx_bitcount += datasize_bits
        self.logger.debug('Received : %s' % (hexlify(data).decode('ascii')))

        if self.response_available() or not self.waiting_response():
            self.logger.debug('Received unwanted data: ' + hexlify(data).decode('ascii'))
            return  # Purposely discard data if we are not expecting any

        self.rx_data.data_buffer += data    # Add data to receive buffer

        if len(self.rx_data.data_buffer) >= 5:  # We have a valid command,subcommand, code and length (16btis)
            if self.rx_data.length is None:
                self.rx_data.length, = struct.unpack('>H', self.rx_data.data_buffer[3:5])   # Read the data length

        if self.rx_data.length is not None:  # We already received a valid header
            expected_bytes_count = self.rx_data.length + 9  # payload + header (5 bytes), CRC (4bytes)
            if len(self.rx_data.data_buffer) >= expected_bytes_count:
                self.rx_data.data_buffer = self.rx_data.data_buffer[0:expected_bytes_count]  # Remove extra bytes

                # We have enough data, try to decode the response and validate the CRC.
                try:
                    self.received_response = Response.from_bytes(self.rx_data.data_buffer)  # CRC validation is done here

                    # Decoding did not raised an exception, we have a valid payload!
                    self.logger.debug("Received Response %s" % self.received_response)
                    self.rx_data.clear()        # Empty the receive buffer
                    self.response_timer.stop()  # Timeout timer can be stop
                    if self.active_request is not None:  # Just to please mypy
                        # Validate that the response match the request
                        if self.received_response.command != self.active_request.command:
                            raise Exception("Unexpected Response command ID : %s" % str(self.received_response))
                        if self.received_response.subfn != self.active_request.subfn:
                            raise Exception("Unexpected Response subfunction : %s" % str(self.received_response))
                    else:
                        # Should never happen. waiting_response() is checked above
                        raise Exception('Got a response while having no request in process')

                    # Here, everything went fine. The application can now send a new request or read the received response.
                except Exception as e:
                    self.logger.error("Received malformed message. " + str(e))
                    self.reset_rx()

    def process_tx(self, newrequest: bool = False) -> None:
        if self.link is None:
            self.reset()
            return

        if self.pending_request is not None:
            approx_delta_bandwidth = (self.pending_request.size() + self.pending_request.get_expected_response_size()) * 8;
            if self.throttler.allowed(approx_delta_bandwidth):
                self.active_request = self.pending_request
                self.pending_request = None
                data = self.active_request.to_bytes()
                self.logger.debug("Sending request %s" % self.active_request)
                self.logger.debug("Sending : %s" % (hexlify(data).decode('ascii')))
                datasize_bits = len(data) * 8
                self.tx_bitcount += datasize_bits
                self.throttler.consume_bandwidth(datasize_bits)
                self.link.write(data)
                self.response_timer.start()
            elif not self.throttler.possible(approx_delta_bandwidth):
                self.logger.critical("Throttling doesn't allow to send request. Dropping %s" % self.pending_request)
                self.pending_request = None
            else:
                if newrequest:  # Not sent right away
                    self.logger.debug('Received request to send. Waiting because of throttling. %s' % self.pending_request)

    def response_available(self) -> bool:
        return (self.received_response is not None)

    def has_timed_out(self) -> bool:
        return self.timed_out

    def clear_timeout(self) -> None:
        self.timed_out = False

    def get_response(self) -> Response:
        """
        Return the response received for the active request
        """
        if self.received_response is None:
            raise Exception('No response to read')

        response = self.received_response   # Make a copy of the response to return before clearing everything
        self.reset_rx()  # Since user read the response, it has been acknowledged. Make sure response_available() return False

        return response

    def reset_rx(self) -> None:
        # Make sure we can send a new request.
        # Also clear the received resposne so that response_available() return False
        self.active_request = None
        self.pending_request = None
        self.received_response = None
        self.response_timer.stop()
        self.rx_data.clear()

    def send_request(self, request: Request) -> None:
        if self.waiting_response():
            raise Exception('Waiting for a response')

        self.pending_request = request
        self.received_response = None
        self.timed_out = False
        self.process_tx(newrequest=True)

    def waiting_response(self) -> bool:
        # We are waiting response if a request is active, meaning it has been sent and reponse has not been acknowledge by the application
        return (self.active_request is not None or self.pending_request is not None)

    def reset(self) -> None:
        self.reset_rx()
        self.clear_timeout()

    def get_average_bitrate(self):
        dt = time.time() - self.bitcount_time
        return (self.rx_bitcount + self.tx_bitcount) / dt
