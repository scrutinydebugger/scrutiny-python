import queue

class RequestDispatcher:

    class RequestRecord:
        __slots__ = ('request', 'success_callback', 'failure_callback', 'success_params', 'failure_params', 'completed')

        def __init__(self):
            self.completed = False

        def complete(self, success=False, response=None, response_data = None):
            try:
                if success:
                    if response is None or response_data is None:
                        raise ValueError('Missing response')
                    self.success_callback(self.request, response, response_data, self.success_params)
                else:
                    self.failure_callback(self.request, self.failure_params)
                self.completed = True
            except:
                self.completed = True
                raise

        def is_completed(self):
            return self.completed

    def __init__(self):
        self.request_queue = queue.Queue()

    def register_request(self, request, success_callback, failure_callback, priority=0, success_params = None, failure_params=None):
        record = self.RequestRecord()
        record.request = request
        record.success_callback = success_callback
        record.success_params = success_params
        record.failure_callback = failure_callback
        record.failure_params = failure_params

        self.request_queue.put(record)

    def next(self):
        if not self.request_queue.empty():
            return self.request_queue.get()
