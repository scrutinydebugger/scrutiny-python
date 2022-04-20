#    request_dispatcher.py
#        Use a PriorityQueue to dispatch Request to the device. Associate each request with
#        its callback
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import bisect
from scrutiny.server.protocol import Response
from scrutiny.server.server_tools import Throttler
from time import time
import math
import logging


class RequestQueue:
    """
    Non-thread-safe Queue with priority.
    Replace queue.PriorityQueue simply because I don't like that they compare data and don't want to introduce workarounds or 
    dataclass from Python 3.7 just for not comparing the data when selecting priority.
    We will have all the flexibility we need with our own minimalist custom class
    """

    def __init__(self, size=None):
        self.clear()
        self.size = size

    def clear(self):
        self.data = []
        self.priorities = []

    def push(self, item, priority=0):
        if self.size is not None and len(self.data) >= self.size:
            raise Exception('Request queue full')

        index = bisect.bisect_left(self.priorities, priority)
        self.data.insert(index, item)
        self.priorities.insert(index, priority)

    def pop(self):
        if len(self.data) > 0:
            item = self.data[-1]
            del self.priorities[-1]
            del self.data[-1]
            return item

    def peek(self):
        if len(self.data) > 0:
            return self.data[-1]

    def empty(self):
        return len(self.data) == 0

    def __len__(self):
        return len(self.data)


class RequestRecord:
    __slots__ = ('request', 'success_callback', 'failure_callback', 'success_params', 'failure_params', 'completed', 'delta_bandwidth')

    def __init__(self):
        self.completed = False

    def complete(self, success=False, response=None, response_data=None):
        self.completed = True  # Set to true at beginning so that it is still true if an exception raise in the callback
        if success:
            if response is None or response_data is None:
                raise ValueError('Missing response')
            self.success_callback(self.request, response.code, response_data, self.success_params)
        else:
            self.failure_callback(self.request, self.failure_params)

    def is_completed(self):
        return self.completed


class RequestDispatcher:
    def __init__(self, queue_size=100):
        self.request_queue = RequestQueue(size=queue_size)  # Will prevent bloating because of throttling
        self.throttler = Throttler()
        self.rx_size_limit = None
        self.tx_size_limit = None
        self.logger = logging.getLogger(self.__class__.__name__)

    def enable_throttling(self, bitrate):
        self.throttler.set_bitrate(bitrate)
        self.throttler.enable()

    def disable_throttling(self):
        self.throttler.disable()

    def register_request(self, request, success_callback, failure_callback, priority=0, success_params=None, failure_params=None):
        if self.rx_size_limit is not None:
            if request.size() > self.rx_size_limit:  # Should not happens. Request generators should craft their request according to this limit
                self.logger.critical('Request is bigger than device receive buffer. Dropping %s' % request)
                return

        if self.tx_size_limit is not None:
            if request.get_expected_response_size() > self.tx_size_limit:  # Should not happens. Request generators should craft their request according to this limit
                self.logger.critical('Request expected response size is bigger than device tx buffer. Dropping %s' % request)
                return

        record = RequestRecord()
        record.request = request
        record.success_callback = success_callback
        record.success_params = success_params
        record.failure_callback = failure_callback
        record.failure_params = failure_params

        record.delta_bandwidth = (request.size() + request.get_expected_response_size()) * 8

        self.request_queue.push(record, priority)

    def set_size_limits(self, rx_size_limit, tx_size_limit):
        self.rx_size_limit = rx_size_limit
        self.tx_size_limit = tx_size_limit

    def process(self):
        self.throttler.process()

    def next(self):
        record = self.request_queue.peek()
        if record is None:
            return

        if self.throttler.allowed(record.delta_bandwidth):
            self.throttler.consume_bandwidth(record.delta_bandwidth)
            return self.request_queue.pop()
