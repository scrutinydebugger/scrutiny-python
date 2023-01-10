#    datalog.py
#        Defines a datalogging configuration that can be read or write from the device.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

from enum import Enum
from scrutiny.core.variable import Variable
from scrutiny.core.basic_types import RuntimePublishedValue, EmbeddedDataType


from typing import Union, List
from abc import ABC, abstractmethod


class Encoding(Enum):
    RAW = 0


class DataloggerStatus:
    IDLE = 0
    CONFIGURED = 1
    ARMED = 2
    ACQUISITION_COMPLETED = 3
    ERROR = 4

# region Operands


class OperandType(Enum):
    Literal = 0
    Var = 1
    VarBit = 2
    RPV = 3


class Operand(ABC):

    @abstractmethod
    def get_type(self) -> OperandType:
        raise NotImplementedError("Not implemented")


class LiteralOperand(Operand):
    value: float

    def __init__(self, value: Union[float, int]):
        self.value = float(value)

    def get_type(self) -> OperandType:
        return OperandType.Literal


class VarOperand(Operand):
    address: int
    datatype: EmbeddedDataType

    def __init__(self, address: int, datatype: EmbeddedDataType):
        if not isinstance(address, int):
            raise ValueError("Given address must be an int")

        if not isinstance(datatype, EmbeddedDataType):
            raise ValueError("Given datatype must be an EmbeddedDataType")

        self.address = address
        self.datatype = datatype

    def get_type(self) -> OperandType:
        return OperandType.Var


class VarBitOperand(Operand):
    address: int
    datatype: EmbeddedDataType
    bitoffset: int
    bitsize: int

    def __init__(self, address: int, datatype: EmbeddedDataType, bitoffset: int, bitsize: int):
        if not isinstance(address, int):
            raise ValueError("Given address must be an int")

        if not isinstance(datatype, EmbeddedDataType):
            raise ValueError("Given datatype must be an EmbeddedDataType")

        if not isinstance(bitoffset, int):
            raise ValueError("Given bitoffset must be an int")

        if not isinstance(bitsize, int):
            raise ValueError("Given bitsize must be an int")

        self.address = address
        self.datatype = datatype
        self.bitoffset = bitoffset
        self.bitsize = bitsize

    def get_type(self) -> OperandType:
        return OperandType.VarBit


class RPVOperand(Operand):
    rpv_id: int

    def __init__(self, rpv_id: int):
        if not isinstance(rpv_id, int):
            raise ValueError("Given operand requires a int")

        self.rpv_id = rpv_id

    def get_type(self) -> OperandType:
        return OperandType.RPV


# endregion

# region Loggable Signals


class LoggableSignalType(Enum):
    MEMORY = 0
    RPV = 1
    TIME = 2


class LoggableSignal:
    signal_type: LoggableSignalType

    @abstractmethod
    def get_type(self) -> OperandType:
        raise NotImplementedError("Not implemented")


class MemoryLoggableSignal(LoggableSignal):
    address: int
    size: int

    def __init__(self, address: int, size: int):
        if not isinstance(address, int):
            raise ValueError("Given address must be an int")

        if not isinstance(size, int):
            raise ValueError("Given size must be an int")

        self.address = address
        self.size = size

    def get_type(self) -> OperandType:
        return LoggableSignalType.MEMORY


class RPVLoggableSignal(LoggableSignal):
    rpv_id: int

    def __init__(self, rpv_id: int):
        if not isinstance(rpv_id, int):
            raise ValueError("Given rpv_id must be an int")
        self.rpv_id = rpv_id

    def get_type(self) -> OperandType:
        return LoggableSignalType.RPV


class TimeLoggableSignal(LoggableSignal):
    def __init__(self):
        pass

    def get_type(self) -> OperandType:
        return LoggableSignalType.TIME

# endregion

# region Trigger Condition


class TriggerConditionID(Enum):
    AlwaysTrue = 0          # Always true
    Equal = 1               # Operand1 == Operand2
    NotEqual = 2            # Operand1 != Operand2
    LessThan = 3            # Operand1 < Operand2
    LessOrEqualThan = 4     # Operand1 <= Operand2
    GreaterThan = 5         # Operand1 > Operand2
    GreaterOrEqualThan = 6  # Operand1 >= Operand2
    ChangeMoreThan = 7      # X=(Operand1[n]-Operand1[n-1]); |X| > |Operand2| && sign(X) == sign(Operand2)
    IsWithin = 8            # |Operand1 - Operand2| < |Operand3|


class TriggerCondition:
    operands: List[Operand]
    condition_id: TriggerConditionID

    def __init__(self, condition_id: TriggerConditionID, *args: List[Operand]):
        self.operands = []
        self.condition_id = condition_id

        if not isinstance(condition_id, TriggerConditionID):
            raise ValueError('Invalid condition ID')

        expected_number_of_operands = {
            TriggerConditionID.AlwaysTrue: 0,
            TriggerConditionID.ChangeMoreThan: 2,
            TriggerConditionID.Equal: 2,
            TriggerConditionID.NotEqual: 2,
            TriggerConditionID.GreaterThan: 2,
            TriggerConditionID.GreaterOrEqualThan: 2,
            TriggerConditionID.LessThan: 2,
            TriggerConditionID.LessOrEqualThan: 2,
            TriggerConditionID.IsWithin: 3
        }

        if len(args) != expected_number_of_operands[condition_id]:
            raise ValueError("%d operands are required for trigger condition %s but %d were given",
                             (expected_number_of_operands[condition_id], condition_id.name, len(args)))

        for operand in args:
            if not isinstance(operand, Operand):
                raise ValueError("Given operand is not a valid Operand object")

        self.operands = list(args)

    def get_operands(self) -> List[Operand]:
        return self.operands

    def get_id(self) -> TriggerConditionID:
        raise self.condition_id


class Configuration:
    _decimation: int
    _probe_location: float
    _timeout: float
    _trigger_condition: TriggerCondition
    _trigger_hold_time: float

    _loggable_signals: List[LoggableSignal]

    def __init__(self):
        self._decimation = 1
        self._probe_location = 0.5
        self._timeout = 0
        self._trigger_condition = TriggerCondition(TriggerConditionID.AlwaysTrue)
        self._trigger_hold_time = 0

        self._loggable_signals = []

    def add_signal(self, signal: LoggableSignal):
        if not isinstance(signal, LoggableSignal):
            raise ValueError('Requires a valid LoggableSignal object')

        self._loggable_signals.append(signal)

    def get_signals(self):
        return self._loggable_signals

    @property
    def decimation(self) -> int:
        return self._decimation

    @decimation.setter
    def decimation(self, v) -> int:
        v = int(v)
        if v <= 0:
            raise ValueError('Decimation must be a value greater than 0')

        self._decimation = v

    @property
    def probe_location(self) -> float:
        return self._probe_location

    @probe_location.setter
    def probe_location(self, v: float) -> None:
        v = float(v)
        if v < 0 or v > 1:
            raise ValueError('Probe location must be a value between 0 and 1')

        self._probe_location = v

    @property
    def timeout(self) -> float:
        return self._timeout

    @timeout.setter
    def timeout(self, v: float) -> None:
        v = float(v)
        if v < 0:
            raise ValueError('Timeout must be a value greater than 0')

        self._timeout = v

    @property
    def trigger_condition(self) -> TriggerCondition:
        return self._trigger_condition

    @trigger_condition.setter
    def trigger_condition(self, v: TriggerCondition) -> None:
        if not isinstance(v, TriggerCondition):
            raise ValueError("Expect a valid TriggerCondition object")

        self._trigger_condition = v

    @property
    def trigger_hold_time(self) -> float:
        return self._trigger_hold_time

    @trigger_hold_time.setter
    def trigger_hold_time(self, v: float) -> None:
        v = float(v)
        if v < 0:
            raise ValueError('Hold time must be a value greater than 0')

        self._trigger_hold_time = v
# endregion
