#    datastore_entry.py
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import uuid
from enum import Enum
import time

from scrutiny.core import Variable, VariableType

from typing import Any, Optional, Dict, Callable, Tuple
from scrutiny.core.typehints import GenericCallback


class Callback():
    fn: GenericCallback
    owner: str
    args: Any

    def __init__(self, fn: GenericCallback, owner: str, args: Any = None):
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

    class EntryType(Enum):
        Var = 0
        Alias = 1

    class UpdateTargetRequest:
        value: Any
        request_timestamp: float
        completed: bool
        failed: bool
        complete_timestamp: Optional[float]

        def __init__(self, value: Any):
            self.value = value
            self.request_timestamp = time.time()
            self.completed = False
            self.complete_timestamp = None
            self.success = False

        def complete(self, success) -> None:
            self.completed = True
            self.success = success
            self.complete_timestamp = time.time()

        def is_complete(self) -> bool:
            return self.completed

        def is_failed(self):
            return self.completed and not self.success

        def is_success(self):
            return self.completed and self.success

        def get_completion_timestamp(self) -> Optional[float]:
            return self.complete_timestamp

    entry_type: "DatastoreEntry.EntryType"
    display_path: str
    entry_id: str
    value_change_callback: Dict[str, Callable[["DatastoreEntry"], Any]]
    pending_target_update: Optional["DatastoreEntry.UpdateTargetRequest"]
    callback_pending: bool
    last_value_update_timestamp: float
    last_target_update_timestamp: Optional[float]
    variable_def: Variable
    value: Any

    def __init__(self, entry_type: "DatastoreEntry.EntryType", display_path: str, variable_def: Variable):

        if entry_type not in [DatastoreEntry.EntryType.Var, DatastoreEntry.EntryType.Alias]:
            raise ValueError('Invalid watchable type')

        if not isinstance(display_path, str):
            raise ValueError('Invalid display path')

        self.entry_type = entry_type
        self.display_path = display_path
        self.entry_id = uuid.uuid4().hex
        self.value_change_callback = {}
        self.pending_target_update = None
        self.callback_pending = False
        self.last_value_update_timestamp = time.time()
        self.last_target_update_timestamp = None
        self.variable_def = variable_def
        self.value = 0

    def get_type(self) -> "DatastoreEntry.EntryType":
        return self.entry_type

    def get_data_type(self) -> VariableType:
        return self.variable_def.get_type()

    def get_core_variable(self) -> Variable:
        return self.variable_def

    def get_id(self) -> str:
        return self.entry_id

    def get_display_path(self) -> str:
        return self.display_path

    def get_address(self):
        return self.variable_def.get_address()

    def get_size(self):
        return self.variable_def.get_size()

    def set_value_from_data(self, data):
        self.set_value(self.variable_def.decode(data))

    def execute_value_change_callback(self) -> None:
        self.callback_pending = True
        for owner in self.value_change_callback:
            self.value_change_callback[owner](self);
        self.callback_pending = False

    def has_callback_pending(self) -> bool:
        return self.callback_pending

    def register_value_change_callback(self, owner: str, callback: GenericCallback, args: Any = None) -> None:
        thecallback = Callback(fn=callback, owner=owner, args=args)
        if owner in self.value_change_callback:
            raise ValueError('This owner already has a callback registered')
        self.value_change_callback[owner] = thecallback

    def unregister_value_change_callback(self, owner: Any) -> None:
        if owner in self.value_change_callback:
            del self.value_change_callback[owner]

    def has_value_change_callback(self, owner=None) -> bool:
        if owner is None:
            return (len(self.value_change_callback) == 0)
        else:
            return (owner in self.value_change_callback)

    def set_value(self, value: Any) -> None:
        self.value = value
        self.last_value_update_timestamp = time.time()
        self.execute_value_change_callback()

    def get_update_time(self) -> float:
        return self.last_value_update_timestamp

    def get_value(self) -> Any:
        return self.value

    def get_last_update_timestamp(self) -> Optional[float]:
        return self.last_target_update_timestamp

    def update_target_value(self, value: Any) -> None:
        self.pending_target_update = self.UpdateTargetRequest(value)

    def has_pending_target_update(self) -> bool:
        if self.pending_target_update is None:
            return False

        if self.pending_target_update.is_complete():
            return False
        else:
            return True

    def mark_target_update_request_complete(self) -> None:
        if self.pending_target_update is not None:
            self.pending_target_update.complete(success=True)
            self.last_target_update_timestamp = self.pending_target_update.get_completion_timestamp()

    def mark_target_update_request_failed(self) -> None:
        if self.pending_target_update is not None:
            self.pending_target_update.complete(success=False)

    def discard_target_update_request(self) -> None:
        self.pending_target_update = None

    def get_pending_target_update_val(self) -> Any:
        if self.has_pending_target_update():
            assert self.pending_target_update is not None  # for mypy
            return self.pending_target_update.value

    def encode_value(self, value: Optional[Any] = None) -> Tuple[bytes, Optional[bytes]]:
        if value is None:
            value = self.value

        return self.variable_def.encode(value)

    def encode_pending_update_value(self):
        if not self.has_pending_target_update():
            raise Exception('Datastore entry has no update request pending')

        return self.encode_value(self.pending_target_update.value)
