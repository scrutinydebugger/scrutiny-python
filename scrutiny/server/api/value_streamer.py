#    value_streamer.py
#        Take the data from the Datastore and sends it to all clients by respecting bitrate
#        limits and avoiding duplicate date.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny.server.datastore.datastore_entry import DatastoreEntry

from typing import List, Set, Dict


class ValueStreamer:
    """
    This class get notified when a value changes in the datastore and decides
    when to actually flush the update to the client handler. It keeps track of the 
    client connection ID so that rules are applied per client.

    It avoid duplicates updates and can also apply some rules such as throttling
    """

    entry_to_publish: Dict[str, Set[DatastoreEntry]]
    frozen_connections: Set[str]

    def __init__(self) -> None:
        self.entry_to_publish = {}
        self.frozen_connections = set()

    def freeze_connection(self, conn_id: str) -> None:
        # Mainly used for unit testing. Pause a connection
        self.frozen_connections.add(conn_id)

    def unfreeze_connection(self, conn_id: str) -> None:
        # Mainly used for unit testing. Unpause a connection
        self.frozen_connections.remove(conn_id)

    def publish(self, entry: DatastoreEntry, conn_id: str) -> None:
        # inform the value streamer that a new value should be published.
        # This is called by the datastore set_value callback
        try:
            self.entry_to_publish[conn_id].add(entry)
        except Exception:
            pass

    def get_stream_chunk(self, conn_id: str) -> List[DatastoreEntry]:
        # Returns a list of entry to be flushed per connection
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
        # Tells if an entry update is pending to be sent to a client
        for conn_id in self.entry_to_publish:
            if entry in self.entry_to_publish[conn_id]:
                return True
        return False

    def new_connection(self, conn_id: str) -> None:
        # Called when the API gets a new connection
        if conn_id not in self.entry_to_publish:
            self.entry_to_publish[conn_id] = set()

    def clear_connection(self, conn_id: str) -> None:
        # Called when the API looses a connection
        if conn_id in self.entry_to_publish:
            del self.entry_to_publish[conn_id]

    def process(self) -> None:
        pass
