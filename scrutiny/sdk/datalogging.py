

from scrutiny import sdk
from scrutiny.core.datalogging import *
from dataclasses import dataclass
from scrutiny.sdk.watchable_handle import WatchableHandle
import enum
from typing import List, Dict, Union, Optional, TYPE_CHECKING
import scrutiny.server.api.typing as api_typing
import threading
from datetime import datetime

from scrutiny.server.api import API

if TYPE_CHECKING:
    from scrutiny.sdk.client import ScrutinyClient


class DataloggingEncoding(enum.Enum):
    """Defines the data format used to store the samples in the datalogging buffer"""
    RAW = 1


@dataclass(frozen=True, init=False)
class SamplingRate:
    """Represent a sampling rate supported by the device"""

    identifier: int
    """The unique identifier of the sampling rate. Matches the embedded device index in the loop array set in the configuration"""

    name: str
    """Name for display"""


@dataclass(frozen=True)
class FixedFreqSamplingRate(SamplingRate):
    """Represent a fixed frequency sampling rate supported by the device"""

    frequency: float
    """The sampling rate frequency"""


@dataclass(frozen=True)
class VariableFreqSamplingRate(SamplingRate):
    """Represent a variable frequency sampling rate supported by the device. Has no known frequency"""
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

    Indexed = "index"
    """No signal will be captured for the X-Axis and the returned X-Axis data will be the index of the samples"""

    IdealTime = 'ideal_time'
    """Time deduced from the sampling frequency. Does not require space in the datalogging buffer. Only available for fixed frequency loops"""

    MeasuredTime = 'measured_time'
    """Time measured by the device. Requires space for a 32 bits value in the datalogging buffer"""

    Signal = 'signal'
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
class DataloggingConfig:
    """A datalogging acquisition configuration. Contains all the configurable parameters for an acquisition"""

    _sampling_rate: int
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
                 sampling_rate: Union[int, SamplingRate],
                 decimation: int = 1,
                 timeout: float = 0.0,
                 name: str = ''):

        if isinstance(sampling_rate, SamplingRate):
            sampling_rate = sampling_rate.identifier

        if not isinstance(sampling_rate, int):
            raise TypeError('sampling_rate must be a int')

        if not isinstance(decimation, int):
            raise TypeError('decimation must be a int')

        if decimation <= 0:
            raise ValueError('decimation must be a positive integer')

        if isinstance(timeout, int):
            timeout = float(timeout)
        if not isinstance(timeout, float):
            raise TypeError('timeout must be a float')
        if timeout < 0 or timeout > API.DATALOGGING_MAX_TIMEOUT:
            raise ValueError(f"timeout must be a number between 0 and {API.DATALOGGING_MAX_TIMEOUT}")

        if not isinstance(name, str):
            raise TypeError('name must be a string')

        self._sampling_rate = sampling_rate
        self._trigger_condition = TriggerCondition.AlwaysTrue
        self._x_axis_type = XAxisType.Indexed
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
        """Adds a Y axis to the acquisition. Returns an object that can be assigned to a signal when calling `add_signal`"""
        if not isinstance(name, str):
            raise TypeError("name must be a string")
        axis = AxisDefinition(axis_id=self._next_axis_id, name=name)
        self._next_axis_id += 1
        self._axes[axis.axis_id] = axis
        return axis

    def add_signal(self,
                   signal: Union[WatchableHandle, str],
                   axis: Union[AxisDefinition, int],
                   name: Optional[str] = None
                   ) -> None:
        """Adds a signal to the acquisition"""
        if isinstance(axis, int) and not isinstance(axis, bool):
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
        """Configure the required conditions to fire the trigger event"""
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

        if isinstance(position, int) and not isinstance(position, bool):
            position = float(position)
        if not isinstance(position, float):
            raise TypeError('position must be a float')
        if position < 0 or position > 1:
            raise ValueError(f"position must be a number between 0 and 1")

        if isinstance(hold_time, int) and not isinstance(hold_time, bool):
            hold_time = float(hold_time)
        if not isinstance(hold_time, float):
            raise TypeError('hold_time must be a float')
        if hold_time < 0 or hold_time > API.DATALOGGING_MAX_HOLD_TIME:
            raise ValueError(f"hold_time must be a number between 0 and {API.DATALOGGING_MAX_HOLD_TIME}")

        self._trigger_condition = condition
        self._trigger_position = position
        self._trigger_hold_time = hold_time
        self._trigger_operands = operands

    def configure_xaxis(self,
                        axis_type: XAxisType,
                        signal: Optional[Union[str, WatchableHandle]] = None,
                        name: Optional[str] = None
                        ) -> None:
        """Configure the X-Axis"""
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

    def _get_api_yaxes(self) -> List[api_typing.DataloggingAxisDef]:
        return [dict(id=x.axis_id, name=x.name) for x in self._axes.values()]

    def _get_api_x_axis_signal(self) -> Optional[api_typing.XAxisSignal]:
        if self._x_axis_signal is None:
            return None
        return {"path": self._x_axis_signal.path, "name": self._x_axis_signal.name}

    def _get_api_trigger_operands(self) -> List[api_typing.DataloggingOperand]:
        out_list: List[api_typing.DataloggingOperand] = []
        for operand in self._trigger_operands:
            if isinstance(operand, (float, int)):
                out_list.append({"type": 'literal', "value": float(operand)})
            elif isinstance(operand, WatchableHandle):
                out_list.append({"type": 'watchable', "value": operand.display_path})
            else:
                raise RuntimeError(f'Unsupported operand type {operand.__class__.__name__}')
        return out_list

    def _get_api_signals(self) -> List[api_typing.DataloggingAcquisitionRequestSignalDef]:
        return [{'path': x.path, 'name': x.name, 'axis_id': x.axis_id} for x in self._signals]


@dataclass(init=False)
class DataloggingRequest:
    _client: "ScrutinyClient"
    _request_token: str

    _success: bool  # If the request has been successfully completed
    _completion_datetime: Optional[datetime]   # datetime of the completion. None if incomplete
    _completed_event: threading.Event   # Event that gets set upon completion of the request
    _failure_reason: str    # Textual description of the reason of the failure to complete. Empty string if incomplete or succeeded
    _acquisition_reference_id: Optional[str]

    def __init__(self, client: "ScrutinyClient", request_token: str):
        self._client = client
        self._request_token = request_token
        self._completed = False
        self._success = False
        self._completion_datetime = None
        self._completed_event = threading.Event()
        self._failure_reason = ""
        self._acquisition_reference_id = None

    def _mark_complete(self, success: bool, reference_id: Optional[str], failure_reason: str = "", timestamp: Optional[datetime] = None):
        # Put a request in "completed" state. Expected to be called by the client worker thread
        self._success = success
        self._failure_reason = failure_reason
        if timestamp is None:
            self._completion_datetime = datetime.now()
        else:
            self._completion_datetime = timestamp
        if success:
            assert reference_id is not None
        self._acquisition_reference_id = reference_id
        self._completed = True
        self._completed_event.set()

    def wait_for_completion(self, timeout: Optional[float] = None):
        """Wait for the acquisition to be triggered and extracted by the server. Once this is done, the `acquisition_reference_id` will not be `None` anymore
        and its value will point to the database entry storing the data.

        :params timeout: Maximum wait time in seconds. Waits forever if `None`

        :raises sdk.exceptions.TimeoutException: If the acquisition does not complete in less than the specified timeout value
        :raises sdk.exceptions.OperationFailure: If an error happened that prevented the acquisition to successfully complete
        """
        self._completed_event.wait(timeout=timeout)
        if not self._completed:
            raise sdk.exceptions.TimeoutException(f"Datalogging acquisition did not complete in {timeout} seconds")
        assert self._completed_event.is_set()

        if not self._success:
            raise sdk.exceptions.OperationFailure(f"Datalogging acquisition failed to complete. {self._failure_reason}")

    def fetch_acquisition(self, timeout=None) -> DataloggingAcquisition:
        """Download and returns an the acquisition data from the server. The acquisition must be complete

        :params timeout: Timeout to get a response by the server in seconds. Uee the default timeout value if `None`

        :raises sdk.exceptions.TimeoutException: If the server does not respond in time
        :raises sdk.exceptions.OperationFailure: If the acquisition is not complete or if an error happen while fetching the data

        """
        if not self._completed:
            raise sdk.exceptions.OperationFailure('Acquisition is not complete yet')

        if self._acquisition_reference_id is None:
            raise sdk.exceptions.OperationFailure('Reference ID is not set.')   # Should not happen

        return self._client.read_datalogging_acquisition(self._acquisition_reference_id, timeout)

    def wait_and_fetch(self, timeout: Optional[float] = None, fetch_timeout: Optional[float] = None):
        """Do successive calls to `wait_for_completion()` & `fetch_acquisition()` and return the acquisition

        :params timeout: Timeout given to `wait_for_completion()`
        :params fetch_timeout: Timeout given to `fetch_acquisition()`

        :raises sdk.exceptions.TimeoutException: If any of the timeout is violated
        :raises sdk.exceptions.OperationFailure: If a problem occur while waiting/fetching
        """
        self.wait_for_completion(timeout)
        return self.fetch_acquisition(fetch_timeout)  # Use default timeout

    @property
    def completed(self) -> bool:
        """Indicates whether the datalogging acquisition request has completed or not"""
        return self._completed_event.is_set()

    @property
    def is_success(self) -> bool:
        """Indicates whether the datalogging acquisition request has successfully completed or not"""
        return self._success

    @property
    def completion_datetime(self) -> Optional[datetime]:
        """The time at which the datalogging acquisition request has been completed. None if not completed yet"""
        return self._completion_datetime

    @property
    def failure_reason(self) -> str:
        """When the datalogging acquisition request failed, this property contains the reason for the failure. Empty string if not completed or succeeded"""
        return self._failure_reason

    @property
    def acquisition_reference_id(self) -> Optional[str]:
        """The unique ID used to fetch the acquisition data from the server. Value is set only if request is completed and succeeded. None otherwise"""
        return self._acquisition_reference_id
