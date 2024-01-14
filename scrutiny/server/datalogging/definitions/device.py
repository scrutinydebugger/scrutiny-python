#    device.py
#        Contains the definitions related to the datalogging feature on the device side. Shared
#        between the DataloggingManager and the DeviceHandler
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from enum import Enum
from typing import Union, List
from abc import ABC, abstractmethod
from dataclasses import dataclass

from scrutiny.core.basic_types import EmbeddedDataType


class Encoding(Enum):
    """Represent a type of data encoding used by the device. Matches the device definition"""
    RAW = 0


class TriggerConditionID(Enum):
    """The ID of the trigger condition to use. Matches the device definition."""
    AlwaysTrue = 0          # Always true
    Equal = 1               # Operand1 == Operand2
    NotEqual = 2            # Operand1 != Operand2
    LessThan = 3            # Operand1 < Operand2
    LessOrEqualThan = 4     # Operand1 <= Operand2
    GreaterThan = 5         # Operand1 > Operand2
    GreaterOrEqualThan = 6  # Operand1 >= Operand2
    ChangeMoreThan = 7      # X=(Operand1[n]-Operand1[n-1]); |X| > |Operand2| && sign(X) == sign(Operand2)
    IsWithin = 8            # |Operand1 - Operand2| < |Operand3|


class DataloggerState(Enum):
    """Represent the state of the device datalogging internal state machine. Matches the device definition"""
    IDLE = 0
    CONFIGURED = 1
    ARMED = 2
    TRIGGERED = 3
    ACQUISITION_COMPLETED = 4
    ERROR = 5


@dataclass
class DataloggingSetup:
    """Represent the device datalogging global parameters."""
    buffer_size: int
    encoding: Encoding
    max_signal_count: int


@dataclass
class AcquisitionMetadata:
    """Represent the metadata attached to an acquisition given by the device"""
    acquisition_id: int
    config_id: int
    number_of_points: int
    data_size: int
    points_after_trigger: int


class OperandType(Enum):
    """Represent a type of operand that can be used for a trigger condition. Matches the device definition"""
    Literal = 0
    Var = 1
    VarBit = 2
    RPV = 3


class Operand(ABC):
    @abstractmethod
    def get_type(self) -> OperandType:
        raise NotImplementedError("Not implemented")


class LiteralOperand(Operand):
    """An operand with a literal value"""
    value: float

    def __init__(self, value: Union[float, int]):
        self.value = float(value)

    def get_type(self) -> OperandType:
        return OperandType.Literal


class VarOperand(Operand):
    """An operand that refers to a variable in memory"""
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
    """An operand that refers to a variable in memory that uses bitfield"""
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
    """An operand that refers to a Runtime Published Value"""
    rpv_id: int

    def __init__(self, rpv_id: int):
        if not isinstance(rpv_id, int):
            raise ValueError("Given operand requires a int")

        self.rpv_id = rpv_id

    def get_type(self) -> OperandType:
        return OperandType.RPV


class LoggableSignalType(Enum):
    """Represent a type of loggable signal that can be given to the device. Matches the device definition"""
    MEMORY = 0
    RPV = 1
    TIME = 2


class LoggableSignal:
    signal_type: LoggableSignalType

    @abstractmethod
    def get_type(self) -> LoggableSignalType:
        raise NotImplementedError("Not implemented")


class MemoryLoggableSignal(LoggableSignal):
    """A loggable data fetched from memory"""
    address: int
    size: int

    def __init__(self, address: int, size: int):
        if not isinstance(address, int):
            raise ValueError("Given address must be an int")

        if not isinstance(size, int):
            raise ValueError("Given size must be an int")

        self.address = address
        self.size = size

    def get_type(self) -> LoggableSignalType:
        return LoggableSignalType.MEMORY


class RPVLoggableSignal(LoggableSignal):
    """A loggable data fetched from Runtime Published Value reading"""
    rpv_id: int

    def __init__(self, rpv_id: int):
        if not isinstance(rpv_id, int):
            raise ValueError("Given rpv_id must be an int")
        self.rpv_id = rpv_id

    def get_type(self) -> LoggableSignalType:
        return LoggableSignalType.RPV


class TimeLoggableSignal(LoggableSignal):
    """A loggable data that represent the time, in device time step (100ns)"""

    def __init__(self) -> None:
        pass

    def get_type(self) -> LoggableSignalType:
        return LoggableSignalType.TIME


class TriggerCondition:
    operands: List[Operand]
    condition_id: TriggerConditionID

    def __init__(self, condition_id: TriggerConditionID, *args: Operand) -> None:
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
        return self.condition_id


class Configuration:
    """Represent a datalogging configuration that can be sent to the device to launch an acquisition """

    _decimation: int
    """Subsampling. Divide the sampling frequency"""

    _probe_location: float
    """Location of the trigger point in the buffer. Value from 0 to 1 where 0 is leftmost and 1 is rightmost"""

    _timeout: float
    """Acquisition timeout in seconds. Device will stop acquiring if it stays in Acquiring state for this amount of time. Ignored if 0"""

    _trigger_condition: TriggerCondition
    """The condition that triggers the trigger graph"""

    _trigger_hold_time: float
    """Amount of time, in seconds, that the trigger condition must be true for the trigger to triggered"""

    _loggable_signals: List[LoggableSignal]
    """List of signals to log during the acquisition"""

    def __init__(self) -> None:
        self._decimation = 1
        self._probe_location = 0.5
        self._timeout = 0
        self._trigger_condition = TriggerCondition(TriggerConditionID.AlwaysTrue)
        self._trigger_hold_time = 0

        self._loggable_signals = []

    def add_signal(self, signal: LoggableSignal) -> None:
        if not isinstance(signal, LoggableSignal):
            raise ValueError('Requires a valid LoggableSignal object')

        self._loggable_signals.append(signal)

    def get_signals(self) -> List[LoggableSignal]:
        return self._loggable_signals

    @property
    def decimation(self) -> int:
        """The acquisition decimation (subsampling factor). A value of 10 will cause the device to log 1 sample each 10 loops iteration."""
        return self._decimation

    @decimation.setter
    def decimation(self, v: int) -> None:
        v = int(v)
        if v <= 0:
            raise ValueError('Decimation must be a value greater than 0')

        self._decimation = v

    @property
    def probe_location(self) -> float:
        """The desired location of the trigger point in the buffer. A value of 0 cause the trigger event to be at the beginning of the data.
        A value of 1 cause the trigger event to be at the end of the data. Any value between 0 and 1 will be linearly interpolated, causing a value of 0.5
        to position the trigger event in the middle of the data window"""
        return self._probe_location

    @probe_location.setter
    def probe_location(self, v: float) -> None:
        v = float(v)
        if v < 0 or v > 1:
            raise ValueError('Probe location must be a value between 0 and 1')

        self._probe_location = v

    @property
    def timeout(self) -> float:
        """Maximum acquisition time in seconds. A value of 0 means no timeout."""
        return self._timeout

    @timeout.setter
    def timeout(self, v: float) -> None:
        v = float(v)
        if v < 0:
            raise ValueError('Timeout must be a value greater than 0')

        self._timeout = v

    @property
    def trigger_condition(self) -> TriggerCondition:
        """The trigger condition"""
        return self._trigger_condition

    @trigger_condition.setter
    def trigger_condition(self, v: TriggerCondition) -> None:
        if not isinstance(v, TriggerCondition):
            raise ValueError("Expect a valid TriggerCondition object")

        self._trigger_condition = v

    @property
    def trigger_hold_time(self) -> float:
        """The amount of time that the trigger condition must be held true before the device mark the sample as the trigger point. Value in seconds"""
        return self._trigger_hold_time

    @trigger_hold_time.setter
    def trigger_hold_time(self, v: float) -> None:
        v = float(v)
        if v < 0:
            raise ValueError('Hold time must be a value greater than 0')

        self._trigger_hold_time = v
