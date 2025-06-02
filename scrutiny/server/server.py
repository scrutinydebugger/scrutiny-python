#    server.py
#        The scrutiny server. Talk with multiple clients through a TCP API and communicate
#        with a device through a given communication link (Serial, UDP, etc)
#        Allow the clients to interact with the device
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

__all__ = ['ScrutinyServer', 'ServerConfig', 'DEFAULT_CONFIG']

import time
import os
import json
import logging
import threading
from copy import copy
from dataclasses import dataclass

from scrutiny.server.api import API, APIConfig
from scrutiny.server.datastore.datastore import Datastore
from scrutiny.server.device.device_handler import DeviceHandler, DeviceHandlerConfig
from scrutiny.server.active_sfd_handler import ActiveSFDHandler
from scrutiny.server.datalogging.datalogging_manager import DataloggingManager
from scrutiny import tools
from scrutiny.tools.signals import SignalExitHandler

from scrutiny.tools.typing import *


class ServerConfig(TypedDict, total=False):
    """The server configuration definition loadable from json"""
    name: str
    autoload_sfd: bool
    debug: bool
    device: DeviceHandlerConfig
    api: APIConfig


DEFAULT_CONFIG: ServerConfig = {
    'name': 'Scrutiny Server (Default config)',
    'autoload_sfd': True,
    'debug': False,    # Requires ipdb. Module must be installed with [dev] extras
    'api': {
        'client_interface_type': 'tcp',
        'client_interface_config': {
            'host': '0.0.0.0',
            'port': 8765
        }
    },
    'device': {
        'response_timeout': 1.0,
        'link_type': 'none',
        'link_config': {
        }
    }
}


class ScrutinyServer:
    """The Scrutiny server that communicate with a device running libscrutiny-embedded and make
    the device internal data available through a multi-client socket API"""

    @dataclass(frozen=True)
    class Statistics:
        device: DeviceHandler.Statistics
        api: API.Statistics
        uptime: float

    server_name: str
    logger: logging.Logger
    config: ServerConfig
    datastore: Datastore
    api: API
    device_handler: DeviceHandler
    sfd_handler: ActiveSFDHandler
    datalogging_manager: DataloggingManager
    rx_data_event: threading.Event
    start_time: float
    stop_event: threading.Event

    def __init__(self,
                 input_config: Optional[Union[str, ServerConfig]] = None,
                 additional_config: Optional[ServerConfig] = None
                 ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = copy(DEFAULT_CONFIG)
        self.stop_event = threading.Event()
        if input_config is not None:
            if isinstance(input_config, str):
                if not os.path.isfile(input_config):
                    raise FileNotFoundError(f"Given config does not exist: {input_config}")

                self.logger.debug('Loading user configuration file: "%s"' % input_config)
                del self.config['name']  # remove "default config" from name
                with open(input_config) as f:
                    try:
                        user_cfg = json.loads(f.read())
                        tools.update_dict_recursive(cast(Dict[Any, Any], self.config), cast(Dict[Any, Any], user_cfg))
                    except Exception as e:
                        raise Exception("Invalid configuration JSON. %s" % e)
            elif isinstance(input_config, dict):
                tools.update_dict_recursive(cast(Dict[Any, Any], self.config), cast(Dict[Any, Any], input_config))

        if additional_config is not None:
            tools.update_dict_recursive(cast(Dict[Any, Any], self.config), cast(Dict[Any, Any], additional_config))

        self.validate_config()
        self.server_name = '<Unnamed>' if 'name' not in self.config else self.config['name']

        self.rx_data_event = threading.Event()
        self.datastore = Datastore()
        self.device_handler = DeviceHandler(
            config=self.config['device'],
            datastore=self.datastore,
            rx_event=self.rx_data_event
        )
        self.datalogging_manager = DataloggingManager(
            datastore=self.datastore,
            device_handler=self.device_handler
        )
        self.sfd_handler = ActiveSFDHandler(
            device_handler=self.device_handler,
            datastore=self.datastore,
            autoload=self.config['autoload_sfd']
        )
        self.api = API(
            self.config['api'],
            server=self,
            enable_debug=self.config['debug'],
            rx_event=self.rx_data_event
        )
        self.start_time = time.monotonic()

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
        exit_handler = SignalExitHandler()
        self.stop_event.clear()
        try:
            self.init()
            while True:
                if exit_handler.must_exit() or self.stop_event.is_set():
                    break
                self.process()
                self.rx_data_event.wait(0.01)   # sleep until we have some IO or 10ms
                self.rx_data_event.clear()
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception as e:
            tools.log_exception(self.logger, e, "Error in server", str_level=logging.CRITICAL)
            raise
        finally:
            self.close_all()

    def stop(self) -> None:
        """ Stop the server """
        self.stop_event.set()
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

    def get_stats(self) -> Statistics:
        """Return the server statistics"""
        return self.Statistics(
            device=self.device_handler.get_stats(),
            api=self.api.get_stats(),
            uptime=time.monotonic() - self.start_time
        )
