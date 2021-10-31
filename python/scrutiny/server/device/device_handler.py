import copy
from scrutiny.server.protocol.comm_handler import CommHandler

class DeviceHandler:
    DEFAULT_COMM_PARAMS = {
            'response_timeout' : 1.0    # If a response take more than this delay to be received after a request is sent, drop the response.
        }

    def __init__(self, config, datastore):
        self.config = config
        self.datastore = datastore

        comm_handler_params = copy.copy(self.DEFAULT_COMM_PARAMS)

        if 'comm_response_timeout' in self.config:
            comm_handler_params['response_timeout'] = self.config['comm_response_timeout']

        self.comm_handler = CommHandler(comm_handler_params)
        self.connected = False

    def connect(self):
        if self.config['link_type'] == 'none':
            return

        if self.config['link_type'] == 'memdump':
            from .links.fake_device_memdump import FakeDeviceMemdump
            device_link = FakeDeviceMemdump(self.config['link_config'])
        elif self.config['link_type'] == 'subprocess':
            from .links.subprocess_link import SubprocessLink
            device_link = SubprocessLink(self.config['link_config'])
        else:
            raise ValueError('Unknown link type %s' % self.config['link_type'])

        self.comm_handler.open(device_link)
        self.connected = True

    def disconnect(self):
        if self.comm_handler is not None:
            self.comm_handler.close()
        self.connected = False

    def refresh_vars(self):
        pass

    def process(self):
        self.comm_handler.process() 
