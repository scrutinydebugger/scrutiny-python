import websockets
import queue
import time 
import asyncio
import threading
import uuid
import logging
import json

class QueueClientHandler:
    def __init__(self, config):
        self.rxqueue = queue.Queue()
        self.txqueue = queue.Queue()
        self.config = config        # Nice to have: have multiple queue with different ID for testing purpose
        self.validate_config(config)

        self.server_to_client_queue = self.config['server_to_client_queue']
        self.client_to_server_queue = self.config['client_to_server_queue']
        self.logger = logging.getLogger(self.__class__.__name__)
        self.stop_requested = False
        self.conn_id = self.__class__.__name__
        self.started = False

    def validate_config(self, config):
        required_field = ['server_to_client_queue', 'client_to_server_queue']
        for field  in required_field:
            if field not in config:
                raise ValueError('%s : Missing config field : %s' % (self.__class__.__name__, field))

    def run(self):
        while not self.stop_requested:
            try:
                while not self.client_to_server_queue.empty():
                    popped = self.client_to_server_queue.get()
                    if popped is not None:
                        try:
                            obj = json.loads(popped)
                            self.rxqueue.put(dict(conn_id = self.conn_id, obj=obj))
                        except Exception as e:
                            self.logger.error('Received invalid msg.  %s' % str(e) )

                while not self.txqueue.empty():
                    popped = self.txqueue.get()
                    if popped is not None:
                        try:
                            msg = json.dumps(popped['obj'])
                            self.server_to_client_queue.put(msg)
                        except Exception as e:
                            self.logger.error('Cannot send message.  %s' % str(e) )

            except Exception as e:
                self.logger.error(str(e))
                self.stop_requested = True
                raise e
            time.sleep(0.01)

    def process(self):
        pass # nothing to do


    def start(self):
        self.thread = threading.Thread(target=self.run)
        self.thread.start()
        self.started = True

    def stop(self):
        self.stop_requested = True
        self.thread.join()

    def send(self, conn_id, obj):
        if not self.txqueue.full():
            container = {'conn_id' : conn_id, 'obj' : obj}
            self.txqueue.put(container)

    def available(self):
        return not self.rxqueue.empty()

    def recv(self):
        return self.rxqueue.get()

