import sys, os
import time
import json
from copy import copy

from scrutiny.server.api import API
from scrutiny.server.datastore import Datastore
from scrutiny.server.device import DeviceHandler

DEFAULT_CONFIG = {
    'api_config' : {
        'client_interface_type' : 'websocket',
        'client_interface_config' : {
            'host' : 'localhost',
            'port' : 8765,
            'name' : 'Scrutiny Server (Default config)'
        },
    },
    'device_config' : {
        'comm_response_timeout' : 1.0,
        'link_type' : 'subprocess',
        'link_config' : {
            'cmd' : 'testapp',
            'args' : ['pipe']
        }
    }
}


class ScrutinyServer:

    def __init__(self, config=None):
        if config is None:
            self.config = copy(DEFAULT_CONFIG)
        else:
            self.config = json.loads(config)

        self.validate_config()
    
    def validate_config(self):
        pass

    def run(self):
        ds = Datastore()
        device_handler = DeviceHandler(self.config['device_config'], ds)
        theapi = API(self.config['api_config'], ds, device_handler)
        theapi.start_listening()
        device_handler.connect()

        try:
            while True:
                theapi.process()
                device_handler.process()
                time.sleep(0.05)
        except KeyboardInterrupt:
            device_handler.disconnect()
            theapi.close()
        except Exception as e:
            device_handler.disconnect()
            theapi.close()
            raise