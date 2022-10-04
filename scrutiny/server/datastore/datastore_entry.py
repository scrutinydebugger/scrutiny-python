#    datastore_entry.py
#        A variable entry in the datastore
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import functools
import uuid
import time
import abc
import re
from scrutiny.core.basic_types import RuntimePublishedValue
from queue import Queue

from scrutiny.server.datastore.entry_type import EntryType
from scrutiny.core.variable import Variable, VariableEnum, EmbeddedDataType
from scrutiny.core.codecs import *

from typing import Any, Optional, Dict, Callable, Tuple, List
from scrutiny.core.typehints import GenericCallback
from scrutiny.core.alias import Alias
class ValueChangeCallback():
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


class UpdateTargetRequestCallback(GenericCallback):
    fn:Callable[[bool, 'DatastoreEntry', float], None]

class UpdateTargetRequest:
    value: Any
    request_timestamp: float
    completed: bool
    success: Optional[bool]
    complete_timestamp: Optional[float]
    completion_callback:Optional[UpdateTargetRequestCallback]
    entry:'DatastoreEntry'

    def __init__(self, value: Any, entry:'DatastoreEntry', callback:Optional[UpdateTargetRequestCallback]=None):
        self.value = value
        self.request_timestamp = time.time()
        self.completed = False
        self.complete_timestamp = None
        self.success = None
        self.completion_callback = callback
        self.entry = entry

    def complete(self, success) -> None:
        self.completed = True
        self.success = success
        self.complete_timestamp = time.time()
        if success:
            self.entry.set_last_target_update_timestamp(self.complete_timestamp)
        
        if self.completion_callback is not None:
            self.completion_callback(success, self.entry, self.complete_timestamp)


    def is_complete(self) -> bool:
        return self.completed

    def is_failed(self) -> Optional[bool]:
        return None if self.success is None else (not self.success)

    def is_success(self) -> Optional[bool]:
        return self.success

    def get_completion_timestamp(self) -> Optional[float]:
        return self.complete_timestamp
    
    def get_value(self) -> Any:
        return self.value



class DatastoreEntry:
    entry_id: str
    value_change_callback: Dict[str, Callable[["DatastoreEntry"], Any]]
    target_update_callback: Dict[str, Callable[["DatastoreEntry"], Any]]
    display_path: str
    value: Any
    last_target_update_timestamp: Optional[float]
    target_update_request_queue:Queue
    last_value_update_timestamp: float


    def __init__(self, display_path: str):
        display_path = display_path.strip()
        self.value_change_callback = {}
        self.target_update_callback = {}
        self.entry_id = uuid.uuid4().hex
        self.display_path = display_path 
        self.last_target_update_timestamp = None
        self.last_value_update_timestamp = time.time()
        self.target_update_request_queue = Queue()
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

    def register_value_change_callback(self, owner: str, callback: GenericCallback, args: Any = None) -> None:
        thecallback = ValueChangeCallback(fn=callback, owner=owner, args=args)
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

    def get_value_change_timestamp(self) -> float:
        return self.last_value_update_timestamp

    def get_last_target_update_timestamp(self) -> Optional[float]:
        return self.last_target_update_timestamp
    
    def set_last_target_update_timestamp(self, val:float) -> None:
        self.last_target_update_timestamp = val

    def update_target_value(self, value: Any, callback:Optional[UpdateTargetRequestCallback]=None) -> UpdateTargetRequest:
        update_request = UpdateTargetRequest(value, entry=self, callback=callback)
        try:
            self.target_update_request_queue.put_nowait(update_request)
        except:
            update_request.complete(success=False)
        return update_request

    def has_pending_target_update(self) -> bool:
        return not self.target_update_request_queue.empty()

    def pop_target_update_request(self) -> Optional[UpdateTargetRequest]:
        try:
            return self.target_update_request_queue.get_nowait()
        except:
            return None

    def encode_value(self, value: Optional[Encodable] = None) -> Tuple[bytes, Optional[bytes]]:
        if value is None:
            value = self.value

        return self.encode(value)


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
    aliasdef:Alias

    def __init__(self, aliasdef:Alias, refentry: DatastoreEntry):
        super().__init__(display_path=aliasdef.get_fullpath())
        self.refentry = refentry
        self.aliasdef = aliasdef

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
    
    def update_target_value(self, value: Any, callback:UpdateTargetRequestCallback=None) -> UpdateTargetRequest:
        alias_request = super().update_target_value(value, callback)
        new_value = self.aliasdef.compute_user_to_device(value)
        nested_callback = UpdateTargetRequestCallback(functools.partial(self.alias_target_update_callback, alias_request))
        new_request = self.refentry.update_target_value(new_value, callback=nested_callback)
        if alias_request.is_complete(): # Edge case if failed to enqueue request.
            new_request.complete(success=alias_request.is_complete())
        return alias_request

    def alias_target_update_callback(self, alias_request: UpdateTargetRequest, success:bool, entry:DatastoreEntry, timestamp:float):
        # entry is a var or a RPV
        alias_request.complete(success=success)



    # The function belows should not be used on a alias
    def set_value(self, *args, **kwargs):
        # Just to make explicit that this is not supposed to happen
        raise NotImplementedError('Cannot set value on a Alias variable')

    ## These function are meant to be used internally to make the alias mechanism work. Not to be used by a user.
    def set_value_internal(self, value:Any):
        new_value = self.aliasdef.compute_device_to_user(value)           
        DatastoreEntry.set_value(self, new_value)

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

    @classmethod
    def make_path(cls, id:int) -> str:
        return '/rpv/x%04X' % id
    
    @classmethod
    def is_valid_path(self, path:str) -> bool:
        return True if re.match(r'^\/?rpv\/x\d+\/?$', path, re.IGNORECASE) else False

    @classmethod
    def make(cls, rpv:RuntimePublishedValue) -> 'DatastoreRPVEntry':
        return DatastoreRPVEntry(display_path=cls.make_path(rpv.id), rpv=rpv)
