import time

class Timer:
    def __init__(self, timeout):
        self.set_timeout(timeout)
        self.start_time = None

    def set_timeout(self, timeout):
        self.timeout = timeout

    def start(self, timeout=None):
        if timeout is not None:
            self.set_timeout(timeout)
        self.start_time = time.time()

    def stop(self):
        self.start_time = None

    def elapsed(self):
        if self.start_time is not None:
            return time.time() - self.start_time
        else:
            return 0

    def is_timed_out(self):
        if self.is_stopped() or self.timeout is None:
            return False
        else:
            return self.elapsed() > self.timeout or self.timeout == 0

    def is_stopped(self):
        return self.start_time == None