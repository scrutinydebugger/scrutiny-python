#    server.py
#        The scrutiny server. Talk with multiple clients through a websocket API and communicate
#        with a device through a given communication link (Serial, UDP, etc)
#        Allow the clients to interact with the device
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import time
import os
import json
import logging
import traceback
from copy import copy

from scrutiny.server.api import API, APIConfig
from scrutiny.server.datastore.datastore import Datastore
from scrutiny.server.device.device_handler import DeviceHandler, DeviceHandlerConfig
from scrutiny.server.active_sfd_handler import ActiveSFDHandler
from scrutiny.server.datalogging.datalogging_manager import DataloggingManager

from typing import TypedDict, Optional, Union


class ServerConfig(TypedDict, total=False):
    """The server configuration definition loadable from json"""
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
    """The Scrutiny server that communicate with a device running libscrutiny-embedded and make
    the device internal data available through a multi-client websocket API"""
    server_name: str
    logger: logging.Logger
    config: ServerConfig
    datastore: Datastore
    api: API
    device_handler: DeviceHandler
    sfd_handler: ActiveSFDHandler
    datalogging_manager: DataloggingManager

    def __init__(self, input_config: Optional[Union[str, ServerConfig]] = None) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = copy(DEFAULT_CONFIG)
        if input_config is not None:
            if isinstance(input_config, str) and os.path.isfile(input_config):
                self.logger.debug('Loading user configuration file: "%s"' % input_config)
                del self.config['name']  # remove "default config" from name
                with open(input_config) as f:
                    try:
                        user_cfg = json.loads(f.read())
                        self.config.update(user_cfg)
                    except Exception as e:
                        raise Exception("Invalid configuration JSON. %s" % e)
            elif isinstance(input_config, dict):
                self.config.update(input_config)

        self.validate_config()
        self.server_name = '<Unnamed>' if 'name' not in self.config else self.config['name']

        self.datastore = Datastore()
        self.device_handler = DeviceHandler(self.config['device_config'], self.datastore)
        self.datalogging_manager = DataloggingManager(self.datastore, self.device_handler)
        self.sfd_handler = ActiveSFDHandler(device_handler=self.device_handler, datastore=self.datastore, autoload=self.config['autoload_sfd'])
        self.api = API(
            self.config['api_config'],
            datastore=self.datastore,
            device_handler=self.device_handler,
            sfd_handler=self.sfd_handler,
            datalogging_manager=self.datalogging_manager,
            enable_debug=self.config['debug'])

    def validate_config(self) -> None:
        if self.config['debug']:
            try:
                import ipdb  # type: ignore
            except ImportError:
                self.config['debug'] = False
                self.logger.warning('Cannot enable debug mode. ipdb module is not available.')

    def init(self) -> None:
        self.api.start_listening()
        self.sfd_handler.init()

    def process(self) -> None:
        self.api.process()
        self.datalogging_manager.process()
        self.device_handler.process()
        self.sfd_handler.process()

    def run(self) -> None:
        """Launch the server code. This function is blocking"""
        self.logger.info('Starting server instance "%s"' % (self.server_name))

        try:
            self.init()
            while True:
                self.process()
                time.sleep(0.01)
        except (KeyboardInterrupt, SystemExit):
            self.close_all()
        except Exception as e:
            self.logger.error(str(e))
            self.logger.debug(traceback.format_exc())
            self.close_all()
            raise

    def stop(self) -> None:
        """ An alias for close_all"""
        self.close_all()

    def close_all(self) -> None:
        """Terminate the server by closing all its resources"""
        if self.api is not None:
            self.api.close()

        if self.device_handler is not None:
            self.device_handler.stop_comm()

        if self.sfd_handler is not None:
            self.sfd_handler.close()

        self.logger.info('Closing server instance "%s"' % self.server_name)
