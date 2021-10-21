import subprocess

class SubprocessLink

    def __init__(self, parameters):
        if 'cmd' not in parameters:
            raise ValueError('Missing subprocess command')

        self.cmd = parameters['cmd']
        self.args = parameters['args'] if 'args' in parameters else []:
        self.process = None

    def initialize(self):
        self.process = subprocess.Popen(self.cmd + self.args, stdout=subprocess.PIPE, stdin=subprocess.PIPE)


    def destroy(self):
        pass

    def read(self):
        pass

    def write(self, data):
        pass
