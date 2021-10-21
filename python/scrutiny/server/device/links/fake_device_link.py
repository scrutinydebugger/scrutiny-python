
from core.memdump import Memdump

#Emulate communication with a device but data is coming from a local memdump file

class FakeDeviceLink

    def __init__(self, parameters):
        if 'filename' not in parameters:
            raise ValueError('Missing memdump filename')

        self.parameters = parameters['filename']
        self.memdump = None

    def initialize(self):
        self.memdump = Memdump(self.parameters[filename])

    def destroy(self):
        self.memdump = None

    def read(self, addr, length):
        return self.memdump.read(addr, length)

