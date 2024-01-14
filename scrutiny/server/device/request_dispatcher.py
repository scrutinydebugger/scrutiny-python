#    request_dispatcher.py
#        Use a PriorityQueue to dispatch Request to the device. Associate each request with
#        its callback
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import bisect
from scrutiny.server.protocol import Request, Response, ResponseCode
from time import time
import logging

from typing import List, Optional, Callable, Any
from scrutiny.core.typehints import GenericCallback


# Type for mypy validation only
class SuccessCallback(GenericCallback):
    callback: Callable[[Request, ResponseCode, bytes, Any], None]


class FailureCallback(GenericCallback):
    callback: Callable[[Request, Any], None]


class RequestQueue:
    """
    Non-thread-safe Queue with priority.
    Replace queue.PriorityQueue simply because I don't like that they compare data and don't want to introduce workarounds or 
    dataclass from Python 3.7 just for not comparing the data when selecting priority.
    We will have all the flexibility we need with our own minimalist custom class
    """
    OVERSIZE_WARNING_LEVEL = 10
    OVERSIZE_ERROR_LEVEL = 100
    WARNING_INTERVAL = 2

    maxsize: Optional[int]       # Upper limit of queue size
    data: List["RequestRecord"]    # Queue data
    priorities: List[int]        # Element for bisect. Bisect does not support searching on a specific key before python 3.10
    logger: logging.Logger
    last_warning_time: Optional[float]

    def __init__(self, maxsize: Optional[int] = None):
        self.clear()
        self.maxsize = maxsize
        self.logger = logging.getLogger(self.__class__.__name__)

    def clear(self) -> None:
        """Delete all data inside the queue"""
        self.data = []
        self.priorities = []

    def push(self, item: "RequestRecord", priority: int = 0) -> None:
        """Push an element into the queue"""
        if self.maxsize is not None and len(self.data) >= self.maxsize:
            raise Exception('Request queue full')

        index = bisect.bisect_left(self.priorities, priority)
        self.data.insert(index, item)
        self.priorities.insert(index, priority)

        queue_size = len(self.data)
        if queue_size >= self.OVERSIZE_WARNING_LEVEL:
            if self.last_warning_time is None or (time() - self.last_warning_time) > self.WARNING_INTERVAL:
                self.last_warning_time = time()
                self.logger.warning("Request queue reached %d" % queue_size)

        if queue_size > self.OVERSIZE_ERROR_LEVEL:
            error_msg = "Request queue is growing too fast. Size=%d" % queue_size
            self.logger.critical(error_msg)
            raise RuntimeError(error_msg)

    def pop(self) -> Optional["RequestRecord"]:
        """Pop an element at the exit of the queue"""
        if len(self.data) > 0:
            item = self.data[-1]
            del self.priorities[-1]
            del self.data[-1]
            return item
        return None

    def peek(self) -> Optional["RequestRecord"]:
        """Get without removing the next element to come at the exit of the queue"""
        if len(self.data) > 0:
            return self.data[-1]
        return None

    def empty(self) -> bool:
        """Returns True if the queue is empty"""
        return len(self.data) == 0

    def __len__(self) -> int:
        return len(self.data)


class RequestRecord:
    """Represents a request to dispatch a scrutiny protocol request. 
    Completion callbacks are attached to this object alongside the protocol request"""

    __slots__ = ('request', 'success_callback', 'failure_callback', 'success_params', 'failure_params', 'completed', 'approximate_delta_bandwidth')

    request: Request
    """The Scrutiny protocol request to send"""

    success_callback: SuccessCallback
    """Callback to call if the request get a valid response"""

    failure_callback: FailureCallback
    """Callback to call if the request fails to get a response (timeout or communication problem)"""

    success_params: Any
    """Parameters to give to the success callback"""

    failure_params: Any
    """Parameters to give to the failure callback"""

    completed: bool
    """True when the request is completed (success or failure)"""

    approximate_delta_bandwidth: int
    """Amount of bits that will be exchanged if this request completes. Used for throttling"""

    def __init__(self) -> None:
        self.completed = False

    def complete(self, success: bool = False, response: Optional[Response] = None) -> None:
        """Mark this record as completed (success or failure). Will triggers callback execution"""
        self.completed = True  # Set to true at beginning so that it is still true if an exception raise in the callback
        if success:
            if response is None:
                raise ValueError('Missing response')
            self.success_callback.__call__(self.request, response, self.success_params)
        else:
            self.failure_callback.__call__(self.request, self.failure_params)

    def is_completed(self) -> bool:
        """Return True if the request has completed (success or failure)"""
        return self.completed


class RequestDispatcher:
    """Uses a priority queue to buffer all pending Scrutiny Protocol requests and 
    decide which one is the next to go out."""

    request_queue: RequestQueue
    """PriorityQueue for requests"""

    logger: logging.Logger
    rx_data_size_limit: Optional[int]   # Used to validate that a request will fit in the device. If the payload is bigger than that, dropped
    tx_data_size_limit: Optional[int]
    critical_error: bool

    def __init__(self, queue_size: int = 100) -> None:
        self.request_queue = RequestQueue(maxsize=queue_size)  # Will prevent bloating because of throttling
        self.logger = logging.getLogger(self.__class__.__name__)
        self.reset()

    def reset(self) -> None:
        """Clear all data within the RequestDispatcher and reset any error."""
        self.rx_data_size_limit = None
        self.tx_data_size_limit = None
        self.critical_error = False
        self.request_queue.clear()

    def is_in_error(self) -> bool:
        """Returns True if an error occurred. Will happen if a request has been enqueued that either 
        has a request or an expected response size bigger than what the device can handle"""
        return self.critical_error

    def register_request(self,
                         request: Request,
                         success_callback: SuccessCallback,
                         failure_callback: FailureCallback,
                         priority: int = 0, success_params: Any = None, failure_params: Any = None) -> None:
        """Enqueue a request to be sent to the device with a priority and completion callbacks"""
        record = RequestRecord()
        record.request = request
        record.success_callback = success_callback
        record.success_params = success_params
        record.failure_callback = failure_callback
        record.failure_params = failure_params
        record.approximate_delta_bandwidth = (request.size() + request.get_expected_response_size()) * 8

        if self.rx_data_size_limit is not None:
            if request.data_size() > self.rx_data_size_limit:  # Should not happens. Request generators should craft their request according to this limit
                self.logger.critical('Request is bigger than device receive buffer. Dropping %s' % request)
                self.critical_error = True
                record.complete(success=False)
                return None

        if self.tx_data_size_limit is not None:
            if request.get_expected_response_data_size() > self.tx_data_size_limit:  # Should not happens. Request generators should craft their request according to this limit
                self.logger.critical('Request expected response size is bigger than device tx buffer. Dropping %s' % request)
                self.critical_error = True
                record.complete(success=False)
                return None

        self.request_queue.push(record, priority)
        return None

    def set_size_limits(self, max_request_payload_size: Optional[int], max_response_payload_size: Optional[int]) -> None:
        """Set the device size limit. If a request is enqueued that doesn't fit these size, it will be dropped and an error will be reported"""
        self.rx_data_size_limit = max_request_payload_size
        self.tx_data_size_limit = max_response_payload_size

    def process(self) -> None:
        """To be called periodically"""
        pass    # nothing to do

    def peek_next(self) -> Optional[RequestRecord]:
        """Get the next request to be sent without removing it from the queue"""
        return self.request_queue.peek()

    def pop_next(self) -> Optional[RequestRecord]:
        """Get the next request to be sent and remove it from the queue"""
        return self.request_queue.pop()
