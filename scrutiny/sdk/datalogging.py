#    datalogging.py
#        Defines all the types used for datalogging in the SDK
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from scrutiny import sdk
from scrutiny.core.datalogging import *
from scrutiny.core import validation
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
    """(Enum) Defines the data format used to store the samples in the datalogging buffer"""
    RAW = 1


@dataclass(frozen=True, init=False)
class SamplingRate:
    """(Immutable struct) Represent a sampling rate supported by the device"""

    identifier: int
    """The unique identifier of the sampling rate. Matches the embedded device index in the loop array set in the configuration"""

    name: str
    """Name for display"""


@dataclass(frozen=True)
class FixedFreqSamplingRate(SamplingRate):
    """(Immutable struct) Represent a fixed frequency sampling rate supported by the device"""

    frequency: float
    """The sampling rate frequency"""

    def __post_init__(self) -> None:
        validation.assert_type(self.identifier, 'identifier', int)
        validation.assert_type(self.name, 'name', str)
        validation.assert_type(self.frequency, 'frequency', float)


@dataclass(frozen=True)
class VariableFreqSamplingRate(SamplingRate):
    """(Immutable struct) Represent a variable frequency sampling rate supported by the device. Has no known frequency"""

    def __post_init__(self) -> None:
        validation.assert_type(self.identifier, 'identifier', int)
        validation.assert_type(self.name, 'name', str)


@dataclass(frozen=True)
class DataloggingCapabilities:
    """(Immutable struct) Tells what the device is able to achieve in terms of datalogging"""

    encoding: DataloggingEncoding
    """The encoding of data"""

    buffer_size: int
    """Size of the datalogging buffer"""

    max_nb_signal: int
    """Maximum number of signal per acquisition (including time if measured)"""

    sampling_rates: List[SamplingRate]
    """List of available sampling rates"""

    def __post_init__(self) -> None:
        validation.assert_type(self.encoding, 'encoding', DataloggingEncoding)
        validation.assert_type(self.buffer_size, 'buffer_size', int)
        validation.assert_type(self.max_nb_signal, 'max_nb_signal', int)
        validation.assert_type(self.sampling_rates, 'sampling_rates', list)
        for i in range(len(self.sampling_rates)):
            validation.assert_type(self.sampling_rates[i], f'sampling_rates[{i}]', SamplingRate)


class XAxisType(enum.Enum):
    """(Enum) Represent a type of X-Axis that a user can select"""

    Indexed = "index"
    """No signal will be captured for the X-Axis and the returned X-Axis data will be the index of the samples"""

    IdealTime = 'ideal_time'
    """Time deduced from the sampling frequency. Does not require space in the datalogging buffer. Only available for fixed frequency loops"""

    MeasuredTime = 'measured_time'
    """Time measured by the device. Requires space for a 32 bits value in the datalogging buffer"""

    Signal = 'signal'
    """X-Axis is an arbitrary signal, not time."""


class TriggerCondition(enum.Enum):
    """(Enum) The type of trigger condition to use."""

    AlwaysTrue = "true"
    """Always true. Triggers immediately after being armed"""

    Equal = "eq"
    """Operand1 == Operand2 """

    NotEqual = "neq"
    """Operand1 != Operand2 """

    LessThan = "lt"
    """Operand1 < Operand2 """

    LessOrEqualThan = "let"
    """Operand1 <= Operand2 """

    GreaterThan = "gt"
    """Operand1 > Operand2 """

    GreaterOrEqualThan = "get"
    """Operand1 >= Operand2 """

    ChangeMoreThan = "cmt"
    """X=(Operand1[n]-Operand1[n-1]); `|X|` > `|Operand2|` && sign(X) == sign(Operand2) """

    IsWithin = "within"
    """`|Operand1 - Operand2|` < `|Operand3|` """


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
        """Creates an instance of :class:`DataloggingConfig<DataloggingConfig>`

        :param sampling_rate: The acquisition sampling rate. Can be the sampling rate ID in the device or an instance 
            of :class:`SamplingRate<scrutiny.sdk.datalogging.SamplingRate>` gotten from the :class:`DataloggingCapabilities<scrutiny.sdk.datalogging.DataloggingCapabilities>` 
            returned by :meth:`ScrutinyClient.get_datalogging_capabilities<scrutiny.sdk.client.ScrutinyClient.get_datalogging_capabilities>` 
        :param decimation: The decimation factor that reduces the effective sampling rate
        :param timeout: Timeout to the acquisition. After the datalogger is armed, it will forcefully trigger after this amount of time. 0 means no timeout
        :param name: Name of the configuration. Save into the database for reference

        :raise TypeError: Given parameter not of the expected type
        :raise ValueError: Given parameter has an invalid value
        """

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
        """Adds a Y axis to the acquisition.
        :param name: The name of the axis, for display purpose. 

        :return: An `AxisDefinition` object that can be assigned to a signal when calling :meth:`add_signal()<scrutiny.sdk.datalogging.DataloggingConfig.add_signal>`
        """
        validation.assert_type(name, 'name', str)
        axis = AxisDefinition(axis_id=self._next_axis_id, name=name)
        self._next_axis_id += 1
        self._axes[axis.axis_id] = axis
        return axis

    def add_signal(self,
                   signal: Union[WatchableHandle, str],
                   axis: Union[AxisDefinition, int],
                   name: Optional[str] = None
                   ) -> None:
        """Adds a signal to the acquisition

        :param signal: The signal to add. Can either be a path to a var/rpv/alias (string) or a :class:`WatchableHandle<scrutiny.sdk.watchable_handle.WatchableHandle>` 
            given by :meth:`ScrutinyClient.watch()<scrutiny.sdk.client.ScrutinyClient.watch>`
        :param axis: The Y axis to assigned this signal to. Can either be the index (int) or the :class:`AxisDefinition<scrutiny.sdk.datalogging.AxisDefinition>` 
            object given by :meth:`add_axis()<scrutiny.sdk.datalogging.DataloggingConfig.add_axis>`
        :param name: A display name for the signal

        :raise IndexError: Invalid axis index
        :raise ValueError: Bad parameter value
        :raise TypeError: Given parameter not of the expected type

        """
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

        validation.assert_type(name, 'name', (str, type(None)))
        if name is None:
            name = signal_path.split('/')[-1]

        self._signals.append(_SignalAxisPair(name=name, path=signal_path, axis_id=axis_id))

    def configure_trigger(self,
                          condition: TriggerCondition,
                          operands: Optional[List[Union[WatchableHandle, float, str]]] = None,
                          position: float = 0.5,
                          hold_time: float = 0
                          ) -> None:
        r"""Configure the required conditions to fire the trigger event

        :param condition: The type of condition used for triggering the acquisition.   
        :param operands: List of operands. Each operands can be a constant number (float), the path to a variable/rpv/alias (str) or a :class:`WatchableHandle<scrutiny.sdk.watchable_handle.WatchableHandle>`
            given by :meth:`ScrutinyClient.watch()<scrutiny.sdk.client.ScrutinyClient.watch>`. The number of operands depends on the trigger condition
        :param position: Position of the trigger event in the datalogging buffer. Value from 0 to 1, where 0 is leftmost, 0.5 middle and 1 rightmost.
        :param hold_time: Time in seconds that the trigger condition must evaluate to `true` before firing the trigger event.

        :raise ValueError: Bad parameter value
        :raise TypeError: Given parameter not of the expected type
        """
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

        validation.assert_type(operands, 'operands', (list, type(None)))

        if operands is None:
            operands = []

        if nb_operands != len(operands):
            raise ValueError(f"Expected {nb_operands} for condition {condition.name}. Got {len(operands)}")

        for i in range(len(operands)):
            if not isinstance(operands[i], (float, int, WatchableHandle, str)):
                raise TypeError(
                    f"Operand {i+1} must be a constant (float), a path to the element (string) or a watchable handle. Got {operands[i].__class__.__name__}")

        position = validation.assert_float_range(position, 'position', 0, 1)
        hold_time = validation.assert_float_range(hold_time, 'hold_time', 0, API.DATALOGGING_MAX_HOLD_TIME)

        self._trigger_condition = condition
        self._trigger_position = position
        self._trigger_hold_time = hold_time
        self._trigger_operands = operands

    def configure_xaxis(self,
                        axis_type: XAxisType,
                        signal: Optional[Union[str, WatchableHandle]] = None,
                        name: Optional[str] = None
                        ) -> None:
        """Configures the X-Axis

        :param axis_type: Type of X-Axis.  
        :param signal: The signal to be used for the X-Axis if its type is set to :attr:`Signal<scrutiny.sdk.datalogging.XAxisType.Signal>`. 
            Ignored if the X-Axis type is not :attr:`Signal<scrutiny.sdk.datalogging.XAxisType.Signal>`. Can be the path to a watchable or an instance 
            of a :class:`WatchableHandle<scrutiny.sdk.watchable_handle.WatchableHandle>`
            given by :meth:`ScrutinyClient.watch()<scrutiny.sdk.client.ScrutinyClient.watch>` 
        :param name: A display name for the X-Axis

        :raise ValueError: Bad parameter value
        :raise TypeError: Given parameter not of the expected type
        """
        validation.assert_type(axis_type, 'axis_type', XAxisType)
        validation.assert_type(name, 'name', (str, type(None)))

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
    """Handle to a request for a datalogging acquisition. Gets updated by the client and reflects the actual status of the acquisition"""

    _client: "ScrutinyClient"
    _request_token: str

    _success: bool  # If the request has been successfully completed
    _completion_datetime: Optional[datetime]   # datetime of the completion. None if incomplete
    _completed_event: threading.Event   # Event that gets set upon completion of the request
    _failure_reason: str    # Textual description of the reason of the failure to complete. Empty string if incomplete or succeeded
    _acquisition_reference_id: Optional[str]

    def __init__(self, client: "ScrutinyClient", request_token: str) -> None:
        self._client = client
        self._request_token = request_token
        self._completed = False
        self._success = False
        self._completion_datetime = None
        self._completed_event = threading.Event()
        self._failure_reason = ""
        self._acquisition_reference_id = None

    def _mark_complete(self, success: bool, reference_id: Optional[str], failure_reason: str = "", timestamp: Optional[datetime] = None) -> None:
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

    def wait_for_completion(self, timeout: Optional[float] = None) -> None:
        """Wait for the acquisition to be triggered and extracted by the server. Once this is done, 
        the :attr:`acquisition_reference_id<acquisition_reference_id>` will not be ``None`` anymore
        and its value will point to the database entry storing the data.

        :params timeout: Maximum wait time in seconds. Waits forever if ``None``

        :raise TimeoutException: If the acquisition does not complete in less than the specified timeout value
        :raise OperationFailure: If an error happened that prevented the acquisition to successfully complete
        """
        timeout = validation.assert_float_range_if_not_none(timeout, 'timeout', minval=0)
        self._completed_event.wait(timeout=timeout)
        if not self._completed:
            raise sdk.exceptions.TimeoutException(f"Datalogging acquisition did not complete in {timeout} seconds")
        assert self._completed_event.is_set()

        if not self._success:
            raise sdk.exceptions.OperationFailure(f"Datalogging acquisition failed to complete. {self._failure_reason}")

    def fetch_acquisition(self, timeout: Optional[float] = None) -> DataloggingAcquisition:
        """Download and returns an acquisition data from the server. The acquisition must be complete

        :params timeout: Timeout to get a response by the server in seconds. Uses the default timeout value if ``None``

        :raise TimeoutException: If the server does not respond in time
        :raise OperationFailure: If the acquisition is not complete or if an error happens while fetching the data

        :return: The :class:`DataloggingAcquisition<scrutiny.core.datalogging.DataloggingAcquisition>` object containing the acquired data

        """
        timeout = validation.assert_float_range_if_not_none(timeout, 'timeout', minval=0)

        if not self._completed:
            raise sdk.exceptions.OperationFailure('Acquisition is not complete yet')

        if self._acquisition_reference_id is None:
            raise sdk.exceptions.OperationFailure('Reference ID is not set.')   # Should not happen

        return self._client.read_datalogging_acquisition(self._acquisition_reference_id, timeout)

    def wait_and_fetch(self, timeout: Optional[float] = None, fetch_timeout: Optional[float] = None) -> DataloggingAcquisition:
        """Do successive calls to :meth:`wait_for_completion()<wait_for_completion>` 
        & :meth:`fetch_acquisition()<fetch_acquisition>` and return the acquisition

        :params timeout: Timeout given to :meth:`wait_for_completion()<wait_for_completion>`
        :params fetch_timeout: Timeout given to :meth:`fetch_acquisition()<fetch_acquisition>`

        :raise TimeoutException: If any of the timeout is violated
        :raise OperationFailure: If a problem occur while waiting/fetching

        :return: The :class:`DataloggingAcquisition<scrutiny.core.datalogging.DataloggingAcquisition>` object containing the acquired data
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
        """The time at which the datalogging acquisition request has been completed. ``None`` if not completed yet"""
        return self._completion_datetime

    @property
    def failure_reason(self) -> str:
        """When the datalogging acquisition request failed, this property contains the reason for the failure. Empty string if not completed or succeeded"""
        return self._failure_reason

    @property
    def acquisition_reference_id(self) -> Optional[str]:
        """The unique ID used to fetch the acquisition data from the server. Value is set only if request is completed and succeeded. ``None`` otherwise"""
        return self._acquisition_reference_id


@dataclass(frozen=True)
class DataloggingStorageEntry:
    """(Immutable struct) Represent an entry in datalogging storage"""

    reference_id: str
    """Database ID used to uniquely identified this acquisition"""

    firmware_id: str
    """Firmware ID of the device that took the acquisition"""

    name: str
    """Name of the acquisition. For display purpose"""

    timestamp: datetime
    """Date/Time at which the acquisition was captured"""

    firmware_metadata: Optional[sdk.SFDMetadata]
    """The metadata of the firmware used by the device if available"""

    def __post_init__(self) -> None:
        validation.assert_type(self.reference_id, 'reference_id', str)
        validation.assert_type(self.firmware_id, 'firmware_id', str)
        validation.assert_type(self.name, 'name', str)
        validation.assert_type(self.timestamp, 'timestamp', datetime)
        validation.assert_type(self.firmware_metadata, 'firmware_metadata', (sdk.SFDMetadata, type(None)))
