#    value_streamer.py
#        Take the data from the Datastore and sends it to all clients by respecting bitrate
#        limits and avoiding duplicate date.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

from scrutiny.server.datastore.datastore_entry import DatastoreEntry

from typing import List


class ValueStreamer:
    def __init__(self):
        self.entry_to_publish = {}
        self.frozen_connections = set()

    def freeze_connection(self, conn_id: str) -> None:
        self.frozen_connections.add(conn_id)

    def unfreeze_connection(self, conn_id: str) -> None:
        self.frozen_connections.remove(conn_id)

    def publish(self, entry: DatastoreEntry, conn_id: str) -> None:
        try:
            self.entry_to_publish[conn_id].add(entry)
        except:
            pass

    def get_stream_chunk(self, conn_id: str) -> List[DatastoreEntry]:
        chunk: List[DatastoreEntry] = []
        if conn_id not in self.entry_to_publish:
            return chunk

        if conn_id in self.frozen_connections:
            return chunk

        for entry in self.entry_to_publish[conn_id]:
            chunk.append(entry)

        for entry in chunk:
            self.entry_to_publish[conn_id].remove(entry)

        return chunk

    def is_still_waiting_stream(self, entry: DatastoreEntry) -> bool:
        for conn_id in self.entry_to_publish:
            if entry in self.entry_to_publish[conn_id]:
                return True
        return False

    def new_connection(self, conn_id: str) -> None:
        if conn_id not in self.entry_to_publish:
            self.entry_to_publish[conn_id] = set()

    def clear_connection(self, conn_id: str) -> None:
        if conn_id in self.entry_to_publish:
            del self.entry_to_publish[conn_id]

    def process(self) -> None:
        pass
