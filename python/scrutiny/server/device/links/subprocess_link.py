import subprocess
import threading
import queue
import logging

class SubprocessLink:

    def __init__(self, parameters):
        if 'cmd' not in parameters:
            raise ValueError('Missing subprocess command')

        self.cmd = parameters['cmd']
        self.args = parameters['args'] if 'args' in parameters else []
        self.process = None
        self.read_queue = queue.Queue()
        self.read_thread = None
        self.logger = logging.getLogger(self.__class__.__name__)

    def initialize(self):
        args = [self.cmd] + self.args
        self.logger.debug('Starting subprocess with command: "%s"' % ' '.join(args))
        self.process = subprocess.Popen([self.cmd] + self.args, stdout=subprocess.PIPE, stdin=subprocess.PIPE, bufsize=1)
        self.read_thread =  threading.Thread(target=self.read_thread_func)
        self.request_thread_exit = False
        self.read_thread.start()


    def destroy(self):
        args = [self.cmd] + self.args
        self.logger.debug('Stopping subprocess "%s"' % ' '.join(args))
        self.request_thread_exit = True
        if self.process is not None:
            self.process.terminate()
            self.process.wait(0.1)
        if self.read_thread is not None:
            self.read_thread.join()

    def read(self):
        data = bytes()
        while not self.read_queue.empty():
            data += self.read_queue.get()
        return data

    def write(self, data):
        pass

    def read_thread_func(self):
        while self.request_thread_exit == False:
            try:
                b = self.process.stdout.read(1)
                self.read_queue.put(b)
            except:
                break  

