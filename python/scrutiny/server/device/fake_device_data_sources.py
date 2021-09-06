from scrutiny.core.memdump import Memdump

class FakeDeviceMemdumpDataSource:

    def __init__(self, filename):
        self.memdump = Memdump(filename)

    def read(self, addr, length):
        return self.memdump.read(addr, length)

    def write(self, addr, data):
        self.memdump.write(addr, data)

