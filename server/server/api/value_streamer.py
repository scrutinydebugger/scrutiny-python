# This class controls the flow of value update sent to clients.
# Rate limiter logic will be here

class ValueStreamer:
    def __init__(self):
        self.entry_to_publish = {}
        #self.watch_per_connection = {}
        self.frozen_connections = set()

    def freeze_connection(self, conn_id):
        self.frozen_connections.add(conn_id)

    def unfreeze_connection(self, conn_id):
        self.frozen_connections.remove(conn_id)

    def publish(self, entry, conn_id):
        try:
            self.entry_to_publish[conn_id].add(entry)
        except:
            pass

    def get_stream_chunk(self, conn_id):
        chunk =[]
        if conn_id not in self.entry_to_publish:
            return chunk

        if conn_id in self.frozen_connections:
            return chunk

        for entry in self.entry_to_publish[conn_id]:
            chunk.append(entry)

        for entry in chunk:
            self.entry_to_publish[conn_id].remove(entry)

        return chunk

    def is_still_waiting_stream(self, entry):
        for conn_id in self.entry_to_publish:
            if entry in self.entry_to_publish[conn_id]:
                return True
        return False

    def new_connection(self, conn_id):
        if conn_id not in self.entry_to_publish:
            self.entry_to_publish[conn_id] = set()

    def clean_connection(self, conn_id):
        if conn_id in self.entry_to_publish:
            del self.entry_to_publish[conn_id]

    def process(self):
        pass
