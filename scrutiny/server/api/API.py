#    API.py
#        Manages the websocket API to talk with the multiple clients. Can be a GUI client
#        or a CLI client
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import logging
import traceback
import math

from scrutiny.server.datastore.datastore import Datastore
from scrutiny.server.datastore.datastore_entry import EntryType
from scrutiny.server.datastore.datastore_entry import DatastoreEntry, UpdateTargetRequestCallback, UpdateTargetRequest
from scrutiny.server.device.device_handler import DeviceHandler
from scrutiny.server.active_sfd_handler import ActiveSFDHandler, SFDLoadedCallback, SFDUnloadedCallback
from scrutiny.server.device.links import LinkConfig
from scrutiny.core.sfd_storage import SFDStorage
from scrutiny.core.variable import EmbeddedDataType
from scrutiny.core.firmware_description import FirmwareDescription

from .websocket_client_handler import WebsocketClientHandler
from .dummy_client_handler import DummyClientHandler
from .value_streamer import ValueStreamer
import scrutiny.server.api.typing as api_typing

from .abstract_client_handler import AbstractClientHandler, ClientHandlerMessage
from scrutiny.server.device.links.abstract_link import LinkConfig as DeviceLinkConfig

from scrutiny.core.typehints import EmptyDict, GenericCallback
from typing import Callable, Dict, List, Set, Any, TypedDict, cast, Optional, Literal


class APIConfig(TypedDict, total=False):
    client_interface_type: str
    client_interface_config: Any


class UpdateVarCallback(GenericCallback):
    callback: Callable[[str, DatastoreEntry], None]


class TargetUpdateCallback(GenericCallback):
    callback: Callable[[str, DatastoreEntry], None]


class InvalidRequestException(Exception):
    def __init__(self, req, msg):
        super().__init__(msg)
        self.req = req


class API:

    # List of commands that can be shared with the clients
    class Command:
        class Client2Api:
            ECHO = 'echo'
            GET_WATCHABLE_LIST = 'get_watchable_list'
            GET_WATCHABLE_COUNT = 'get_watchable_count'
            SUBSCRIBE_WATCHABLE = 'subscribe_watchable'
            UNSUBSCRIBE_WATCHABLE = 'unsubscribe_watchable'
            GET_INSTALLED_SFD = 'get_installed_sfd'
            GET_LOADED_SFD = 'get_loaded_sfd'
            LOAD_SFD = 'load_sfd'
            GET_SERVER_STATUS = 'get_server_status'
            SET_LINK_CONFIG = "set_link_config"
            GET_POSSIBLE_LINK_CONFIG = "get_possible_link_config"   # todo
            WRITE_VALUE = "write_value"
            DEBUG = 'debug'

        class Api2Client:
            ECHO_RESPONSE = 'response_echo'
            GET_WATCHABLE_LIST_RESPONSE = 'response_get_watchable_list'
            GET_WATCHABLE_COUNT_RESPONSE = 'response_get_watchable_count'
            SUBSCRIBE_WATCHABLE_RESPONSE = 'response_subscribe_watchable'
            UNSUBSCRIBE_WATCHABLE_RESPONSE = 'response_unsubscribe_watchable'
            WATCHABLE_UPDATE = 'watchable_update'
            GET_INSTALLED_SFD_RESPONSE = 'response_get_installed_sfd'
            GET_LOADED_SFD_RESPONSE = 'response_get_loaded_sfd'
            GET_POSSIBLE_LINK_CONFIG_RESPONSE = "response_get_possible_link_config"
            SET_LINK_CONFIG_RESPONSE = 'set_link_config_response'
            INFORM_SERVER_STATUS = 'inform_server_status'
            WRITE_VALUE_RESPONSE = 'response_write_value'
            INFORM_WRITE_COMPLETION = 'inform_write_completion'
            ERROR_RESPONSE = 'error'

    FLUSH_VARS_TIMEOUT: float = 0.1

    data_type_to_str: Dict[EmbeddedDataType, str] = {
        EmbeddedDataType.sint8: 'sint8',
        EmbeddedDataType.sint16: 'sint16',
        EmbeddedDataType.sint32: 'sint32',
        EmbeddedDataType.sint64: 'sint64',
        EmbeddedDataType.sint128: 'sint128',
        EmbeddedDataType.sint256: 'sint256',
        EmbeddedDataType.uint8: 'uint8',
        EmbeddedDataType.uint16: 'uint16',
        EmbeddedDataType.uint32: 'uint32',
        EmbeddedDataType.uint64: 'uint64',
        EmbeddedDataType.uint128: 'uint128',
        EmbeddedDataType.uint256: 'uint256',
        EmbeddedDataType.float8: 'float8',
        EmbeddedDataType.float16: 'float16',
        EmbeddedDataType.float32: 'float32',
        EmbeddedDataType.float64: 'float64',
        EmbeddedDataType.float128: 'float128',
        EmbeddedDataType.float256: 'float256',
        EmbeddedDataType.cfloat8: 'cfloat8',
        EmbeddedDataType.cfloat16: 'cfloat16',
        EmbeddedDataType.cfloat32: 'cfloat32',
        EmbeddedDataType.cfloat64: 'cfloat64',
        EmbeddedDataType.cfloat128: 'cfloat128',
        EmbeddedDataType.cfloat256: 'cfloat256',
        EmbeddedDataType.boolean: 'boolean'
    }

    device_conn_status_to_str: Dict[DeviceHandler.ConnectionStatus, str] = {
        DeviceHandler.ConnectionStatus.UNKNOWN: 'unknown',
        DeviceHandler.ConnectionStatus.DISCONNECTED: 'disconnected',
        DeviceHandler.ConnectionStatus.CONNECTING: 'connecting',
        DeviceHandler.ConnectionStatus.CONNECTED_NOT_READY: 'connected',
        DeviceHandler.ConnectionStatus.CONNECTED_READY: 'connected_ready'
    }

    str_to_entry_type: Dict[str, EntryType] = {
        'var': EntryType.Var,
        'alias': EntryType.Alias,
        'rpv': EntryType.RuntimePublishedValue
    }

    datastore: Datastore
    device_handler: DeviceHandler
    logger: logging.Logger
    connections: Set[str]
    streamer: ValueStreamer
    req_count: int
    client_handler: AbstractClientHandler
    sfd_handler: ActiveSFDHandler

    # The method to call for each command
    ApiRequestCallbacks: Dict[str, str] = {
        Command.Client2Api.ECHO: 'process_echo',
        Command.Client2Api.GET_WATCHABLE_LIST: 'process_get_watchable_list',
        Command.Client2Api.GET_WATCHABLE_COUNT: 'process_get_watchable_count',
        Command.Client2Api.SUBSCRIBE_WATCHABLE: 'process_subscribe_watchable',
        Command.Client2Api.UNSUBSCRIBE_WATCHABLE: 'process_unsubscribe_watchable',
        Command.Client2Api.GET_INSTALLED_SFD: 'process_get_installed_sfd',
        Command.Client2Api.LOAD_SFD: 'process_load_sfd',
        Command.Client2Api.GET_LOADED_SFD: 'process_get_loaded_sfd',
        Command.Client2Api.GET_SERVER_STATUS: 'process_get_server_status',
        Command.Client2Api.SET_LINK_CONFIG: 'process_set_link_config',
        Command.Client2Api.GET_POSSIBLE_LINK_CONFIG: 'process_get_possible_link_config',
        Command.Client2Api.WRITE_VALUE: 'process_write_value'

    }

    def __init__(self, config: APIConfig, datastore: Datastore, device_handler: DeviceHandler, sfd_handler: ActiveSFDHandler, enable_debug: bool = False):
        self.validate_config(config)

        if config['client_interface_type'] == 'websocket':
            self.client_handler = WebsocketClientHandler(config['client_interface_config'])
        elif config['client_interface_type'] == 'dummy':
            self.client_handler = DummyClientHandler(config['client_interface_config'])
        else:
            raise NotImplementedError('Unsupported client interface type. %s', config['client_interface_type'])

        self.datastore = datastore
        self.device_handler = device_handler
        self.sfd_handler = sfd_handler
        self.logger = logging.getLogger('scrutiny.' + self.__class__.__name__)
        self.connections = set()            # Keep a list of all clients connections
        self.streamer = ValueStreamer()     # The value streamer takes cares of publishing values to the client without polling.
        self.req_count = 0

        self.enable_debug = enable_debug

        if enable_debug:
            import ipdb  # type: ignore
            API.Command.Client2Api.DEBUG = 'debug'
            self.ApiRequestCallbacks[API.Command.Client2Api.DEBUG] = 'process_debug'

        self.sfd_handler.register_sfd_loaded_callback(SFDLoadedCallback(self.sfd_loaded_callback))
        self.sfd_handler.register_sfd_unloaded_callback(SFDUnloadedCallback(self.sfd_unloaded_callback))

    @classmethod
    def get_datatype_name(cls, datatype: EmbeddedDataType) -> str:
        if datatype not in cls.data_type_to_str:
            raise ValueError('Unknown datatype : %s' % (str(datatype)))

        return cls.data_type_to_str[datatype]

    def sfd_loaded_callback(self, sfd: FirmwareDescription):
        # Called when a SFD is loaded after a device connection
        for conn_id in self.connections:
            self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=self.craft_inform_server_status_response()))

    def sfd_unloaded_callback(self):
        # Called when a SFD is unloaded (device disconnected)
        for conn_id in self.connections:
            self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=self.craft_inform_server_status_response()))

    def get_client_handler(self) -> AbstractClientHandler:
        return self.client_handler

    def open_connection(self, conn_id: str) -> None:
        self.connections.add(conn_id)
        self.streamer.new_connection(conn_id)

    def close_connection(self, conn_id: str) -> None:
        self.datastore.stop_watching_all(conn_id)   # Removes this connection as a watcher from all entries
        self.connections.remove(conn_id)
        self.streamer.clear_connection(conn_id)

    def is_new_connection(self, conn_id: str) -> bool:
        # Tells if a connection ID is new (not known)
        return True if conn_id not in self.connections else False

    # Extract a chunk of data from the value streamer and send it to the clients.
    def stream_all_we_can(self) -> None:
        for conn_id in self.connections:
            chunk = self.streamer.get_stream_chunk(conn_id)     # get a list of entry to send to this connection

            if len(chunk) == 0:
                continue

            msg: api_typing.S2C.WatchableUpdate = {
                'cmd': self.Command.Api2Client.WATCHABLE_UPDATE,
                'reqid': None,
                'updates': [dict(id=x.get_id(), value=x.get_value()) for x in chunk]
            }

            self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=msg))

    def validate_config(self, config: APIConfig):
        if 'client_interface_type' not in config:
            raise ValueError('Missing entry in API config : client_interface_type ')

        if 'client_interface_config' not in config:
            raise ValueError('Missing entry in API config : client_interface_config')

    # Launch the client interface handler
    def start_listening(self) -> None:
        self.client_handler.start()

    # to be called periodically
    def process(self) -> None:
        self.client_handler.process()   # Get incoming requests
        while self.client_handler.available():
            popped = self.client_handler.recv()
            assert popped is not None  # make mypy happy
            conn_id = popped.conn_id
            obj = cast(api_typing.C2SMessage, popped.obj)

            if self.is_new_connection(conn_id):
                self.logger.debug('Opening connection %s' % conn_id)
                self.open_connection(conn_id)

            self.process_request(conn_id, obj)

        # Close  dead connections
        conn_to_close = [conn_id for conn_id in self.connections if not self.client_handler.is_connection_active(conn_id)]
        for conn_id in conn_to_close:
            self.logger.debug('Closing connection %s' % conn_id)
            self.close_connection(conn_id)

        self.streamer.process()     # Decides which message needs to go out
        self.stream_all_we_can()    # Gives the message to the client handler
        self.client_handler.process()  # Give a chance to outgoing message to be written to output buffer

    # Process a request gotten from the Client Handler

    def process_request(self, conn_id: str, req: api_typing.C2SMessage):
        # Handle an incoming request from the client handler
        try:
            self.req_count += 1
            self.logger.debug('[Conn:%s] Processing request #%d - %s' % (conn_id, self.req_count, req))

            if 'cmd' not in req:
                raise InvalidRequestException(req, 'No command in request')

            cmd = req['cmd']

            if not isinstance(cmd, str):
                raise InvalidRequestException(req, 'cmd is not a valid string')

            # Fetch the right function from a global dict and call it
            # Response are sent in each callback. Not all requests requires a response
            if cmd in self.ApiRequestCallbacks:
                callback = getattr(self, self.ApiRequestCallbacks[cmd])
                callback.__call__(conn_id, req)
            else:
                raise InvalidRequestException(req, 'Unsupported command %s' % cmd)

        except InvalidRequestException as e:
            # Client sent a bad request. Controlled error
            self.logger.debug('[Conn:%s] Invalid request #%d. %s' % (conn_id, self.req_count, str(e)))
            response = self.make_error_response(req, str(e))
            self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))
        except Exception as e:
            # Unknown internal error
            self.logger.error('[Conn:%s] Unexpected error while processing request #%d. %s' % (conn_id, self.req_count, str(e)))
            self.logger.debug(traceback.format_exc())
            response = self.make_error_response(req, 'Internal error')
            self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    def process_debug(self, conn_id: str, req: Dict[Any, Any]) -> None:
        # Start ipdb tracing upon reception of a "debug" message (if enabled)
        if self.enable_debug:
            import ipdb  # type: ignore
            ipdb.set_trace()

    # === ECHO ====
    def process_echo(self, conn_id: str, req: api_typing.C2S.Echo) -> None:
        if 'payload' not in req:
            raise InvalidRequestException(req, 'Missing payload')
        response: api_typing.S2C.Echo = {
            'cmd': self.Command.Api2Client.ECHO_RESPONSE,
            'reqid': self.get_req_id(req),
            'payload': req['payload']
        }
        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    #  ===  GET_WATCHABLE_LIST     ===
    def process_get_watchable_list(self, conn_id: str, req: api_typing.C2S.GetWatchableList) -> None:
        # Improvement : This may be a big response. Generate multi-packet response in a worker thread
        # Not asynchronous by choice
        max_per_response = None
        if 'max_per_response' in req:
            if not isinstance(req['max_per_response'], int):
                raise InvalidRequestException(req, 'Invalid max_per_response content')

            max_per_response = req['max_per_response']

        type_to_include: List[EntryType] = []
        if self.is_dict_with_key(cast(Dict, req), 'filter'):
            if self.is_dict_with_key(cast(Dict, req['filter']), 'type'):
                if isinstance(req['filter']['type'], list):
                    for t in req['filter']['type']:
                        if t not in self.str_to_entry_type:
                            raise InvalidRequestException(req, 'Unsupported type filter :"%s"' % (t))

                        type_to_include.append(self.str_to_entry_type[t])

        if len(type_to_include) == 0:
            type_to_include = [EntryType.Var, EntryType.Alias, EntryType.RuntimePublishedValue]

        # Sends RPV first, variable last
        priority = [EntryType.RuntimePublishedValue, EntryType.Alias, EntryType.Var]

        entries = {}
        for entry_type in priority:  # TODO : Improve this not to copy the whole datastore while sending. Use a generator instead
            entries[entry_type] = self.datastore.get_entries_list_by_type(entry_type) if entry_type in type_to_include else []

        done = False

        while not done:
            if max_per_response is None:
                entries_to_send = entries
                done = True
            else:
                count = 0
                entries_to_send = {
                    EntryType.RuntimePublishedValue: [],
                    EntryType.Alias: [],
                    EntryType.Var: []
                }

                for entry_type in priority:
                    n = min(max_per_response - count, len(entries[entry_type]))
                    entries_to_send[entry_type] = entries[entry_type][0:n]
                    entries[entry_type] = entries[entry_type][n:]
                    count += n

                remaining = 0
                for entry_type in entries:
                    remaining += len(entries[entry_type])

                done = (remaining == 0)

            response: api_typing.S2C.GetWatchableList = {
                'cmd': self.Command.Api2Client.GET_WATCHABLE_LIST_RESPONSE,
                'reqid': self.get_req_id(req),
                'qty': {
                    'var': len(entries_to_send[EntryType.Var]),
                    'alias': len(entries_to_send[EntryType.Alias]),
                    'rpv': len(entries_to_send[EntryType.RuntimePublishedValue])
                },
                'content': {
                    'var': [self.make_datastore_entry_definition_no_type(x) for x in entries_to_send[EntryType.Var]],
                    'alias': [self.make_datastore_entry_definition_no_type(x) for x in entries_to_send[EntryType.Alias]],
                    'rpv': [self.make_datastore_entry_definition_no_type(x) for x in entries_to_send[EntryType.RuntimePublishedValue]]
                },
                'done': done
            }

            self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    #  ===  GET_WATCHABLE_COUNT ===
    def process_get_watchable_count(self, conn_id: str, req: api_typing.C2S.GetWatchableCount) -> None:
        # Returns the number of watchable per type
        response: api_typing.S2C.GetWatchableCount = {
            'cmd': self.Command.Api2Client.GET_WATCHABLE_COUNT_RESPONSE,
            'reqid': self.get_req_id(req),
            'qty': {
                'var': self.datastore.get_entries_count(EntryType.Var),
                'alias': self.datastore.get_entries_count(EntryType.Alias),
                'rpv': self.datastore.get_entries_count(EntryType.RuntimePublishedValue),
            }
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    #  ===  SUBSCRIBE_WATCHABLE ===
    def process_subscribe_watchable(self, conn_id: str, req: api_typing.C2S.SubscribeWatchable) -> None:
        # Add the connection ID to the list of watchers of given datastore entries.
        # datastore callback will write the new values in the API output queue (through the value streamer)
        if 'watchables' not in req and not isinstance(req['watchables'], list):
            raise InvalidRequestException(req, 'Invalid or missing watchables list')

        # Check existence of all watchable before doing anything.
        for watchable in req['watchables']:
            try:
                self.datastore.get_entry(watchable)  # Will raise an exception if not existant
            except KeyError as e:
                raise InvalidRequestException(req, 'Unknown watchable ID : %s' % str(watchable))

        for watchable in req['watchables']:
            self.datastore.start_watching(
                entry_id=watchable,
                watcher=conn_id,    # We use the API connection ID as datastore watcher ID
                value_change_callback=UpdateVarCallback(self.entry_value_change_callback)
            )

        response: api_typing.S2C.SubscribeWatchable = {
            'cmd': self.Command.Api2Client.SUBSCRIBE_WATCHABLE_RESPONSE,
            'reqid': self.get_req_id(req),
            'watchables': req['watchables']
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    #  ===  UNSUBSCRIBE_WATCHABLE ===
    def process_unsubscribe_watchable(self, conn_id: str, req: api_typing.C2S.UnsubscribeWatchable) -> None:
        # Unsubscribe client from value update of the given datastore entries
        if 'watchables' not in req and not isinstance(req['watchables'], list):
            raise InvalidRequestException(req, 'Invalid or missing watchables list')

        # Check existence of all entries before doing anything
        for watchable in req['watchables']:
            try:
                self.datastore.get_entry(watchable)  # Will raise an exception if not existant
            except KeyError as e:
                raise InvalidRequestException(req, 'Unknown watchable ID : %s' % str(watchable))

        for watchable in req['watchables']:
            self.datastore.stop_watching(watchable, watcher=conn_id)

        response: api_typing.S2C.UnsubscribeWatchable = {
            'cmd': self.Command.Api2Client.SUBSCRIBE_WATCHABLE_RESPONSE,
            'reqid': self.get_req_id(req),
            'watchables': req['watchables']
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    #  ===  GET_INSTALLED_SFD ===
    def process_get_installed_sfd(self, conn_id: str, req: api_typing.C2S.GetInstalledSFD):
        # Request to know the list of installed Scrutiny Firmware Description on this server
        firmware_id_list = SFDStorage.list()
        metadata_dict = {}
        for firmware_id in firmware_id_list:
            metadata_dict[firmware_id] = SFDStorage.get_metadata(firmware_id)

        response: api_typing.S2C.GetInstalledSFD = {
            'cmd': self.Command.Api2Client.GET_INSTALLED_SFD_RESPONSE,
            'reqid': self.get_req_id(req),
            'sfd_list': metadata_dict
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    #  ===  GET_LOADED_SFD ===
    def process_get_loaded_sfd(self, conn_id: str, req: api_typing.C2S.GetLoadedSFD):
        # Request to get the actively loaded Scrutiny Firmware Description. Loaded by the SFD Handler
        # pon connection with a known device
        sfd = self.sfd_handler.get_loaded_sfd()

        response: api_typing.S2C.GetLoadedSFD = {
            'cmd': self.Command.Api2Client.GET_LOADED_SFD_RESPONSE,
            'reqid': self.get_req_id(req),
            'firmware_id': sfd.get_firmware_id_ascii() if sfd is not None else None
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    #  ===  LOAD_SFD ===
    def process_load_sfd(self, conn_id: str, req: api_typing.C2S.LoadSFD):
        # Forcibly load a Scrutiny Firmware Descritpion through API
        if 'firmware_id' not in req and not isinstance(req['firmware_id'], str):
            raise InvalidRequestException(req, 'Invalid firmware_id')

        try:
            self.sfd_handler.request_load_sfd(req['firmware_id'])
        except Exception as e:
            self.logger.error('Cannot load SFD %s. %s' % (req['firmware_id'], str(e)))
        # Do not send a response. There's a callback on SFD Loading that will notfy everyone once completed.

    #  ===  GET_SERVER_STATUS ===
    def process_get_server_status(self, conn_id: str, req: api_typing.C2S.GetServerStatus):
        # Request the server status.
        obj = self.craft_inform_server_status_response(reqid=self.get_req_id(req))
        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=obj))

    #  ===  SET_LINK_CONFIG ===
    def process_set_link_config(self, conn_id: str, req: api_typing.C2S.SetLinkConfig):
        # With this request, the user can change the device connection through an API call
        if 'link_type' not in req or not isinstance(req['link_type'], str):
            raise InvalidRequestException(req, 'Invalid link_type')

        if 'link_config' not in req or not isinstance(req['link_config'], dict):
            raise InvalidRequestException(req, 'Invalid link_config')

        link_config_err: Optional[Exception] = None
        try:
            self.device_handler.validate_link_config(req['link_type'], cast(DeviceLinkConfig, req['link_config']))
        except Exception as e:
            link_config_err = e

        if link_config_err:
            raise InvalidRequestException(req, "Link configuration is not good for given link type. " + str(link_config_err))

        self.device_handler.configure_comm(req['link_type'], cast(LinkConfig, req['link_config']))

        response: api_typing.S2C.Empty = {
            'cmd': self.Command.Api2Client.SET_LINK_CONFIG_RESPONSE,
            'reqid': self.get_req_id(req)
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    #  todo
    def process_get_possible_link_config(self, conn_id: str, req: api_typing.C2S.GetPossibleLinkConfig):
        configs = []

        udp_config = {
            'name': 'udp',
            'params': {
                'host': {
                    'description': 'UDP Hostname or IP address',
                    'default': 'localhost',
                    'type': 'string'
                },
                'port': {
                    'description': 'UDP port',
                    'default': 8765,
                    'type': 'int',
                    'range': {'min': 0, 'max': 65535}
                }
            }
        }

        configs.append(udp_config)

        try:
            import serial.tools.list_ports  # type: ignore
            ports = serial.tools.list_ports.comports()
            portname_list: List[str] = [] if ports is None else [port.device for port in ports]

            serial_config = {
                'name': 'serial',
                'params': {
                    'portname': {
                        'description': 'Serial port name',
                        'type': 'select',
                        'text-edit': True,
                        'values': portname_list
                    },
                    'baudrate': {
                        'description': 'Speed transmission in Baud/s (bit/s)',
                        'default': 115200,
                        'type': 'select',
                        'text-edit': True,
                        'values': [
                            1200,
                            2400,
                            4800,
                            9600,
                            14400,
                            19200,
                            28800,
                            38400,
                            57600,
                            115200,
                            230400
                        ]
                    },
                    'stopbits': {
                        'description': 'Number of stop bits',
                        'type': 'select',
                        'values': [1, 1.5, 2]
                    },
                    'databits': {
                        'description': 'Number of data bits',
                        'default': 5,
                        'type': 'select',
                        'values': [5, 6, 7, 8]
                    },
                    'parity': {
                        'description': 'Parity validation',
                        'default': 'none',
                        'type': 'select',
                        'values': ['none', 'even', 'odd', 'mark', 'space']
                    }
                }
            }

            configs.append(serial_config)
        except Exception as e:
            self.logger.debug('Serial communication not possible.\n' + traceback.format_exc())

        response: api_typing.S2C.GetPossibleLinkConfig = {
            'cmd': self.Command.Api2Client.GET_POSSIBLE_LINK_CONFIG_RESPONSE,
            'reqid': self.get_req_id(req),
            'configs': configs
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    #  ===  WRITE_VALUE ===
    def process_write_value(self, conn_id: str, req: api_typing.C2S.WriteValue) -> None:
        # We first fetch the entries as it will raise an exception if the ID does not exist
        # We don't want to trigger a write if an entry is bad in the request
        if 'updates' not in req:
            raise InvalidRequestException(req, 'Missing "updates" field')

        if not isinstance(req['updates'], list):
            raise InvalidRequestException(req, 'Invalid "updates" field')

        for update in req['updates']:
            if 'watchable' not in update:
                raise InvalidRequestException(req, 'Missing "watchable" field')

            if 'value' not in update:
                raise InvalidRequestException(req, 'Missing "value" field')

            if not isinstance(update['watchable'], str):
                raise InvalidRequestException(req, 'Invalid "watchable" field')

            value = update['value']
            if isinstance(value, str):
                valstr = value.lower().strip()
                if valstr == "true":
                    value = True
                elif valstr == "false":
                    value = False
                elif valstr.startswith("0x"):
                    value = int(valstr[2:], 16)
                elif valstr.startswith("-0x"):
                    value = -int(valstr[3:], 16)
                else:
                    try:
                        value = float(valstr)
                    except:
                        value = None
            if value is None or not isinstance(value, int) and not isinstance(value, float) and not isinstance(value, bool):
                raise InvalidRequestException(req, 'Invalid "value" field')
            if not math.isfinite(value):
                raise InvalidRequestException(req, 'Invalid "value" field')
            update['value'] = value

            try:
                entry = self.datastore.get_entry(update['watchable'])
            except Exception as e:
                raise InvalidRequestException(req, 'Unknown watchable ID %s' % update['watchable'])

            if not self.datastore.is_watching(entry, conn_id):
                raise InvalidRequestException(req, 'Cannot update entry %s without being subscribed to it' % entry.get_id())

        for update in req['updates']:
            entry = self.datastore.get_entry(update['watchable'])
            entry.update_target_value(update['value'], callback=UpdateTargetRequestCallback(self.entry_target_update_callback))

        response: api_typing.S2C.WriteValue = {
            'cmd': self.Command.Api2Client.WRITE_VALUE_RESPONSE,
            'reqid': self.get_req_id(req),
            'watchables': [update['watchable'] for update in req['updates']]
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    def craft_inform_server_status_response(self, reqid: Optional[int] = None) -> api_typing.S2C.InformServerStatus:
        # Make a Server to client message that inform the actual state of the server
        # Qeury the state of all subpart of the software.
        sfd = self.sfd_handler.get_loaded_sfd()
        device_link_type = self.device_handler.get_link_type()
        device_comm_link = self.device_handler.get_comm_link()
        device_info_input = self.device_handler.get_device_info()

        loaded_sfd: Optional[api_typing.SFDEntry] = None
        if sfd is not None:
            loaded_sfd = {
                "firmware_id": str(sfd.get_firmware_id_ascii()),
                "metadata": sfd.get_metadata()
            }

        device_info: Optional[api_typing.DeviceInfo] = None
        if device_info_input is not None and device_info_input.all_ready():
            device_info = {
                'device_id': cast(str, device_info_input.device_id),
                'display_name': cast(str, device_info_input.display_name),
                'max_tx_data_size': cast(int, device_info_input.max_tx_data_size),
                'max_rx_data_size': cast(int, device_info_input.max_rx_data_size),
                'max_bitrate_bps': cast(int, device_info_input.max_bitrate_bps),
                'rx_timeout_us': cast(int, device_info_input.rx_timeout_us),
                'heartbeat_timeout_us': cast(int, device_info_input.heartbeat_timeout_us),
                'address_size_bits': cast(int, device_info_input.address_size_bits),
                'protocol_major': cast(int, device_info_input.protocol_major),
                'protocol_minor': cast(int, device_info_input.protocol_minor),
                'supported_feature_map': cast(Dict[str, bool], device_info_input.supported_feature_map),
                'forbidden_memory_regions': cast(List[Dict[str, int]], device_info_input.forbidden_memory_regions),
                'readonly_memory_regions': cast(List[Dict[str, int]], device_info_input.readonly_memory_regions)
            }

        if device_comm_link is None:
            link_config = cast(EmptyDict, {})
        else:
            link_config = cast(api_typing.LinkConfig, device_comm_link.get_config())
        response: api_typing.S2C.InformServerStatus = {
            'cmd': self.Command.Api2Client.INFORM_SERVER_STATUS,
            'reqid': reqid,
            'device_status': self.device_conn_status_to_str[self.device_handler.get_connection_status()],
            'device_info': device_info,
            'loaded_sfd': loaded_sfd,
            'device_comm_link': {
                'link_type': cast(api_typing.LinkType, device_link_type),
                'link_config': link_config
            }
        }

        return response

    def entry_value_change_callback(self, conn_id: str, datastore_entry: DatastoreEntry) -> None:
        # This callback is given to the datastore when we a client start watching an entry.
        self.streamer.publish(datastore_entry, conn_id)
        self.stream_all_we_can()

    def entry_target_update_callback(self, success: bool, datastore_entry: DatastoreEntry, timestamp: float) -> None:
        # This callback is given to the datastore when we make a write request (target update request)
        # It will be called once the request is completed.
        watchers = self.datastore.get_watchers(datastore_entry)

        msg: api_typing.S2C.WriteCompletion = {
            'cmd': self.Command.Api2Client.INFORM_WRITE_COMPLETION,
            'reqid': None,
            'watchable': datastore_entry.get_id(),
            'status': "ok" if success else "failed",
            'timestamp': timestamp
        }

        for watcher_conn_id in watchers:
            self.client_handler.send(ClientHandlerMessage(conn_id=watcher_conn_id, obj=msg))

    def make_datastore_entry_definition_no_type(self, entry: DatastoreEntry) -> api_typing.DatastoreEntryDefinitionNoType:
        # Craft the data structure sent by the API to give the available watchables
        definition: api_typing.DatastoreEntryDefinitionNoType = {
            'id': entry.get_id(),
            'display_path': entry.get_display_path(),
            'datatype': self.get_datatype_name(entry.get_data_type())
        }

        if entry.has_enum():
            enum = entry.get_enum()
            assert enum is not None
            enum_def = enum.get_def()
            definition['enum'] = {  # Cherry pick items to avoid sending too much to client
                'name': enum.get_name(),
                'values': enum_def['values']
            }

        return definition

    def make_error_response(self, req: api_typing.C2SMessage, msg: str) -> api_typing.S2C.Error:
        # craft a standardized error message
        cmd = '<empty>'
        if 'cmd' in req:
            cmd = req['cmd']

        response: api_typing.S2C.Error = {
            'cmd': self.Command.Api2Client.ERROR_RESPONSE,
            'reqid': self.get_req_id(req),
            'request_cmd': cmd,
            'msg': msg
        }
        return response

    def get_req_id(self, req: api_typing.C2SMessage) -> Optional[int]:
        return req['reqid'] if 'reqid' in req else None

    def is_dict_with_key(self, d: Dict[Any, Any], k: Any):
        return isinstance(d, dict) and k in d

    def close(self) -> None:
        self.client_handler.stop()
