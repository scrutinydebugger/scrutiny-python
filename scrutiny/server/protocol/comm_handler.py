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


from scrutiny.server.protocol import Request, Response
from scrutiny.tools import Timer, Throttler
from copy import copy
import logging
import struct
from binascii import hexlify
import time
from scrutiny.server.device.links import AbstractLink, LinkConfig
import traceback
import queue

from typing import TypedDict, Optional, Any, Dict, Type, cast
import threading


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

    _active_request: Optional[Request]
    _received_response: Optional[Response]
    _link: Optional[AbstractLink]
    _params: "CommHandler.Params"
    _response_timer: Timer
    _rx_data: "CommHandler.RxData"
    _logger: logging.Logger
    _opened: bool
    _throttler: Throttler
    _rx_bitcount: int
    _tx_bitcount: int
    _bitcount_time: float
    _timed_out: bool
    _pending_request: Optional[Request]
    _link_type: str
    _last_open_error: Optional[str]
    _rx_data_event:Optional[threading.Event]
    
    _rx_queue:"queue.Queue[bytes]"
    _rx_thread:Optional[threading.Thread]
    _rx_thread_started:threading.Event
    _rx_thread_stop_requested:threading.Event

    def __init__(self, params: Dict[str, Any] = {}) -> None:
        self._active_request = None      # Contains the request object that has been sent to the device. When None, no request sent and we are standby
        self._received_response = None   # Indicates that a response has been received.
        self._link = None                # Abstracted communication channel that implements  initialize, destroy, write, read
        self.params = copy(self.DEFAULT_PARAMS)
        self.params.update(cast(CommHandler.Params, params))

        self._response_timer = Timer(self.params['response_timeout'])    # Timer for response timeout management
        self._rx_data = self.RxData()    # Contains the response data while we read it.
        self._logger = logging.getLogger(self.__class__.__name__)
        self._opened = False     # True when communication channel is active and working.
        self.reset_bitrate_monitor()
        self._throttler = Throttler()
        self._link_type = "none"
        self._last_open_error = None
        self._rx_data_event = None

        self._rx_queue = queue.Queue()
        self._rx_thread_started = threading.Event()
        self._rx_thread = None
        self._rx_thread_stop_requested = threading.Event()

    def _rx_thread_task(self) -> None:
        self._logger.debug("RX thread started")
        self._rx_thread_started.set()
        while not self._rx_thread_stop_requested.is_set():
            if self._link is not None:
                try:
                    data = self._link.read(timeout=0.5)
                    if data is not None and len(data) > 0:
                        self._rx_queue.put(data)
                        if self._rx_data_event is not None:
                            self._rx_data_event.set()
                except Exception as e:
                    self._logger.error(str(e))
            else:
                time.sleep(0.2)
        self._logger.debug("RX thread exiting")
        

    def set_rx_data_event(self, evt:threading.Event) -> None:
        self._rx_data_event = evt

    def enable_throttling(self, bitrate: float) -> None:
        """Enable throttling on communication.
        Overall bitrate (incoming and outgoing data included) will try to be respected.
        This does not take in account the protocol overhead. Just the payload sum.
        """
        self._throttler.set_bitrate(bitrate)
        self._throttler.enable()

    def disable_throttling(self) -> None:
        """Disable throttling on communication with the device"""
        self._throttler.set_bitrate(0)
        self._throttler.disable()

    def is_throttling_enabled(self) -> bool:
        """Returns True if throttling is enabled on the device communication"""
        return self._throttler.is_enabled()

    def get_throttling_bitrate(self) -> Optional[float]:
        """Get the target bitrate for throttling. None if disabled"""
        return self._throttler.get_bitrate() if self._throttler.is_enabled() else None

    def reset_bitrate_monitor(self) -> None:
        """Reset data size counters"""
        self.rx_bitcount = 0
        self.tx_bitcount = 0
        self.bitcount_time = time.perf_counter()

    def get_link(self) -> Optional[AbstractLink]:
        """Return the Link object used to talk with the device."""
        return self._link

    def get_link_type(self) -> str:
        """Return the link type as a string. This type is the same used by the server configuration"""
        return self._link_type

    def set_link(self, link_type: str, link_config: LinkConfig) -> None:
        """Set the device Link object from a type and a configuration."""
        self._logger.debug('Configuring new device link of type %s with config : %s' % (link_type, str(link_config)))

        self.close()
        if link_type == 'none':
            self._link = None
            self._link_type = "none"
            return

        self._link_type = link_type

        link_class = self._get_link_class(link_type)
        self._link = link_class.make(link_config)
        self._last_open_error = None

    def validate_link_config(self, link_type: str, link_config: LinkConfig) -> None:
        """Raises an exception if the given configuration is wrong for the given link type"""
        link_class = self._get_link_class(link_type)
        return link_class.validate_config(link_config)

    def _get_link_class(self, link_type: str) -> Type[AbstractLink]:
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
        else:
            raise ValueError('Unknown link type %s' % link_type)

        return link_class

    def _stop_rx_thread(self, timeout:float = 1) -> None:
        """Stop the internal thread dedicated to reading the device link object"""
        if self._rx_thread is not None:
            if self._rx_thread.is_alive():
                self._rx_thread_stop_requested.set()
                self._rx_thread.join(timeout)
                if self._rx_thread.is_alive():
                    self._logger.error("Failed to stop the RX thread")
        
        self._rx_thread = None

    def open(self) -> None:
        self._logger.debug("Opening communication with device")
        """Try to open the communication channel with the device."""
        if self._link is None:
            raise Exception('Link must be set before opening')

        try:
            self._link.initialize()
            self._rx_queue = queue.Queue()
            self._rx_thread = threading.Thread(target=self._rx_thread_task, daemon=True)
            self._rx_thread_started.clear()
            self._rx_thread_stop_requested.clear()
            self._rx_thread.start()
            if not self._rx_thread_started.wait(timeout=1):
                self._stop_rx_thread()
                raise TimeoutError("RX thread did not start")
            
            self._opened = True
            self._last_open_error = None
            self._logger.debug("Communication with device opened")
        except Exception as e:
            err = str(e)
            full_error = f"Cannot initialize device. {err}"
            if self._last_open_error != err:
                self._logger.error(full_error)
            elif self._logger.isEnabledFor(logging.DEBUG):
                self._logger.debug(full_error)
            self._last_open_error = err
            self._opened = False 

    def is_open(self) -> bool:
        """Return True if the communication channel is open with the device"""
        return self._opened

    def close(self) -> None:
        """Close the communication channel with the device"""
        self._logger.debug("Closing communication with device")
        self._stop_rx_thread()

        if self._link is not None:
            self._link.destroy()

        self.reset()
        self._last_open_error = None
        self._opened = False
        self._logger.debug("Communication with device closed")

    def is_operational(self) -> bool:
        """Return True if the communication channel is presently in a healthy state."""
        if self._link is None:
            return False

        return self._opened and self._link.operational()

    def process(self) -> None:
        """To be called periodically"""
        if self._link is None:
            self.reset()
            return

        if self._link.initialized() and not self._link.operational():
            self._logger.error('Communication link stopped working. Stopping communication')
            # Something broken here. Hardware disconnected maybe?
            self.close()    # Destroy and deinit the link
            return

        if self.is_operational():
            self._link.process()  # Process the link handling
            self._throttler.process()
            self._process_rx()   # Treat response reception
            self._process_tx()   # Handle throttling

    def _process_rx(self) -> None:
        """Handle data reception"""
        assert self._link is not None

        # If we haven't got a response or we know we won't get one. Mark the request as timed out
        if self.waiting_response() and (self._response_timer.is_timed_out() or not self._link.operational()):
            self.reset_rx()
            self.timed_out = True

        if self._rx_queue.empty():
            return
        data = self._rx_queue.get()

        datasize_bits = len(data) * 8
        self._throttler.consume_bandwidth(datasize_bits)
        self.rx_bitcount += datasize_bits
        self._logger.debug('Received : %s' % (hexlify(data).decode('ascii')))

        if self.response_available() or not self.waiting_response():
            self._logger.debug('Received unwanted data: ' + hexlify(data).decode('ascii'))
            return  # Purposely discard data if we are not expecting any

        self._rx_data.data_buffer += data    # Add data to receive buffer

        if len(self._rx_data.data_buffer) >= 5:  # We have a valid command,subcommand, code and length (16bits)
            if self._rx_data.length is None:
                self._rx_data.length, = struct.unpack('>H', self._rx_data.data_buffer[3:5])   # Read the data length

        if self._rx_data.length is not None:  # We already received a valid header
            expected_bytes_count = self._rx_data.length + 9  # payload + header (5 bytes), CRC (4bytes)
            if len(self._rx_data.data_buffer) >= expected_bytes_count:
                self._rx_data.data_buffer = self._rx_data.data_buffer[0:expected_bytes_count]  # Remove extra bytes

                # We have enough data, try to decode the response and validate the CRC.
                try:
                    self._received_response = Response.from_bytes(self._rx_data.data_buffer)  # CRC validation is done here

                    # Decoding did not raised an exception, we have a valid payload!
                    self._logger.debug("Received Response %s" % self._received_response)
                    self._rx_data.clear()        # Empty the receive buffer
                    self._response_timer.stop()  # Timeout timer can be stop
                    if self._active_request is not None:  # Just to please mypy
                        # Validate that the response match the request
                        if self._received_response.command != self._active_request.command:
                            raise RuntimeError("Unexpected Response command ID : %s Expecting: %s" %
                                            (str(self._received_response), self._active_request.command))
                        if self._received_response.subfn != self._active_request.subfn:
                            raise RuntimeError("Unexpected Response subfunction : %s. Expecting: %s" %
                                            (str(self._received_response), self._active_request.subfn))
                    else:
                        # Should never happen. waiting_response() is checked above
                        raise RuntimeError('Got a response while having no request in process')

                    # Here, everything went fine. The application can now send a new request or read the received response.
                except Exception as e:
                    self._logger.error("Received malformed message. " + str(e))
                    self.reset_rx()

    def _process_tx(self, newrequest: bool = False) -> None:
        """Handle data transmission"""
        assert self._link is not None

        if self._pending_request is not None:
            approx_delta_bandwidth = (self._pending_request.size() + self._pending_request.get_expected_response_size()) * 8
            if self._throttler.allowed(approx_delta_bandwidth):
                self._active_request = self._pending_request
                self._pending_request = None
                data = self._active_request.to_bytes()
                self._logger.debug("Sending request %s" % self._active_request)
                self._logger.debug("Sending : %s" % (hexlify(data).decode('ascii')))
                datasize_bits = len(data) * 8
                try:
                    self._link.write(data)
                    err = None
                except Exception as e:
                    err = e
                    self._logger.error('Cannot write to communication link. %s' % str(e))
                    self._logger.debug(traceback.format_exc())

                if not err:
                    self.tx_bitcount += datasize_bits
                    self._throttler.consume_bandwidth(datasize_bits)
                    self._response_timer.start(self.params['response_timeout'])
            elif not self._throttler.possible(approx_delta_bandwidth):
                self._logger.critical("Throttling doesn't allow to send request. Dropping %s" % self._pending_request)
                self._pending_request = None
            else:
                if newrequest:  # Not sent right away
                    self._logger.debug('Received request to send. Waiting because of throttling. %s' % self._pending_request)

    def response_available(self) -> bool:
        """Return True if a response for the pending request has been received"""
        return (self._received_response is not None)

    def has_timed_out(self) -> bool:
        """Return True if the pending request has timed out without response"""
        return self.timed_out

    def clear_timeout(self) -> None:
        """Clear the timeout if the pending request did time out. Put back the CommHandler in a ready state for the next request"""
        self.timed_out = False

    def get_response(self) -> Response:
        """Return the response received for the active request"""
        if self._received_response is None:
            raise Exception('No response to read')

        response = self._received_response   # Make a copy of the response to return before clearing everything
        self.reset_rx()  # Since user read the response, it has been acknowledged. Make sure response_available() return False

        return response

    def reset_rx(self) -> None:
        """ 
        Make sure we can send a new request.
        Also clear the received response so that response_available() return False
        """
        self._active_request = None
        self._pending_request = None
        self._received_response = None
        self._response_timer.stop()
        self._rx_data.clear()

    def send_request(self, request: Request) -> None:
        """Sends a request to the device"""
        if self.waiting_response():
            raise Exception('Cannot send new request. Already waiting for a response')

        if self._opened:
            self._pending_request = request
            self._received_response = None
            self.timed_out = False
            self._process_tx(newrequest=True)

    def waiting_response(self) -> bool:
        """Return True if there is a pending request waiting for a response. 
        Will return False if the pending request does time out"""
        # We are waiting response if a request is active, meaning it has been sent and response has not been acknowledge by the application
        if not self._opened:
            return False
        return (self._active_request is not None or self._pending_request is not None)

    def reset(self) -> None:
        """Put back the CommHandler to its startup state"""
        self.reset_rx()
        self.clear_timeout()

    def get_average_bitrate(self) -> float:
        """Get the measured average bitrate since last counter reset"""
        dt = time.perf_counter() - self.bitcount_time
        return float(self.rx_bitcount + self.tx_bitcount) / float(dt)
