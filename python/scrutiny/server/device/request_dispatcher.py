#    request_dispatcher.py
#        Use a PriorityQueue to dispatch Request to the device. Associate each request wi
#        its callback
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import bisect


class RequestDispatcher:

    class RequestQueue:
        """
        Non-thread-safe Queue with priority.
        Replace queue.PriorityQueue simply because I don't like that they compare data and don't want to introduce workarounds or 
        dataclass from Python 3.7 just for not comparing the data when selecting priority.
        We will have all the flexibility we need with our own minimalist custom class
        """

        def __init__(self):
            self.clear()

        def clear(self):
            self.data = []
            self.priorities = []

        def push(self, item, priority=0):
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
        __slots__ = ('request', 'success_callback', 'failure_callback', 'success_params', 'failure_params', 'completed')

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

    def __init__(self):
        self.request_queue = self.RequestQueue()

    def register_request(self, request, success_callback, failure_callback, priority=0, success_params=None, failure_params=None):
        record = self.RequestRecord()
        record.request = request
        record.success_callback = success_callback
        record.success_params = success_params
        record.failure_callback = failure_callback
        record.failure_params = failure_params

        self.request_queue.push(record, priority)

    def next(self):
        return self.request_queue.pop()
