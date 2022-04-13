import queue

class RequestDispatcher:

    class RequestRecord:
        __slots__ = ('request', 'success_callback', 'failure_callback', 'success_params', 'failure_params', 'completed')

        def __init__(self):
            self.completed = False

        def complete(self, success=False, response=None, response_data = None):
            self.completed = True # Set to true at beginning so that it is still true if an exception raise in the callback
            if success:
                if response is None or response_data is None:
                    raise ValueError('Missing response')
                self.success_callback(self.request, response.code, response_data, self.success_params)
            else:
                self.failure_callback(self.request, self.failure_params)


        def is_completed(self):
            return self.completed

        # Workaround for PriorityQueue that compare the data when priority is equal. bpo-31145
        def __lt__(self, other):
            return False

        def __gt__(self, other):
            return False

        def __eq__(self, other):
            return True

    def __init__(self):
        self.request_queue = queue.PriorityQueue()

    def register_request(self, request, success_callback, failure_callback, priority=0, success_params = None, failure_params=None):
        record = self.RequestRecord()
        record.request = request
        record.success_callback = success_callback
        record.success_params = success_params
        record.failure_callback = failure_callback
        record.failure_params = failure_params

        self.request_queue.put((priority, record))

    def next(self):
        if not self.request_queue.empty():
            prio, req = self.request_queue.get()
            return req
