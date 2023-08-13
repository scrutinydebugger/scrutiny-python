
from scrutiny.core.datalogging import *
from dataclasses import dataclass
from scrutiny.sdk.watchable_handle import WatchableHandle
import enum
from typing import List, Dict, Union, Optional


class DataloggingEncoding(enum.Enum):
    RAW = 1


@dataclass(frozen=True)
class SamplingRate:
    identifier: int
    name: str


@dataclass(frozen=True)
class FixedFreqSamplingRate(SamplingRate):
    frequency: float


@dataclass(frozen=True)
class VariableFreqSamplingRate(SamplingRate):
    pass


@dataclass(frozen=True)
class DataloggingCapabilities:
    """Tells what the device is able to achieve in terms of datalogging"""

    encoding: DataloggingEncoding
    """The encoding of data"""

    buffer_size: int
    """Size of the datalogging buffer"""

    max_nb_signal: int
    """Maximum number of signal per acquisition (including time if measured)"""

    sampling_rates: List[SamplingRate]
    """List of available sampling rates"""


class XAxisType(enum.Enum):
    """Represent a type of X-Axis that a user can select"""

    IdealTime = 0,
    """Time deduced from the sampling frequency. Does not require space in the datalogging buffer. Only available for fixed frequency loops"""

    MeasuredTime = 1,
    """Time measured by the device. Requires space for a 32 bits value in the datalogging buffer"""

    Signal = 2
    """X-Axis is an arbitrary signal, not time."""


class TriggerCondition(enum.Enum):
    """The type of trigger condition to use."""

    AlwaysTrue = "true"
    """Always true. Triggers immediately after being armed"""

    Equal = "eq"
    """Operand1 == Operand2 """

    NotEqual = "neq"
    """Operand1 != Operand2 """

    LessThan = "get"
    """Operand1 < Operand2 """

    LessOrEqualThan = "gt"
    """Operand1 <= Operand2 """

    GreaterThan = "let"
    """Operand1 > Operand2 """

    GreaterOrEqualThan = "lt"
    """Operand1 >= Operand2 """

    ChangeMoreThan = "cmt"
    """X=(Operand1[n]-Operand1[n-1]); |X| > |Operand2| && sign(X) == sign(Operand2) """

    IsWithin = "within"
    """|Operand1 - Operand2| < |Operand3| """


@dataclass
class _Signal:
    name: Optional[str]
    path: str


@dataclass
class _SignalAxisPair(_Signal):
    name: Optional[str]
    path: str
    axis_id: int


@dataclass(init=False)
class DataloggingRequest:
    _sampling_rate: Union[int, str]
    _trigger_condition: TriggerCondition
    _x_axis_type: XAxisType
    _x_axis_signal: Optional[_Signal]
    _decimation: int
    _timeout: float
    _trigger_position: float
    _trigger_hold_time: float
    _name: str
    _trigger_operands: List[Union[WatchableHandle, float, str]]
    _axes: Dict[int, AxisDefinition]
    _signals: List[_SignalAxisPair]
    _next_axis_id: int

    def __init__(self,
                 sampling_rate: Union[int, str],
                 decimation: int = 1,
                 timeout: float = 0,
                 name: str = ''):

        self._sampling_rate = sampling_rate
        self._trigger_condition = TriggerCondition.AlwaysTrue
        self._x_axis_type = XAxisType.MeasuredTime
        self._x_axis_signal = None
        self._decimation = decimation
        self._timeout = timeout
        self._trigger_position = 0.5
        self._trigger_hold_time = 0
        self._name = name

        self._next_axis_id = 0
        self._trigger_operands = []
        self._signals = []
        self._axes = {}

    def add_axis(self, name: str) -> AxisDefinition:
        axis = AxisDefinition(axis_id=self._next_axis_id, name=name)
        self._next_axis_id += 1
        self._axes[axis.axis_id] = axis
        return axis

    def add_signal(self,
                   signal: Union[WatchableHandle, str],
                   axis: Union[AxisDefinition, int],
                   name: Optional[str] = None
                   ) -> None:
        if isinstance(axis, int):
            if axis not in self._axes:
                raise IndexError(f"No axis with index {axis}")
            assert self._axes[axis].axis_id == axis
            axis = self._axes[axis]
        elif isinstance(axis, AxisDefinition):
            if axis.axis_id not in self._axes or self._axes[axis.axis_id] is not axis:
                raise ValueError("Unknown axis given")
        else:
            raise TypeError(f'Expected axis to be an integer index or an Axis object. Got {axis.__class__.__name__}')

        axis_id = axis.axis_id

        signal_path: str
        if isinstance(signal, WatchableHandle):
            signal_path = signal.display_path
        elif isinstance(signal, str):
            signal_path = signal
        else:
            raise TypeError(f'Expected signal to be a valid path (string) or a watchable handle. Got {signal.__class__.__name__}')

        if name is not None and not isinstance(name, str):
            raise TypeError(f"name must be a string. Got {name.__class__.__name__}")

        self._signals.append(_SignalAxisPair(name=name, path=signal_path, axis_id=axis_id))

    def configure_trigger(self,
                          condition: TriggerCondition,
                          operands: Optional[List[Union[WatchableHandle, float, str]]] = None,
                          position: float = 0.5,
                          hold_time: float = 0
                          ) -> None:
        if condition in [TriggerCondition.AlwaysTrue]:
            nb_operands = 0
        elif condition in [TriggerCondition.Equal,
                           TriggerCondition.NotEqual,
                           TriggerCondition.GreaterThan,
                           TriggerCondition.GreaterOrEqualThan,
                           TriggerCondition.LessThan,
                           TriggerCondition.LessOrEqualThan,
                           TriggerCondition.ChangeMoreThan]:
            nb_operands = 2
        elif condition in [TriggerCondition.IsWithin]:
            nb_operands = 3
        else:
            raise ValueError(f"Unsupported trigger condition {condition}")

        if operands is None:
            operands = []

        if not isinstance(operands, list):
            raise TypeError("Operands must be a list or None")

        if nb_operands != len(operands):
            raise ValueError(f"Expected {nb_operands} for condition {condition.name}. Got {len(operands)}")

        for i in range(len(operands)):
            if not isinstance(operands[i], (float, int, WatchableHandle, str)):
                raise TypeError(
                    f"Operand {i+1} must be a constant (float), a path to the element (string) or a watchable handle. Got {operands[i].__class__.__name__}")

        self._trigger_condition = condition
        self._trigger_position = position
        self._trigger_hold_time = hold_time
        self._trigger_operands = operands

    def configure_xaxis(self,
                        axis_type: XAxisType,
                        signal: Optional[Union[str, WatchableHandle]] = None,
                        name: Optional[str] = None
                        ) -> None:
        if not isinstance(axis_type, XAxisType):
            raise TypeError("axis_type must be an instance of XAxisType")

        if name is not None and not isinstance(name, str):
            raise TypeError(f"name must be a string. Got {name.__class__.__name__}")

        signal_out: Optional[_Signal] = None
        if axis_type == XAxisType.Signal:
            if signal is None:
                raise ValueError('A signal must be given when X axis is set to "signal"')
            if isinstance(signal, str):
                signal_out = _Signal(name=name, path=signal)
            elif isinstance(signal, WatchableHandle):
                signal_out = _Signal(name=name, path=signal.display_path)
            else:
                raise TypeError(f"Expected signal to be a valid path (string) or a watchable handle. Got {signal.__class__.__name__}")

        self._x_axis_signal = signal_out
        self._x_axis_type = axis_type
