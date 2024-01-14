#    comm_handler.py
#        The CommHandler task is to convert Requests and Response from or to a stream of bytes.
#        
#        This class manage send requests, wait for response, indicates if a response timeout
#        occurred and decodes bytes.
#        It manages the low level part of the communication protocol with the device
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from queue import Queue
from scrutiny.server.protocol import Request, Response
from scrutiny.tools import Timer, Throttler
from copy import copy
import logging
import struct
from binascii import hexlify
import time
from scrutiny.server.device.links import AbstractLink, LinkConfig
import traceback

from typing import TypedDict, Optional, Any, Dict, Type, cast


class CommHandler:
    """
    This class is the bridge between the application and the communication channel with the device.
    It exchange bytes with the device and exchanges request/response with the upper layer.
    The link object abstract the communication channel.

    This class also act as a Link Factory.
    """

    class Params(TypedDict):
        response_timeout: int

    class RxData:
        __slots__ = ('data_buffer', 'length', 'length_bytes_received')

        data_buffer: bytes
        length: Optional[int]
        length_bytes_received: int

        def __init__(self) -> None:
            self.clear()

        def clear(self) -> None:
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
    link_type: str

    def __init__(self, params: Dict[str, Any] = {}) -> None:
        self.active_request = None      # Contains the request object that has been sent to the device. When None, no request sent and we are standby
        self.received_response = None   # Indicates that a response has been received.
        self.link = None                # Abstracted communication channel that implements  initialize, destroy, write, read
        self.params = copy(self.DEFAULT_PARAMS)
        self.params.update(cast(CommHandler.Params, params))

        self.response_timer = Timer(self.params['response_timeout'])    # Timer for response timeout management
        self.rx_data = self.RxData()    # Contains the response data while we read it.
        self.logger = logging.getLogger(self.__class__.__name__)
        self.opened = False     # True when communication channel is active and working.
        self.reset_bitrate_monitor()
        self.throttler = Throttler()
        self.link_type = "none"

    def enable_throttling(self, bitrate: float) -> None:
        """Enable throttling on communication.
        Overall bitrate (incoming and outgoing data included) will try to be respected.
        This does not take in account the protocol overhead. Just the payload sum.
        """
        self.throttler.set_bitrate(bitrate)
        self.throttler.enable()

    def disable_throttling(self) -> None:
        """Disable throttling on communication with the device"""
        self.throttler.set_bitrate(0)
        self.throttler.disable()

    def is_throttling_enabled(self) -> bool:
        """Returns True if throttling is enabled on the device communication"""
        return self.throttler.is_enabled()

    def get_throttling_bitrate(self) -> Optional[float]:
        """Get the target bitrate for throttling. None if disabled"""
        return self.throttler.get_bitrate() if self.throttler.is_enabled() else None

    def reset_bitrate_monitor(self) -> None:
        """Reset data size counters"""
        self.rx_bitcount = 0
        self.tx_bitcount = 0
        self.bitcount_time = time.time()

    def get_link(self) -> Optional[AbstractLink]:
        """Return the Link object used to talk with the device."""
        return self.link

    def get_link_type(self) -> str:
        """Return the link type as a string. This type is the same used by the server configuration"""
        return self.link_type

    def set_link(self, link_type: str, link_config: LinkConfig) -> None:
        """Set the device Link object from a type and a configuration."""
        self.logger.debug('Configuring new device link of type %s with config : %s' % (link_type, str(link_config)))

        self.close()
        if link_type == 'none':
            self.link = None
            self.link_type = "none"
            return

        self.link_type = link_type

        link_class = self.get_link_class(link_type)
        self.link = link_class.make(link_config)

    def validate_link_config(self, link_type: str, link_config: LinkConfig) -> None:
        """Raises an exception if the given configuration is wrong for the given link type"""
        link_class = self.get_link_class(link_type)
        return link_class.validate_config(link_config)

    def get_link_class(self, link_type: str) -> Type[AbstractLink]:
        """Link Factory that returns the correct Link class based on a type given as string."""
        link_class: Type[AbstractLink]

        if link_type == 'udp':
            from scrutiny.server.device.links.udp_link import UdpLink
            link_class = UdpLink
        elif link_type == 'serial':
            from scrutiny.server.device.links.serial_link import SerialLink
            link_class = SerialLink
        elif link_type == 'dummy':
            from scrutiny.server.device.links.dummy_link import DummyLink
            link_class = DummyLink
        elif link_type == 'thread_safe_dummy':
            from scrutiny.server.device.links.dummy_link import ThreadSafeDummyLink
            link_class = ThreadSafeDummyLink
        else:
            raise ValueError('Unknown link type %s' % link_type)

        return link_class

    def open(self) -> None:
        """Try to open the communication channel with the device."""
        if self.link is None:
            raise Exception('Link must be set before opening')

        try:
            self.link.initialize()
            self.opened = True
        except Exception as e:
            self.logger.error("Cannot connect to device. " + str(e))
            self.opened = False

    def is_open(self) -> bool:
        """Return True if the communication channel is open with the device"""
        return self.opened

    def close(self) -> None:
        """Close the communication channel with the device"""
        if self.link is not None:
            self.link.destroy()

        self.reset()
        self.opened = False

    def is_operational(self) -> bool:
        """Return True if the communication channel is presently in a healthy state."""
        if self.link is None:
            return False

        return self.opened and self.link.operational()

    def process(self) -> None:
        """To be called periodically"""
        if self.link is None:
            self.reset()
            return

        if self.link.initialized() and not self.link.operational():
            self.logger.error('Communication link stopped working. Stopping communication')
            # Something broken here. Hardware disconnected maybe?
            self.close()    # Destroy and deinit the link
            return

        if self.is_operational():
            self.link.process()  # Process the link handling
            self.throttler.process()
            self.process_rx()   # Treat response reception
            self.process_tx()   # Handle throttling

    def process_rx(self) -> None:
        """Handle data reception"""
        assert self.link is not None

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

        if len(self.rx_data.data_buffer) >= 5:  # We have a valid command,subcommand, code and length (16bits)
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
                            raise Exception("Unexpected Response command ID : %s Expecting: %s" %
                                            (str(self.received_response), self.active_request.command))
                        if self.received_response.subfn != self.active_request.subfn:
                            raise Exception("Unexpected Response subfunction : %s. Expecting: %s" %
                                            (str(self.received_response), self.active_request.subfn))
                    else:
                        # Should never happen. waiting_response() is checked above
                        raise Exception('Got a response while having no request in process')

                    # Here, everything went fine. The application can now send a new request or read the received response.
                except Exception as e:
                    self.logger.error("Received malformed message. " + str(e))
                    self.reset_rx()

    def process_tx(self, newrequest: bool = False) -> None:
        """Handle data transmission"""
        assert self.link is not None

        if self.pending_request is not None:
            approx_delta_bandwidth = (self.pending_request.size() + self.pending_request.get_expected_response_size()) * 8;
            if self.throttler.allowed(approx_delta_bandwidth):
                self.active_request = self.pending_request
                self.pending_request = None
                data = self.active_request.to_bytes()
                self.logger.debug("Sending request %s" % self.active_request)
                self.logger.debug("Sending : %s" % (hexlify(data).decode('ascii')))
                datasize_bits = len(data) * 8
                try:
                    self.link.write(data)
                    err = None
                except Exception as e:
                    err = e
                    self.logger.error('Cannot write to communication link. %s' % str(e))
                    self.logger.debug(traceback.format_exc())

                if not err:
                    self.tx_bitcount += datasize_bits
                    self.throttler.consume_bandwidth(datasize_bits)
                    self.response_timer.start(self.params['response_timeout'])
            elif not self.throttler.possible(approx_delta_bandwidth):
                self.logger.critical("Throttling doesn't allow to send request. Dropping %s" % self.pending_request)
                self.pending_request = None
            else:
                if newrequest:  # Not sent right away
                    self.logger.debug('Received request to send. Waiting because of throttling. %s' % self.pending_request)

    def response_available(self) -> bool:
        """Return True if a response for the pending request has been received"""
        return (self.received_response is not None)

    def has_timed_out(self) -> bool:
        """Return True if the pending request has timed out without response"""
        return self.timed_out

    def clear_timeout(self) -> None:
        """Clear the timeout if the pending request did time out. Put back the CommHandler in a ready state for the next request"""
        self.timed_out = False

    def get_response(self) -> Response:
        """Return the response received for the active request"""
        if self.received_response is None:
            raise Exception('No response to read')

        response = self.received_response   # Make a copy of the response to return before clearing everything
        self.reset_rx()  # Since user read the response, it has been acknowledged. Make sure response_available() return False

        return response

    def reset_rx(self) -> None:
        """ 
        Make sure we can send a new request.
        Also clear the received response so that response_available() return False
        """
        self.active_request = None
        self.pending_request = None
        self.received_response = None
        self.response_timer.stop()
        self.rx_data.clear()

    def send_request(self, request: Request) -> None:
        """Sends a request to the device"""
        if self.waiting_response():
            raise Exception('Cannot send new request. Already waiting for a response')

        if self.opened:
            self.pending_request = request
            self.received_response = None
            self.timed_out = False
            self.process_tx(newrequest=True)

    def waiting_response(self) -> bool:
        """Return True if there is a pending request waiting for a response. 
        Will return False if the pending request does time out"""
        # We are waiting response if a request is active, meaning it has been sent and response has not been acknowledge by the application
        if not self.opened:
            return False
        return (self.active_request is not None or self.pending_request is not None)

    def reset(self) -> None:
        """Put back the CommHandler to its startup state"""
        self.reset_rx()
        self.clear_timeout()

    def get_average_bitrate(self) -> float:
        """Get the measured average bitrate since last counter reset"""
        dt = time.time() - self.bitcount_time
        return float(self.rx_bitcount + self.tx_bitcount) / float(dt)
