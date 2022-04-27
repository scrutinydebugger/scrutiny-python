#    datalog.py
#        Defines a datalogging configuration that can be read or write from the device.
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

from enum import Enum
from scrutiny.core import VariableType

from typing import Union


class DatalogConfiguration:
    __slots__ = '_destination', '_sample_rate', '_decimation', '_trigger', 'watches'

    class TriggerCondition(Enum):
        EQUAL = 0
        LESS_THAN = 1
        GREATER_THAN = 2
        LESS_OR_EQUAL_THAN = 3
        GREATER_OR_EQUAL_THAN = 4
        CHANGE = 5
        CHANGE_GREATER = 6
        CHANGE_LESS = 7

    class OperandType(Enum):
        CONST = 1
        WATCH = 2

    class Operand:
        operand_type: "DatalogConfiguration.OperandType"

        def get_type_id(self) -> int:
            return self.operand_type.value

    class ConstOperand(Operand):
        value: float
        operand_type: "DatalogConfiguration.OperandType"

        def __init__(self, value: float):
            self.value = value
            self.operand_type = DatalogConfiguration.OperandType.CONST

    class WatchOperand(Operand):
        address: int
        length: int
        interpret_as: VariableType
        operand_type: "DatalogConfiguration.OperandType"

        def __init__(self, address: int, length: int, interpret_as: VariableType):
            self.address = address
            self.length = length
            self.interpret_as = VariableType(interpret_as)
            self.operand_type = DatalogConfiguration.OperandType.WATCH

    class Watch:
        __slots__ = 'address', 'length'

        address: int
        length: int

        def __init__(self, address: int, length: int):
            self.address = address
            self.length = length

    class Trigger:
        __slots__ = '_condition', '_operand1', '_operand2'

        _condition: "DatalogConfiguration.TriggerCondition"
        _operand1: "DatalogConfiguration.Operand"
        _operand2: "DatalogConfiguration.Operand"

        @property
        def condition(self):
            return self._condition

        @condition.setter
        def condition(self, val: "DatalogConfiguration.TriggerCondition"):
            if not isinstance(val, DatalogConfiguration.TriggerCondition):
                raise ValueError('Trigger condition must be an instance of TriggerCondition')
            self._condition = val

        @property
        def operand1(self):
            return self._operand1

        @operand1.setter
        def operand1(self, val):
            if not isinstance(val, DatalogConfiguration.Operand):
                raise ValueError('operand1 must be an instance of TriggerCondition.Operand')
            self._operand1 = val

        @property
        def operand2(self):
            return self._operand2

        @operand2.setter
        def operand2(self, val):
            if not isinstance(val, DatalogConfiguration.Operand):
                raise ValueError('operand2 must be an instance of TriggerCondition.Operand')
            self._operand2 = val

    def __init__(self):
        watches: self.Watch
        _trigger: "DatalogConfiguration.Trigger"
        _destination: int
        _sample_rate: Union[int, float]
        _decimation: int

        self.watches = []
        self._trigger = self.Trigger()

    def add_watch(self, address, length):
        self.watches.append(self.Watch(address, length))

    @property
    def destination(self):
        return self._destination

    @destination.setter
    def destination(self, val):
        if not isinstance(val, int):
            raise ValueError('destination must be an integer')
        self._destination = val

    @property
    def sample_rate(self):
        return self._sample_rate

    @sample_rate.setter
    def sample_rate(self, val: Union[int, float]):
        if not isinstance(val, (int, float)):
            raise ValueError('sample_rate must be a a numeric value')

        if val <= 0:
            raise ValueError('sample_rate must be a positive value')

        self._sample_rate = val

    @property
    def decimation(self):
        return self._decimation

    @decimation.setter
    def decimation(self, val: int):
        if not isinstance(val, int):
            raise ValueError('decimation must be an integer')

        if val < 1:
            raise ValueError('decimation must be an integer greater than or equal to 1')

        self._decimation = val

    @property
    def trigger(self):
        return self._trigger

    @trigger.setter
    def trigger(self, val: "DatalogConfiguration.Trigger"):
        if not isinstance(val, DatalogConfiguration.Trigger):
            raise ValueError('trigger must be an instance of DatalogConfiguration.Trigger')

        self._trigger = val


class DatalogLocation:
    _target_id: int
    _location_type: "DatalogLocation.LocationType"
    _name: str

    class LocationType(Enum):
        RAM = 0
        ROM = 1
        EXTERNAL = 2

    def __init__(self, target_id: int, location_type: "DatalogLocation.LocationType", name: str):
        self.target_id = target_id
        self.location_type = location_type
        self.name = name

    @property
    def target_id(self) -> int:
        return self._target_id

    @target_id.setter
    def target_id(self, val) -> None:
        if not isinstance(val, int):
            raise ValueError('Target ID must be an integer')

        if val < 0 or val > 0xFF:
            raise ValueError('Target ID must be a one byte positive integer')

        self._target_id = val

    @property
    def location_type(self) -> "DatalogLocation.LocationType":
        return self._location_type

    @location_type.setter
    def location_type(self, val: "DatalogLocation.LocationType"):
        if not isinstance(val, DatalogLocation.LocationType):
            raise ValueError('Target type must be an instance of DatalogLocation.LocationType')

        self._location_type = val

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, val: str) -> None:
        if not isinstance(val, str):
            raise ValueError('Target name must be an ascii string')

        if len(val.encode('ascii')) > 0xFF:
            raise ValueError('Target name must be smaller than 255 bytes')

        self._name = val


class LogStatus(Enum):
    Triggered = 1
    WaitForTrigger = 2
    Recording = 3
    Disabled = 4


class RecordInfo:
    _record_id: int
    _location_type: "DatalogLocation.LocationType"
    _size: int

    def __init__(self, record_id: int, location_type: "DatalogLocation.LocationType", size: int):
        self.record_id = record_id
        self.location_type = location_type
        self.size = size

    @property
    def location_type(self) -> "DatalogLocation.LocationType":
        return self._location_type

    @location_type.setter
    def location_type(self, val: "DatalogLocation.LocationType") -> None:
        if isinstance(val, int):
            val = DatalogLocation.LocationType(val)

        if not isinstance(val, DatalogLocation.LocationType):
            print(val)
            raise ValueError('location_type must be a valid DatalogLocation.LocationType')

        self._location_type = val

    @property
    def record_id(self) -> int:
        return self._record_id

    @record_id.setter
    def record_id(self, val: int) -> None:
        if not isinstance(val, int):
            raise ValueError('record_id must be an integer')

        if val < 0:
            raise ValueError('record_id must be a positive integer')

        self._record_id = val

    @property
    def size(self) -> int:
        return self._size

    @size.setter
    def size(self, val: int) -> None:
        if not isinstance(val, int):
            raise ValueError('size must be an integer')

        if val < 0:
            raise ValueError('size must be a positive integer')

        self._size = val
