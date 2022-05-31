#    request_dispatcher.py
#        Use a PriorityQueue to dispatch Request to the device. Associate each request with
#        its callback
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import bisect
from scrutiny.server.protocol import Request, RequestData, Response, ResponseData, ResponseCode
from scrutiny.server.tools import Throttler
from time import time
import math
import logging

from typing import List, Optional, Callable, Any, TypeVar
from scrutiny.core.typehints import GenericCallback


# Type for mypy validation only
class SuccessCallback(GenericCallback):
    callback: Optional[Callable[[Request, ResponseCode, bytes, Any], None]]


class FailureCallback(GenericCallback):
    callback: Optional[Callable[[Request, Any], None]]


class RequestQueue:
    """
    Non-thread-safe Queue with priority.
    Replace queue.PriorityQueue simply because I don't like that they compare data and don't want to introduce workarounds or 
    dataclass from Python 3.7 just for not comparing the data when selecting priority.
    We will have all the flexibility we need with our own minimalist custom class
    """

    maxsize: Optional[int]       # Upper limit of queue size
    data: List["RequestRecord"]    # Queue data
    priorities: List[int]        # Element for bisect. Bisect does not support searching on a specific key before python 3.10

    def __init__(self, maxsize: Optional[int] = None):
        self.clear()
        self.maxsize = maxsize

    def clear(self) -> None:
        self.data = []
        self.priorities = []

    def push(self, item: "RequestRecord", priority: int = 0) -> None:
        if self.maxsize is not None and len(self.data) >= self.maxsize:
            raise Exception('Request queue full')

        index = bisect.bisect_left(self.priorities, priority)
        self.data.insert(index, item)
        self.priorities.insert(index, priority)

    def pop(self) -> Optional["RequestRecord"]:
        if len(self.data) > 0:
            item = self.data[-1]
            del self.priorities[-1]
            del self.data[-1]
            return item
        return None

    def peek(self) -> Optional["RequestRecord"]:
        if len(self.data) > 0:
            return self.data[-1]
        return None

    def empty(self) -> bool:
        return len(self.data) == 0

    def __len__(self):
        return len(self.data)


class RequestRecord:
    __slots__ = ('request', 'success_callback', 'failure_callback', 'success_params', 'failure_params', 'completed', 'approximate_delta_bandwidth')

    request: Request
    success_callback: SuccessCallback
    failure_callback: FailureCallback
    success_params: Any
    failure_params: Any
    completed: bool
    approximate_delta_bandwidth: int

    def __init__(self):
        self.completed = False

    def complete(self, success: bool = False, response: Optional[Response] = None):
        self.completed = True  # Set to true at beginning so that it is still true if an exception raise in the callback
        if success:
            if response is None:
                raise ValueError('Missing response')
            self.success_callback.__call__(self.request, response, self.success_params)
        else:
            self.failure_callback.__call__(self.request, self.failure_params)

    def is_completed(self) -> bool:
        return self.completed


class RequestDispatcher:

    request_queue: RequestQueue
    logger: logging.Logger
    rx_size_limit: Optional[int]
    tx_size_limit: Optional[int]
    critical_error: bool

    def __init__(self, queue_size=100):
        self.request_queue = RequestQueue(maxsize=queue_size)  # Will prevent bloating because of throttling
        self.logger = logging.getLogger(self.__class__.__name__)
        self.reset()

    def reset(self) -> None:
        self.rx_size_limit = None
        self.tx_size_limit = None
        self.critical_error = False
        self.request_queue.clear()

    def is_in_error(self) -> bool:
        return self.critical_error

    def register_request(self, request: Request, success_callback: SuccessCallback, failure_callback: FailureCallback, priority: int = 0, success_params: Any = None, failure_params: Any = None) -> None:
        record = RequestRecord()
        record.request = request
        record.success_callback = success_callback
        record.success_params = success_params
        record.failure_callback = failure_callback
        record.failure_params = failure_params
        record.approximate_delta_bandwidth = (request.size() + request.get_expected_response_size()) * 8

        if self.rx_size_limit is not None:
            if request.size() > self.rx_size_limit:  # Should not happens. Request generators should craft their request according to this limit
                self.logger.critical('Request is bigger than device receive buffer. Dropping %s' % request)
                self.critical_error = True
                record.complete(success=False)
                return None

        if self.tx_size_limit is not None:
            if request.get_expected_response_size() > self.tx_size_limit:  # Should not happens. Request generators should craft their request according to this limit
                self.logger.critical('Request expected response size is bigger than device tx buffer. Dropping %s' % request)
                self.critical_error = True
                record.complete(success=False)
                return None

        self.request_queue.push(record, priority)
        return None

    def set_size_limits(self, max_request_size: Optional[int], max_response_size: Optional[int]) -> None:
        self.rx_size_limit = max_request_size
        self.tx_size_limit = max_response_size

    def process(self) -> None:
        pass    # nothing to do

    def peek_next(self) -> Optional[RequestRecord]:
        return self.request_queue.peek()

    def pop_next(self) -> Optional[RequestRecord]:
        return self.request_queue.pop()
