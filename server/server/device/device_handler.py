import copy

class DeviceHandler:

    def __init__(self, datastore, firmware_desc):
        self.device = None
        self.ds = datastore
        self.firmware_desc = firmware_desc
        self.to_update_list = None

    def connect(self, device_type, parameters):
        if device_type == 'memdump':
            from .links.fake_device_memdump import FakeDeviceMemdump
            self.device = FakeDeviceMemdump(parameters)
        else:
            raise ValueError('Unknown device type %s' % device_type)

        self.device.initialize()

    def disconnect(self):
        if self.device is not None:
            self.device.destroy()
        self.device = None

    def refresh_vars(self):
        pass

    def process(self):
        if to_update_list is None:
            watched_entries = self.datastore.get_watched_entries()
            self.to_update_list = list(watched_entries)
            sort(self.to_update_list, key=lambda entry: entry.get_update_time())

        while len(self.to_update_list) > 0 and not self.device.busy():
            entry_to_read = self.to_update_list.pop(0)
            # todos
