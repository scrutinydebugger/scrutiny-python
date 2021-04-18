import uuid
from enum import Enum
import datetime

class DatastoreEntry:

    class Type(Enum):
        eVar = 0
        eAlias = 1

    class UpdateTargetRequest:
        def __init__(self, value):
            self.value = value;
            self.request_timestamp = datetime.now()
            self.completed = False
            self.complete_timestamp = None

        def complete(self):
            self.completed = True
            self.complete_timestamp = datetime.now()

        def is_complete(self):
            return self.completed

    def __init__(self, wtype, display_path):
        
        if wtype not in [self.Type.eVar, self.Type.eAlias]:
            raise ValueError('Invalid watchable type')

        if not isinstance(display_path, str):
            raise ValueError('Invalid display path')

        self.wtype = wtype
        self.display_path = display_path
        self.entry_id = uuid.uuid4().hex
        self.dirty = False
        self.valid = False
        self.watched = False
        self.dirty_callbacks = []
        self.pending_target_update = None

    def get_type(self):
        return self.wtype

    def get_id(self):
        return self.entry_id

    def get_display_path(self):
        return self.display_path


    def set_dirty(self, val=True):
        just_got_dirty = False
        if not self.dirty and val == True:
            just_got_dirty = True
        self.dirty = val
        if just_got_dirty and self.watched:
            for callback in self.dirty_callbacks:
                if callable(callback[0]):
                    if callback[1] is None:
                        callback[0].__call__(self)
                    else:
                        callback[0].__call__(self, callback[1])
    
    def is_dirty(self):
        return self.dirty

    def watch(self, dirty_callback=None, args=None):
        self.watched = True
        if callable(dirty_callback):
            self.dirty_callbacks.append( (dirty_callback, args) )

    def stop_watching(self):
        self.watched = False
        self.dirty_callbacks = []

    def is_watched(self):
        return self.watched

    def update_target_value(self, value):
        self.pending_target_update = self.UpdateTargetRequest(value)

    def has_pending_target_update(self):
        if self.pending_target_update is None:
            return False

        if self.pending_target_update.is_completed():
            return False
        else:
            return True

    def mark_target_update_request_complete(self):
         if self.pending_target_update is not None:
            self.pending_target_update.complete()
    
    def discard_target_update_request(self):
        self.pending_target_update = None

    def get_pending_target_update_val(self):
        if self.has_pending_target_update():
            return self.pending_target_update.value
