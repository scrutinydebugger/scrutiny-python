from .ClientHandler import ClientHandler

class API:
    def __init__(self, config):
        self.handler = ClientHandler(config)

    def start_listening(self):
        self.handler.start()

    def process(self):
        while not self.handler.rxqueue.empty():
            popped = self.handler.rxqueue.get()

            if 'obj' not in popped or 'conn_id' not in popped:
                continue

            print('RECEIVED : Connection %s - %s' % (popped['conn_id'], popped['obj']))
            echoed_msg = popped
            echoed_msg['obj']['your_conn_id'] = popped['conn_id']
            self.handler.txqueue.put(echoed_msg)

    def close(self):
        self.handler.stop()



