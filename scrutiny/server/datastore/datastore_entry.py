#    datastore_entry.py
#        A variable entry in the datastore
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = [
    'EntryType',
    'DatastoreEntry',
    'DatastoreVariableEntry',
    'DatastoreAliasEntry',
    'DatastoreRPVEntry',
    'UpdateTargetRequestCallback',
    'UpdateTargetRequest'
]

import uuid
import time
import abc
import re
from scrutiny.core.basic_types import RuntimePublishedValue
import queue

from scrutiny.server.datastore.entry_type import EntryType
from scrutiny.core.basic_types import EmbeddedDataType, Endianness
from scrutiny.core.variable import Variable, VariableEnum
from scrutiny.core.codecs import *

from scrutiny.core.typehints import GenericCallback
from scrutiny.core.alias import Alias
from typing import Any, Optional, Dict, Callable, Tuple, Union


class ValueChangeCallback():
    """
    Callback object that ties a function and a owner ID.
    Is assigned to watched datastore entry so the watcher can be notified.
    """
    fn: GenericCallback
    owner: str
    args: Any

    def __init__(self, fn: GenericCallback, owner: str) -> None:
        if not callable(fn):
            raise ValueError('callback must be a callable')

        if owner is None:
            raise ValueError('Invalid owner for callback')

        self.fn = fn
        self.owner = owner

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        self.fn.__call__(self.owner, *args, **kwargs)


class UpdateTargetRequestCallback(GenericCallback):
    """Callback to call when a target update request completes"""
    fn: Callable[[bool, 'DatastoreEntry', float], None]


class UpdateTargetRequest:
    """
    Represent a request to write an entry in the target device.
    Once this request is completed and successful, the datastore can be updated.
    """
    value: Any
    request_timestamp: float
    completed: bool
    success: Optional[bool]
    complete_timestamp: Optional[float]
    completion_callback: Optional[UpdateTargetRequestCallback]
    entry: 'DatastoreEntry'

    def __init__(self, value: Any, entry: 'DatastoreEntry', callback: Optional[UpdateTargetRequestCallback] = None):
        self.value = value
        self.request_timestamp = time.time()
        self.completed = False
        self.complete_timestamp = None
        self.success = None
        self.completion_callback = callback
        self.entry = entry

    def complete(self, success: bool) -> None:
        """ Mark a request as completed. Success or not. Call the registered callbacks."""
        self.completed = True
        self.success = success
        self.complete_timestamp = time.time()
        if success:
            self.entry.set_last_target_update_timestamp(self.complete_timestamp)

        if self.completion_callback is not None:
            self.completion_callback(success, self.entry, self.complete_timestamp)

    def is_complete(self) -> bool:
        """Returns True if the request has been marked as completed (success or failure)"""
        return self.completed

    def is_failed(self) -> Optional[bool]:
        """Returns True if this request completed with a failure. None if incomplete"""
        return None if self.success is None else (not self.success)

    def is_success(self) -> Optional[bool]:
        """Returns True if this request completed with a success. None if incomplete"""
        return self.success

    def get_completion_timestamp(self) -> Optional[float]:
        """Returns the timestamp at which the request has been completed. None if incomplete"""
        return self.complete_timestamp

    def get_value(self) -> Any:
        """Get the value requested"""
        return self.value


class DatastoreEntry(abc.ABC):
    """
    Represent an entry in the datastore that can be written and read.
    it has a unique ID and a display path used for GUI tree-like rendering.

    An entry can also be requested to be updated on the target (write request). 
    When the value change or a write request is completed, a callback will be called.
    """
    entry_id: str
    value_change_callback: Dict[str, Callable[["DatastoreEntry"], Any]]
    target_update_callback: Dict[str, Callable[["DatastoreEntry"], Any]]
    display_path: str
    value: Any
    last_target_update_timestamp: Optional[float]
    target_update_request_queue: "queue.Queue[UpdateTargetRequest]"
    last_value_update_timestamp: float

    def __init__(self, display_path: str):
        display_path = display_path.strip()
        self.value_change_callback = {}
        self.target_update_callback = {}
        self.entry_id = uuid.uuid4().hex    # unique ID
        self.display_path = display_path
        self.last_target_update_timestamp = None
        self.last_value_update_timestamp = time.time()
        self.target_update_request_queue = queue.Queue()
        self.value = 0

    @abc.abstractmethod
    def get_data_type(self) -> EmbeddedDataType:
        """Returns the device data type"""
        raise NotImplementedError("Abstract method")

    @abc.abstractmethod
    def get_type(self) -> EntryType:
        """Return the datastore entry type"""
        raise NotImplementedError("Abstract method")

    @abc.abstractmethod
    def has_enum(self) -> bool:
        """Returns True if the entry has an enum"""
        raise NotImplementedError("Abstract method")

    @abc.abstractmethod
    def get_enum(self) -> VariableEnum:
        """Returns the enum attached to the entry. Raise an exception if there is None"""
        raise NotImplementedError("Abstract method")

    @abc.abstractmethod
    def encode(self, value: Encodable) -> Tuple[bytes, Optional[bytes]]:
        """Encode the value to a stream of bytes and a data mask. 
        Returns as tuple : (data, mask)"""
        raise NotImplementedError("Abstract method")

    @abc.abstractmethod
    def decode(self, data: bytes) -> Encodable:
        """Decode a stream of bytes into a Python value"""
        raise NotImplementedError("Abstract method")

    def get_id(self) -> str:
        """Returns the datastore entry ID"""
        return self.entry_id

    def get_display_path(self) -> str:
        """Get the tree-like display path of the datastore entry """
        return self.display_path

    def get_value(self) -> Any:
        """Returns the current entry value"""
        return self.value

    def set_value_from_data(self, data: bytes) -> None:
        """Converts bytes gotten from memory to a value"""
        self.set_value(self.decode(data))

    def execute_value_change_callback(self) -> None:
        """Run all the callbacks when the value is updated"""
        for owner in self.value_change_callback:
            self.value_change_callback[owner](self)

    def register_value_change_callback(self, owner: str, callback: GenericCallback) -> None:
        """Add a callback to be called when this entry value changes"""
        thecallback = ValueChangeCallback(fn=callback, owner=owner)
        if owner in self.value_change_callback:
            raise ValueError('This owner already has a callback registered')
        self.value_change_callback[owner] = thecallback

    def unregister_value_change_callback(self, owner: Any) -> None:
        """Remove a callback on value change"""
        if owner in self.value_change_callback:
            del self.value_change_callback[owner]

    def has_value_change_callback(self, owner: Optional[str] = None) -> bool:
        """Tells if this entry has at least one callback for the given owner."""
        if owner is None:
            return (len(self.value_change_callback) == 0)
        else:
            return (owner in self.value_change_callback)

    def set_value(self, value: Any) -> None:
        """ Change the value in the datastore. Should be done by the device side of
         the datastore as callbacks are meant to propagate the update to the user (API side)"""
        self.value = value
        self.last_value_update_timestamp = time.time()
        self.execute_value_change_callback()

    def get_value_change_timestamp(self) -> float:
        """Returns the timestamp of the last value update made to this entry """
        return self.last_value_update_timestamp

    def get_last_target_update_timestamp(self) -> Optional[float]:
        """Returns the timestamp of the last successful completed target value update (write)"""
        return self.last_target_update_timestamp

    def set_last_target_update_timestamp(self, val: float) -> None:
        """Sets the timestamp of the last successful completed target value update (write)"""
        self.last_target_update_timestamp = val


class DatastoreVariableEntry(DatastoreEntry):
    """
    A datastore entry that represents  variable in memory. It is linked to a "Variable" object
    that contains an address, a type, an endianness, optional bitfield, etc.
    """
    variable_def: Variable
    codec: BaseCodec    # The codec used to converts bytes to values and vice versa

    def __init__(self, display_path: str, variable_def: Variable):
        super().__init__(display_path=display_path)
        self.variable_def = variable_def
        self.codec = Codecs.get(self.variable_def.get_type(), self.variable_def.endianness)

    def get_type(self) -> EntryType:
        """Returns the device data type"""
        return EntryType.Var    # Datastore entry type

    def get_data_type(self) -> EmbeddedDataType:
        """Return the datastore entry type"""
        return self.variable_def.get_type()  # Variable datatype

    def get_core_variable(self) -> Variable:
        """Return the referenced variable definition"""
        return self.variable_def

    def get_address(self) -> int:
        """Return the referenced variable address"""
        return self.variable_def.get_address()

    def get_size(self) -> int:
        """Return the variable data size"""
        return self.variable_def.get_type().get_size_byte()

    def has_enum(self) -> bool:
        """Returns True if the entry has an enum"""
        return self.variable_def.has_enum()

    def get_enum(self) -> VariableEnum:
        """Returns the enum attached to the entry. Raise an exception if there is None"""
        enum = self.variable_def.get_enum()  # Possibly has no enum.
        assert enum is not None             # Should have checked with has_enum() first
        return enum

    def is_bitfield(self) -> bool:
        """Returns True if this variable is a bitfield"""
        return self.variable_def.is_bitfield()

    def get_bitsize(self) -> Optional[int]:
        """Returns the size of the bitfield. None if this variable is not a bitfield """
        return self.variable_def.get_bitsize()

    def get_bitoffset(self) -> Optional[int]:
        """Returns the offset of the bitfield in the variable. None if this variable is not a bitfield"""
        return self.variable_def.get_bitoffset()

    def encode(self, value: Encodable) -> Tuple[bytes, Optional[bytes]]:
        """Encode the value to a stream of bytes and a data mask. 
        Returns as tuple : (data, mask)"""
        return self.variable_def.encode(value)  # Returns a tuple of (data, mask)

    def decode(self, data: bytes) -> Encodable:
        """Decode a stream of bytes into a Python value"""
        return self.variable_def.decode(data)


class DatastoreAliasEntry(DatastoreEntry):
    """
    Represent a datastore entry of type Alias.
    It will points to another datastore entry of type != Alias and
    route write/read request to them. 

    It works by subscribing to them, just like the API would do.
    """

    refentry: DatastoreEntry    # Entry pointed by the alias
    aliasdef: Alias             # The definition of the alias

    def __init__(self, aliasdef: Alias, refentry: DatastoreEntry) -> None:
        super().__init__(display_path=aliasdef.get_fullpath())
        self.refentry = refentry
        self.aliasdef = aliasdef

    def resolve(self, obj: Optional["DatastoreEntry"] = None) -> DatastoreEntry:
        """ Returns the referenced entry """
        if obj == None:
            obj = self.refentry

        if isinstance(obj, DatastoreAliasEntry):    # Just in case recursion happens.. but shouldn't
            return obj.resolve(obj.refentry)
        assert obj is not None
        return obj

    def get_type(self) -> EntryType:
        """Returns the device data type"""
        return EntryType.Alias  # Datastore entry type

    def get_data_type(self) -> EmbeddedDataType:
        """Return the datastore entry type"""
        return self.refentry.get_data_type()    # Variable datatype

    def has_enum(self) -> bool:
        """Returns True if the entry has an enum"""
        return self.refentry.has_enum()

    def get_enum(self) -> VariableEnum:
        """Returns the enum attached to the entry. Raise an exception if there is None"""
        return self.refentry.get_enum()

    def encode(self, value: Encodable) -> Tuple[bytes, Optional[bytes]]:
        """Encode the value to a stream of bytes and a data mask. 
        Returns as tuple : (data, mask)"""
        return self.refentry.encode(value)

    def decode(self, data: bytes) -> Encodable:
        """Decode a stream of bytes into a Python value"""
        return self.aliasdef.compute_device_to_user(self.refentry.decode(data))

    def alias_target_update_callback(self, alias_request: UpdateTargetRequest, success: bool, entry: DatastoreEntry, timestamp: float) -> None:
        """Callback used by an alias to grab the result of the target update and apply it to its own"""
        # entry is a var or a RPV
        alias_request.complete(success=success)

    def set_value(self, *args: Any, **kwargs: Any) -> None:
        """Will raise an exception. Not supposed to be called"""
        # Just to make explicit that this is not supposed to happen
        raise NotImplementedError('Cannot set value on a Alias variable')

    def set_value_internal(self, value: Union[int, float, bool]) -> None:
        """Set the value of this alias object."""
        # These function are meant to be used internally to make the alias mechanism work. Not to be used by a user.
        new_value = self.aliasdef.compute_device_to_user(value)
        DatastoreEntry.set_value(self, new_value)


class DatastoreRPVEntry(DatastoreEntry):
    """A datastore entry that represents a Runtime Published Value"""

    rpv: RuntimePublishedValue
    codec: BaseCodec

    def __init__(self, display_path: str, rpv: RuntimePublishedValue):
        super().__init__(display_path=display_path)
        self.rpv = rpv
        self.codec = Codecs.get(rpv.datatype, Endianness.Big)    # Default protocol encoding is big endian

    def get_type(self) -> EntryType:
        """Returns the device data type"""
        return EntryType.RuntimePublishedValue

    def get_data_type(self) -> EmbeddedDataType:
        """Return the datastore entry type"""
        return self.rpv.datatype

    def has_enum(self) -> bool:
        """Returns True if the entry has an enum"""
        return False

    def get_enum(self) -> VariableEnum:
        """Returns the enum attached to the entry. Raise an exception if there is None"""
        raise NotImplementedError('RuntimePublishedValues does not have enums')

    def encode(self, value: Encodable) -> Tuple[bytes, Optional[bytes]]:
        """Encode the value to a stream of bytes and a data mask. 
        Returns as tuple : (data, mask)"""
        value = Codecs.make_value_valid(self.get_data_type(), value)
        return self.codec.encode(value), None   # Not bitmask on RPV.

    def decode(self, data: bytes) -> Encodable:
        """Decode a stream of bytes into a Python value"""
        return self.codec.decode(data)

    def get_rpv(self) -> RuntimePublishedValue:
        """Returns the Runtime Published Value (RPV) definition attached to this entry"""
        return self.rpv

    @classmethod
    def make_path(cls, id: int) -> str:
        """Make a datastore display path out of a numeric RPV ID"""
        return '/rpv/x%04X' % id

    @classmethod
    def is_valid_path(self, path: str) -> bool:
        """Returns True if the given tree-like path is the path of a Runtime Published Value"""
        return True if re.match(r'^\/?rpv\/x\d+\/?$', path, re.IGNORECASE) else False

    @classmethod
    def make(cls, rpv: RuntimePublishedValue) -> 'DatastoreRPVEntry':
        """Make a datastore entry from a RPV definition"""
        return DatastoreRPVEntry(display_path=cls.make_path(rpv.id), rpv=rpv)
