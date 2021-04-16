
from .datastore_entry import DatastoreEntry

entries = []
for i in range(10):
    entry = DatastoreEntry(DatastoreEntry.Type.eVar, 'SomeDisplayPath_%d' % i)
    entries.append(entry)