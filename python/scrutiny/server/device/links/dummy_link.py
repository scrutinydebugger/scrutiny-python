
class DummyLink:
    def __init__(self):
        self.initialize()

    def initialize(self):
        self.to_device_data = bytes()
        self.from_device_data = bytes()

    def destroy(self):
        self.to_device_data = bytes()
        self.from_device_data = bytes()

    def write(self, data):
        self.to_device_data += data

    def read(self):
        data = self.from_device_data
        self.from_device_data = bytes()
        return data

    def emulate_device_read(self):
        data = self.to_device_data
        self.to_device_data = bytes()
        return data

    def emulate_device_write(self, data):
        self.from_device_data += data

    def process(self):
        pass

    def operational(self):
        return True

