#    server.py
#        The scrutiny server. Talk with multiple clients through a websocket API and communicate
#        with a device through a given communication link (Serial, UDP, etc)
#        Allow the clients to interract with the device
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import sys
import os
import time
import json
import logging
import traceback
from copy import copy

from scrutiny.server.api import API, APIConfig
from scrutiny.server.datastore import Datastore
from scrutiny.server.device.device_handler import DeviceHandler, DeviceHandlerConfig
from scrutiny.server.active_sfd_handler import ActiveSFDHandler

from typing import TypedDict, Optional


class ServerConfig(TypedDict, total=False):
    name: str
    autoload_sfd: bool
    debug: bool
    device_config: DeviceHandlerConfig
    api_config: APIConfig


DEFAULT_CONFIG: ServerConfig = {
    'name': 'Scrutiny Server (Default config)',
    'autoload_sfd': True,
    'debug': False,    # Requires ipdb. Module must be installed with [dev] extras
    'api_config': {
        'client_interface_type': 'websocket',
        'client_interface_config': {
            'host': 'localhost',
            'port': 8765
        }
    },
    'device_config': {
        'response_timeout': 1.0,
        'link_type': 'none',
        'link_config': {
        }
    }
}


class ScrutinyServer:
    server_name: str
    logger: logging.Logger
    config: ServerConfig
    datastore: Datastore
    api: API
    device_handler: DeviceHandler
    sfd_handler: ActiveSFDHandler

    def __init__(self, config_filename: str = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = copy(DEFAULT_CONFIG)
        if config_filename is not None:
            self.logger.debug('Loading user configuration file: "%s"' % config_filename)
            del self.config['name']  # remove "default config" from name
            with open(config_filename) as f:
                try:
                    user_cfg = json.loads(f.read())
                    self.config.update(user_cfg)
                except Exception as e:
                    raise Exception("Invalid configuration JSON. %s" % e)

        self.validate_config()
        self.server_name = '<Unnamed>' if 'name' not in self.config else self.config['name']

        self.datastore = Datastore()
        self.device_handler = DeviceHandler(self.config['device_config'], self.datastore)
        self.sfd_handler = ActiveSFDHandler(device_handler=self.device_handler, datastore=self.datastore, autoload=self.config['autoload_sfd'])
        self.api = API(self.config['api_config'], datastore=self.datastore, device_handler=self.device_handler,
                       sfd_handler=self.sfd_handler, enable_debug=self.config['debug'])

    def validate_config(self) -> None:
        pass

    def run(self) -> None:
        self.logger.info('Starting server instance "%s"' % (self.server_name))

        try:
            self.api.start_listening()
            self.sfd_handler.init()
            while True:
                self.api.process()
                self.device_handler.process()
                self.sfd_handler.process()

                time.sleep(0.05)
        except KeyboardInterrupt:
            self.close_all()
        except Exception as e:
            self.logger.error(str(e))
            self.logger.debug(''.join(traceback.format_exception(None, e, e.__traceback__)))
            self.close_all()
            raise

    def close_all(self) -> None:
        if self.api is not None:
            self.api.close()

        if self.device_handler is not None:
            self.device_handler.stop_comm()

        if self.sfd_handler is not None:
            self.sfd_handler.close()

        self.logger.info('Closing server instance "%s"' % self.server_name)
