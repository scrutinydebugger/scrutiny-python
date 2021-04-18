from .websocket_client_handler import WebsocketClientHandler
from .queue_client_handler import QueueClientHandler
from ..datastore import Datastore, DatastoreEntry
import logging
import numbers

class InvalidRequestException(Exception):
    def __init__(self, req, msg):
        super().__init__(self.msg)
        self.req = req


class API:
    
    entry_type_to_str = {
        DatastoreEntry.Type.eVar : 'var',
        DatastoreEntry.Type.eAlias : 'alias',
    }

    str_to_entry_type = {
        'var' : DatastoreEntry.Type.eVar,
        'alias' : DatastoreEntry.Type.eAlias
    }


    class Command:
        ECHO = 'echo'
        GET_WATCHABLE_LIST = 'get_watchable_list'
        GET_WATCHABLE_COUNT = 'get_watchable_count'

    class Response:
        ECHO = 'response_echo'
        GET_WATCHABLE_LIST = 'response_get_watchable_list'
        GET_WATCHABLE_COUNT = 'response_get_watchable_count'
        ERROR = 'error'

    def __init__(self, config, datastore):
        self.validate_config(config)

        if config['client_interface_type'] == 'websocket':
            self.handler = WebsocketClientHandler(config['client_interface_config'])
        elif config['client_interface_type'] == 'queue':
            self.handler = QueueClientHandler(config['client_interface_config'])
        else:
            raise NotImplementedError('Unsupported client interface type. %s' , config['client_interface_type'])

        self.datastore = datastore
        self.logger = logging.getLogger(self.__class__.__name__)

    def validate_config(self, config):
        if 'client_interface_type' not in config:
            raise ValueError('Missing entry in API config : client_interface_type ')

        if 'client_interface_config' not in config:
            raise ValueError('Missing entry in API config : client_interface_config')

    def start_listening(self):
        self.handler.start()

    def process(self):
        self.handler.process()
        while self.handler.available():
            popped = self.handler.recv()

            if 'obj' not in popped or 'conn_id' not in popped:
                continue

            conn_id = popped['conn_id']
            obj = popped['obj']

            try:
                self.process_request(conn_id, obj)
            except Exception as e:
                self.logger.error('Cannot process request. %s' % str(e))
                self.logger.debug('Conn ID: %s \n Data: %s' % (conn_id, str(obj)))

        self.process_tasks()

    def process_tasks(self):
        pass  # Do nothing for now.  Exist to run background task so that the API doesn't block

    def process_request(self, conn_id, req):
        try:
            if 'cmd' not in req:
                raise InvalidRequestException(req, 'No command in request')

            cmd = req['cmd']
            if cmd == self.Command.ECHO:
                self.process_echo(conn_id, req)
            elif cmd == self.Command.GET_WATCHABLE_LIST:
                self.process_get_watchable_list(conn_id, req)
            elif cmd == self.Command.GET_WATCHABLE_COUNT:
                self.process_get_watchable_count(conn_id, req)
            else:
                raise InvalidRequestException(req, 'Unsupported command %s' % cmd)
        
        except InvalidRequestException as e:
            response = self.make_error_response(req, e.message)
            self.handler.send(conn_id, response)
        except Exception as e:
            response = self.make_error_response(req, 'Internal error')
            self.handler.send(conn_id, response)
            raise


    def process_echo(self, conn_id, req):
        self.logger.debug('Processing Echo')
        response = dict(cmd=self.Response.ECHO, payload=req['payload'])
        self.handler.send(conn_id, response) 


    def process_get_watchable_list(self, conn_id, req):
        # Improvement : This may be a big response. Generate multi-packet response in a worker thread
        # Not asynchronous by choice 
        max_per_response = None
        if 'max_per_response' in req: 
            if not isinstance(req['max_per_response'], int):
                raise InvalidRequestException(req, 'Invalid max_per_response content')

            max_per_response = req['max_per_response']

        type_to_include = []
        if self.is_dict_with_key(req, 'filter'):
            if self.is_dict_with_key(req['filter'], 'type'):
                if isinstance(req['filter']['type'], list):
                    for t in req['filter']['type']:
                        if t not in self.str_to_entry_type:
                            raise InvalidRequestException(req, 'Insupported type filter :"%s"' % (t))
                    
                        type_to_include.append(self.str_to_entry_type[t])
        
        if len(type_to_include) == 0:
            type_to_include = [DatastoreEntry.Type.eVar, DatastoreEntry.Type.eAlias]
        
        variables   = self.datastore.get_entries_list_by_type(DatastoreEntry.Type.eVar)     if DatastoreEntry.Type.eVar     in type_to_include else []
        alias       = self.datastore.get_entries_list_by_type(DatastoreEntry.Type.eAlias)   if DatastoreEntry.Type.eAlias   in type_to_include else []

        done = False
        while not done:
            if max_per_response is None:
                alias_to_send = alias
                var_to_send = variables
                done = True
            else:
                nAlias = min(max_per_response, len(alias))
                alias_to_send = alias[0:nAlias]
                alias = alias[nAlias:]

                nVar = min(max_per_response - nAlias, len(variables))
                var_to_send = variables[0:nVar]
                variables=varaibles[nVar:]

                done = True if len(variables) + len(alias) == 0 else False

            response = {
                'cmd' : self.Response.GET_WATCHABLE_LIST,
                'qty' : {
                    'var' : len(var_to_send),
                    'alias' : len(alias_to_send)
                },
                'content' : {
                    'var' : [self.make_datastore_entry_definition(x) for x in var_to_send],
                    'alias' : [self.make_datastore_entry_definition(x) for x in alias_to_send]
                },
                'done' : done
            }

            self.handler.send(conn_id, response)

            
    def process_get_watchable_count(self, conn_id, req):
        response = {
            'cmd' : self.Response.GET_WATCHABLE_COUNT,
            'qty' : {
                'var' : 0,
                'alias' : 0
            }
        }

        response['qty']['var'] = self.datastore.get_entries_count(DatastoreEntry.Type.eVar)
        response['qty']['alias'] = self.datastore.get_entries_count(DatastoreEntry.Type.eAlias)
        self.handler.send(conn_id, response) 


    def make_datastore_entry_definition(self, entry):
        return {
            'id' : entry.get_id(),
            'type' : self.entry_type_to_str[entry.get_type()],
            'display_path' : entry.get_display_path(),
        }

    def make_error_response(self, req, msg):
        cmd = '<empty>'
        if 'cmd' in req:
            cmd = req['cmd']
        obj = {
            'cmd' : self.Response.ERROR,
            'request_cmd' : cmd,
            'msg' : msg
        }
        return obj

    def is_dict_with_key(self, d, k):
        return  isinstance(d, dict) and k in d 

    def close(self):
        self.handler.stop()
