from .websocket_client_handler import WebsocketClientHandler
from .queue_client_handler import QueueClientHandler
from ..datastore import Datastore
import logging

class API:

    class Command:
        ECHO = 'echo'

    class Response:
        ECHO = 'echo_response'

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


    def process_request(self, conn_id, req):
        if 'cmd' not in req:
            raise ValueError('No command in request')

        cmd = req['cmd']
        if cmd == self.Command.ECHO:
            self.process_echo(conn_id, req)
        else:
            raise NotImplementedError('Unsupported command %s' % cmd)


    def process_echo(self, conn_id, req):
        self.logger.debug('Processing Echo')
        response = dict(cmd=self.Response.ECHO, payload=req['payload'])
        self.handler.send(conn_id, response) 

    def close(self):
        self.handler.stop()
