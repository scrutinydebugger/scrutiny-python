from .ClientHandler import ClientHandler

class API:
    def __init__(self, config):
        self.handler = ClientHandler(config)

    def start_listening(self):
        self.handler.start()

    def process(self):
        while self.handler.available():
            popped = self.handler.recv()

            if 'obj' not in popped or 'conn_id' not in popped:
                continue

            conn_id = popped['conn_id']
            obj = popped['obj']

            print('RECEIVED : Connection %s - %s' % (conn_id, obj))
            echoed_obj = obj
            echoed_obj['your_conn_id'] = conn_id
            self.handler.send(conn_id, echoed_obj)

    def close(self):
        self.handler.stop()
