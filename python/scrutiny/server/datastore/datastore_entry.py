import uuid
from enum import Enum
from datetime import datetime

class Callback:
    def __init__(self, fn, owner, args=None):
        if not callable(fn):
            raise ValueError('callback must be a callable')

        if owner is None:
            raise ValueError('Invalid owner for callback')

        self.fn = fn
        self.owner = owner
        self.args = args

    def __call__(self, *args, **kwargs):
        if self.args is None:
            self.fn.__call__(self.owner, *args, **kwargs)
        else:    
            self.fn.__call__(self.owner, self.args, *args, **kwargs)


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
        self.value_change_callback = {}
        self.pending_target_update = None
        self.callback_pending = False
        self.last_value_update = datetime.now()

    def get_type(self):
        return self.wtype

    def get_id(self):
        return self.entry_id

    def get_display_path(self):
        return self.display_path


    def execute_value_change_callback(self):
        self.callback_pending = True
        for owner in self.value_change_callback:
            self.value_change_callback[owner](self);
        self.callback_pending = False

    def has_callback_pending(self):
        return self.callback_pending 

    def register_value_change_callback(self, owner=None, callback=None,  args=None):
        thecallback = Callback(fn=callback, owner=owner, args=args)
        if owner in self.value_change_callback:
            raise ValueError('This owner already has a callback registered')
        self.value_change_callback[owner] = thecallback

    def unregister_value_change_callback(self, owner):
        if owner in self.value_change_callback:
            del self.value_change_callback[owner]

    def has_value_change_callback(self, owner=None):
        if owner is None:
            return (len(self.value_change_callback) == 0)
        else:
            return (owner in self.value_change_callback)

    def set_value(self, value):
        self.value = value
        self.last_value_update = datetime.now()
        self.execute_value_change_callback()

    def get_update_time(self):
        return self.last_value_update
        
    def get_value(self):
        return self.value

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
