import sys, os
import time
import json
import logging
import traceback
from copy import copy

from scrutiny.server.api import API
from scrutiny.server.datastore import Datastore
from scrutiny.server.device import DeviceHandler

DEFAULT_CONFIG = {
    'name' : 'Scrutiny Server (Default config)',
    'api_config' : {
        'client_interface_type' : 'websocket',
        'client_interface_config' : {
            'host' : 'localhost',
            'port' : 8765            
        }
    },
    'device_config' : {
        'comm_response_timeout' : 1.0,
        'link_type' : 'none',
        'link_config' : {
        }
    }
}


class ScrutinyServer:

    def __init__(self, config=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = copy(DEFAULT_CONFIG)
        if config is not None:
            self.logger.debug('Loading user configuration file: "%s"' % config)
            del self.config['name'] # remove "default config" from name
            with open(config) as f:
                try:
                    user_cfg = json.loads(f.read())
                    self.config.update(user_cfg)
                except Exception as e:
                    raise Exception("Invalid configuration JSON. %s" % e)

        self.validate_config()

        self.theapi = None
        self.device_handler = None
        self.server_name =  '<Unnamed>' if 'name' not in self.config else self.config['name']
    
    def validate_config(self):
        pass

    def run(self):
        self.logger.info('Starting server instance "%s"' % (self.server_name))
        ds = Datastore()
        try:
            self.device_handler = DeviceHandler(self.config['device_config'], ds)
            self.api = API(self.config['api_config'], ds, self.device_handler)
            
            self.api.start_listening()
            self.device_handler.connect()
            while True:
                self.api.process()
                self.device_handler.process()
                time.sleep(0.05)
        except KeyboardInterrupt:
            self.close_all()
        except Exception as e:
            self.logger.error(str(e))
            self.logger.debug(traceback.format_exc())
            self.close_all()
            raise

    def close_all(self):
        if self.api is not None:
            self.api.close()

        if self.device_handler is not None:
            self.device_handler.disconnect()

        self.logger.info('Closing server instance "%s"' % self.server_name)
