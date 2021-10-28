import unittest
from scrutiny.server.device.device_handler import DeviceHandler
from scrutiny.server.datastore import Datastore, DatastoreEntry
import platform

@unittest.skip("Incomplete")
class TestDeviceHandler(unittest.TestCase):

    def setUp(self):
        ds = Datastore()
        firmware_desc_file = None
        self.device_handler = DeviceHandler(ds, firmware_desc_file)

        if platform.system() == 'Windows':
            exec_name = 'testapp_winx64_msvc.exe'
        else:
            #todo
            raise NotImplementedError('Unsupported OS for now')

        params = {
            'cmd' : os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_artifact', exec_name),
            'args' : 'pipe'
        }

        self.device_handler.connect('subprocess', params)
        #todo.       