#    datastore_entry.py
#        A variable entry in the datastore
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import uuid
from enum import Enum
import time
import abc
from scrutiny.core.basic_types import RuntimePublishedValue

from scrutiny.core.variable import Variable, VariableEnum, EmbeddedDataType
from scrutiny.core.codecs import *

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


class EntryType(Enum):
    Var = 0
    Alias = 1
    RuntimePublishedValue = 2


class UpdateTargetRequest:
    value: Any
    request_timestamp: float
    completed: bool
    success: Optional[bool]
    complete_timestamp: Optional[float]
    completion_callbacks = Dict[str, Callable[["DatastoreEntry", 'UpdateTargetRequest'], Any]]

    def __init__(self, value: Any):
        self.value = value
        self.request_timestamp = time.time()
        self.completed = False
        self.complete_timestamp = None
        self.success = None

    def complete(self, success) -> None:
        self.completed = True
        self.success = success
        self.complete_timestamp = time.time()

    def is_complete(self) -> bool:
        return self.completed

    def is_failed(self) -> Optional[bool]:
        return None if self.success is None else (not self.success)

    def is_success(self) -> Optional[bool]:
        return self.success

    def get_completion_timestamp(self) -> Optional[float]:
        return self.complete_timestamp


class DatastoreEntry:
    entry_id: str
    value_change_callback: Dict[str, Callable[["DatastoreEntry"], Any]]
    target_update_callback: Dict[str, Callable[["DatastoreEntry"], Any]]
    display_path: str
    value: Any
    last_target_update_timestamp: Optional[float]
    pending_target_update: Optional[UpdateTargetRequest]
    last_value_update_timestamp: float

    def __init__(self, display_path: str):

        self.value_change_callback = {}
        self.target_update_callback = {}
        self.entry_id = uuid.uuid4().hex
        self.display_path = display_path
        self.last_target_update_timestamp = None
        self.last_value_update_timestamp = time.time()
        self.pending_target_update = None
        self.value = 0

    @abc.abstractmethod
    def get_data_type(self) -> EmbeddedDataType:
        raise NotImplementedError("Abstract class")

    @abc.abstractmethod
    def get_type(self) -> EntryType:
        raise NotImplementedError("Abstract class")

    @abc.abstractmethod
    def has_enum(self) -> bool:
        raise NotImplementedError("Abstract class")

    @abc.abstractmethod
    def get_enum(self) -> VariableEnum:
        raise NotImplementedError("Abstract class")

    @abc.abstractmethod
    def encode(self, value: Encodable) -> Tuple[bytes, Optional[bytes]]:
        raise NotImplementedError("Abstract class")

    @abc.abstractmethod
    def decode(self, data: bytes) -> Encodable:
        raise NotImplementedError("Abstract class")

    def get_id(self) -> str:
        return self.entry_id

    def get_display_path(self) -> str:
        return self.display_path

    def get_value(self) -> Any:
        return self.value

    def set_value_from_data(self, data) -> None:
        self.set_value(self.decode(data))

    def execute_value_change_callback(self) -> None:
        for owner in self.value_change_callback:
            self.value_change_callback[owner](self)

    def execute_target_update_callback(self) -> None:
        for owner in self.target_update_callback:
            self.target_update_callback[owner](self)

    def register_value_change_callback(self, owner: str, callback: GenericCallback, args: Any = None) -> None:
        thecallback = Callback(fn=callback, owner=owner, args=args)
        if owner in self.value_change_callback:
            raise ValueError('This owner already has a callback registered')
        self.value_change_callback[owner] = thecallback

    def register_target_update_callback(self, owner: str, callback: GenericCallback, args: Any = None) -> None:
        thecallback = Callback(fn=callback, owner=owner, args=args)
        if owner in self.target_update_callback:
            raise ValueError('This owner already has a callback registered')
        self.target_update_callback[owner] = thecallback

    def unregister_value_change_callback(self, owner: Any) -> None:
        if owner in self.value_change_callback:
            del self.value_change_callback[owner]

    def unregister_target_update_callback(self, owner: Any) -> None:
        if owner in self.value_change_callback:
            del self.value_change_callback[owner]

    def has_value_change_callback(self, owner=None) -> bool:
        if owner is None:
            return (len(self.value_change_callback) == 0)
        else:
            return (owner in self.value_change_callback)

    def has_target_update_callback(self, owner=None) -> bool:
        if owner is None:
            return (len(self.target_update_callback) == 0)
        else:
            return (owner in self.target_update_callback)

    def set_value(self, value: Any) -> None:
        self.value = value
        self.last_value_update_timestamp = time.time()
        self.execute_value_change_callback()

    def get_update_time(self) -> float:
        return self.last_value_update_timestamp

    def get_last_update_timestamp(self) -> Optional[float]:
        return self.last_target_update_timestamp

    def update_target_value(self, value: Any) -> UpdateTargetRequest:
        self.pending_target_update = UpdateTargetRequest(value)
        return self.pending_target_update

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
            self.execute_target_update_callback()

    def mark_target_update_request_failed(self) -> None:
        if self.pending_target_update is not None:
            self.pending_target_update.complete(success=False)
            self.execute_target_update_callback()

    def get_target_update_record(self) -> Optional[UpdateTargetRequest]:
        return self.pending_target_update

    def discard_target_update_request(self) -> None:
        self.pending_target_update = None

    def get_pending_target_update_val(self) -> Any:
        if self.has_pending_target_update():
            assert self.pending_target_update is not None  # for mypy
            return self.pending_target_update.value

    def encode_value(self, value: Optional[Encodable] = None) -> Tuple[bytes, Optional[bytes]]:
        if value is None:
            value = self.value

        return self.encode(value)

    def encode_pending_update_value(self) -> Tuple[bytes, Optional[bytes]]:
        if not self.has_pending_target_update():
            raise Exception('Datastore entry has no update request pending')
        assert self.pending_target_update is not None

        return self.encode_value(self.pending_target_update.value)


class DatastoreVariableEntry(DatastoreEntry):
    variable_def: Variable
    codec: BaseCodec

    def __init__(self, display_path: str, variable_def: Variable):
        super().__init__(display_path=display_path)
        self.variable_def = variable_def
        self.codec = Codecs.get(self.variable_def.get_type(), self.variable_def.endianness)

    def get_type(self) -> EntryType:
        return EntryType.Var

    def get_data_type(self) -> EmbeddedDataType:
        return self.variable_def.get_type()

    def get_core_variable(self) -> Variable:
        return self.variable_def

    def get_address(self) -> int:
        return self.variable_def.get_address()

    def get_size(self) -> int:
        typesize = self.variable_def.get_type().get_size_byte()
        assert typesize is not None
        return typesize

    def has_enum(self) -> bool:
        return self.variable_def.has_enum()

    def get_enum(self) -> VariableEnum:
        enum = self.variable_def.get_enum()
        assert enum is not None
        return enum

    def encode(self, value: Encodable) -> Tuple[bytes, Optional[bytes]]:
        return self.variable_def.encode(value)

    def decode(self, data: bytes) -> Encodable:
        return self.variable_def.decode(data)


class DatastoreAliasEntry(DatastoreEntry):

    refentry: DatastoreEntry

    def __init__(self, display_path: str, refentry: DatastoreEntry):
        super().__init__(display_path=display_path)
        self.refentry = refentry

    def resolve(self, obj=None) -> DatastoreEntry:
        if obj == None:
            obj = self.refentry

        if isinstance(obj, DatastoreAliasEntry):
            return obj.resolve(obj.refentry)
        return obj

    def get_type(self) -> EntryType:
        return EntryType.Alias

    def get_data_type(self) -> EmbeddedDataType:
        return self.refentry.get_data_type()

    def has_enum(self) -> bool:
        return self.refentry.has_enum()

    def get_enum(self) -> VariableEnum:
        return self.refentry.get_enum()

    def encode(self, value: Encodable) -> Tuple[bytes, Optional[bytes]]:
        return self.refentry.encode(value)

    def decode(self, data: bytes) -> Encodable:
        return self.refentry.decode(data)
    

    def update_target_value(self, value: Any) -> UpdateTargetRequest:
        self.refentry.update_target_value(value)
        return super().update_target_value(value)

    # The function belows should not be used on a alias
    def set_value(self, *args, **kwargs):
        # Just to make explicit that this is not supposed to happen
        raise NotImplementedError('Cannot set value on a Alias variable')

    def mark_target_update_request_complete(self, *args, **kwargs):
        raise NotImplementedError('Cannot use mark_target_update_request_complete on a Alias variable')

    def mark_target_update_request_failed(self, *args, **kwargs):
        raise NotImplementedError('Cannot use mark_target_update_request_failed on a Alias variable')

    ## These function are meant to be used internally to make the alias mechanism work. Not to be used by a user.
    def set_value_internal(self, *args, **kwargs):
        DatastoreEntry.set_value(self, *args, **kwargs)
    
    def mark_target_update_request_complete_internal(self, *args, **kwargs) :
        return super().mark_target_update_request_complete(*args, **kwargs)

    def mark_target_update_request_failed_internal(self, *args, **kwargs) :
        return super().mark_target_update_request_failed(*args, **kwargs)

class DatastoreRPVEntry(DatastoreEntry):

    rpv: RuntimePublishedValue
    codec: BaseCodec

    def __init__(self, display_path: str, rpv: RuntimePublishedValue):
        super().__init__(display_path=display_path)
        self.rpv = rpv
        self.codec = Codecs.get(rpv.datatype, Endianness.Big)    # Default protocol encoding is big endian

    def get_type(self) -> EntryType:
        return EntryType.RuntimePublishedValue

    def get_data_type(self) -> EmbeddedDataType:
        return self.rpv.datatype

    def has_enum(self) -> bool:
        return False

    def get_enum(self) -> VariableEnum:
        raise NotImplementedError('RuntimePublishedValues does not have enums')

    def encode(self, value: Encodable) -> Tuple[bytes, Optional[bytes]]:
        return self.codec.encode(value), None   # Not bitmask on RPV.

    def decode(self, data: bytes) -> Encodable:
        return self.codec.decode(data)

    def get_rpv(self) -> RuntimePublishedValue:
        return self.rpv
