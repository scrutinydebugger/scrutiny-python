#    _api_parser.py
#        Internal parsing function for the Scrutiny server API messages
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

import scrutiny.sdk as sdk
from typing import *
from scrutiny.core.basic_types import *
from scrutiny.server.api.API import API
from scrutiny.server.api import typing as api_typing
from dataclasses import dataclass
from datetime import datetime
from base64 import b64decode
import binascii
import time


@dataclass
class WatchableConfiguration:
    watchable_type: sdk.WatchableType
    datatype: EmbeddedDataType
    server_id: str


@dataclass
class WatchableUpdate:
    server_id: str
    value: Union[bool, int, float]


@dataclass
class WriteCompletion:
    request_token: str
    watchable: str
    success: bool
    timestamp: datetime
    batch_index: int


@dataclass
class WriteConfirmation:
    request_token: str
    count: int


@dataclass
class MemoryReadCompletion:
    request_token: str
    success: bool
    data: Optional[bytes]
    error: str
    timestamp: float


T = TypeVar('T', str, int, float, bool)


def _check_response_dict(cmd: str, d: Any, name: str, types: Union[Type, Iterable[Type]], previous_parts: str = '') -> None:
    if isinstance(types, type):
        types = tuple([types])
    else:
        types = tuple(types)

    parts = name.split('.')
    key = parts[0]

    if not key:
        return

    if previous_parts:
        part_name = f"{previous_parts}.{key}"
    else:
        part_name = key
    next_parts = parts[1:]

    if key not in d:
        raise sdk.exceptions.BadResponseError(f'Missing field {part_name} in message "{cmd}"')

    if len(next_parts) > 0:
        if not isinstance(d, dict):
            raise sdk.exceptions.BadResponseError(f'Field {part_name} is expected to be a dictionary in message "{cmd}"')

        _check_response_dict(cmd, d[key], '.'.join(next_parts), types, part_name)
    else:

        if not isinstance(d[key], types):
            gotten_type = d[key].__class__.__name__
            typename = "(%s)" % ', '.join([t.__name__ for t in types])
            raise sdk.exceptions.BadResponseError(
                f'Field {part_name} is expected to be of type "{typename}" but found "{gotten_type}" in message "{cmd}"')


def _fetch_dict_val(d: Any, path: str, wanted_type: Type[T], default: Optional[T], allow_none=True) -> Optional[T]:
    if d is None:
        return default
    assert isinstance(d, dict)
    parts = path.split('.')
    key = parts[0]
    next_parts = parts[1:]

    if not key:
        raise RuntimeError('Empty path to fetch from dict')

    if key not in d:
        return default

    if len(next_parts) == 0:
        if d[key] is None:
            if allow_none:
                return None
            raise sdk.exceptions.BadResponseError(f'Field {key} cannot be None')
        return wanted_type(d[key])
    else:
        return _fetch_dict_val(d[key], '.'.join(next_parts), wanted_type=wanted_type, default=default)


def _fetch_dict_val_no_none(d: Any, path: str, wanted_type: Type[T], default: T) -> T:
    return cast(T, _fetch_dict_val(d, path, wanted_type, default, allow_none=False))


def parse_get_watchable_single_element(response: api_typing.S2C.GetWatchableList, requested_path: str) -> WatchableConfiguration:
    """Parse a response to get_watchable_list and assume the request was for a single watchable"""
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.GET_WATCHABLE_LIST_RESPONSE

    _check_response_dict(cmd, response, 'qty.alias', int)
    _check_response_dict(cmd, response, 'qty.rpv', int)
    _check_response_dict(cmd, response, 'qty.var', int)
    _check_response_dict(cmd, response, 'done', bool)

    total = response['qty']['alias'] + response['qty']['rpv'] + response['qty']['var']
    if total == 0:
        raise sdk.exceptions.NameNotFoundError(f'No watchable element matches the path {requested_path} on the server')

    if total > 1:
        raise sdk.exceptions.BadResponseError(f"More than one item were returned by the server that matched the path {requested_path}")

    if response['done'] != True:
        raise sdk.exceptions.BadResponseError(f"done field should be True")

    _check_response_dict(cmd, response, 'content.alias', list)
    _check_response_dict(cmd, response, 'content.rpv', list)
    _check_response_dict(cmd, response, 'content.var', list)

    watchable_type: sdk.WatchableType = sdk.WatchableType.NA
    content: Any = None
    WatchableTypeKey = Literal['rpv', 'alias', 'var']

    typekey: WatchableTypeKey
    if response['qty']['alias'] == 1:
        watchable_type = sdk.WatchableType.Alias
        typekey = 'alias'
    elif response['qty']['rpv']:
        watchable_type = sdk.WatchableType.RuntimePulishedValue
        content = response['content']['rpv']
        typekey = 'rpv'
    elif response['qty']['var']:
        watchable_type = sdk.WatchableType.Variable
        typekey = 'var'
    else:
        raise sdk.exceptions.BadResponseError('Unknown watchable type')

    key: WatchableTypeKey
    for key in get_args(WatchableTypeKey):
        expected_count = 1 if key == typekey else 0
        if len(response['content'][key]) != expected_count:
            raise sdk.exceptions.BadResponseError("Incoherent element quantity in API response.")

    content = cast(dict, response['content'][typekey][0])
    keyprefix = f'content.{typekey}[0]'
    _check_response_dict(cmd, content, 'id', str, keyprefix)
    _check_response_dict(cmd, content, 'display_path', str, keyprefix)
    _check_response_dict(cmd, content, 'datatype', str, keyprefix)

    if content['datatype'] not in API.APISTR_2_DATATYPE:
        raise sdk.exceptions.BadResponseError(f"Unknown datatype {content['datatype']}")

    datatype = EmbeddedDataType(API.APISTR_2_DATATYPE[content['datatype']])

    if requested_path != content['display_path']:
        raise sdk.exceptions.BadResponseError(
            f"The display path of the element returned by the server does not matched the requested path. Got {content['display_path']} but expected {requested_path}")

    if not isinstance(content['id'], str):
        raise sdk.exceptions.BadResponseError(f"Invalid server id received for watchable {requested_path}")

    return WatchableConfiguration(
        watchable_type=watchable_type,
        datatype=datatype,
        server_id=content['id']
    )


def parse_inform_server_status(response: api_typing.S2C.InformServerStatus) -> sdk.ServerInfo:
    """Parse the inform_server_status message"""

    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.INFORM_SERVER_STATUS
    NoneType: Type = type(None)

    _check_response_dict(cmd, response, 'device_status', str)
    _check_response_dict(cmd, response, 'device_session_id', (str, NoneType))

    def _device_status_from_api(api_val: api_typing.DeviceCommStatus) -> sdk.DeviceCommState:
        if api_val == API.DeviceCommStatus.UNKNOWN:
            return sdk.DeviceCommState.NA
        if api_val == API.DeviceCommStatus.DISCONNECTED:
            return sdk.DeviceCommState.Disconnected
        if api_val == API.DeviceCommStatus.CONNECTING:
            return sdk.DeviceCommState.Connecting
        if api_val == API.DeviceCommStatus.CONNECTED:
            return sdk.DeviceCommState.Connecting   # This is not a mistake Connected->Connecting, for sdk simplicity
        if api_val == API.DeviceCommStatus.CONNECTED_READY:
            return sdk.DeviceCommState.ConnectedReady
        raise sdk.exceptions.BadResponseError('Unsupported device communication status "{api_val}"')

    _check_response_dict(cmd, response, 'device_info', (dict, NoneType))
    device_info: Optional[sdk.DeviceInfo] = None
    if isinstance(response['device_info'], dict):
        _check_response_dict(cmd, response, 'device_info.device_id', str)
        _check_response_dict(cmd, response, 'device_info.display_name', str)
        _check_response_dict(cmd, response, 'device_info.max_tx_data_size', int)
        _check_response_dict(cmd, response, 'device_info.max_rx_data_size', int)
        _check_response_dict(cmd, response, 'device_info.max_bitrate_bps', int)
        _check_response_dict(cmd, response, 'device_info.rx_timeout_us', int)
        _check_response_dict(cmd, response, 'device_info.heartbeat_timeout_us', int)
        _check_response_dict(cmd, response, 'device_info.address_size_bits', int)
        _check_response_dict(cmd, response, 'device_info.protocol_major', int)
        _check_response_dict(cmd, response, 'device_info.protocol_minor', int)
        _check_response_dict(cmd, response, 'device_info.supported_feature_map.memory_write', bool)
        _check_response_dict(cmd, response, 'device_info.supported_feature_map.datalogging', bool)
        _check_response_dict(cmd, response, 'device_info.supported_feature_map.user_command', bool)
        _check_response_dict(cmd, response, 'device_info.supported_feature_map._64bits', bool)
        _check_response_dict(cmd, response, 'device_info.forbidden_memory_regions', list)
        _check_response_dict(cmd, response, 'device_info.readonly_memory_regions', list)

        forbidden_regions: List[sdk.MemoryRegion] = []
        for region in response['device_info']['forbidden_memory_regions']:
            _check_response_dict(cmd, region, 'start', int)
            _check_response_dict(cmd, region, 'end', int)
            if region['end'] <= region['start']:
                raise sdk.exceptions.BadResponseError(f'Received a forbidden memory region with incoherent start and end in message "{cmd}"')
            size = region['end'] - region['start'] + 1
            if size <= 0:
                raise sdk.exceptions.BadResponseError(f'Got a forbidden memory region with an invalid size "{cmd}"')
            forbidden_regions.append(sdk.MemoryRegion(
                start=region['start'],
                size=size
            ))

        readonly_regions: List[sdk.MemoryRegion] = []
        for region in response['device_info']['readonly_memory_regions']:
            _check_response_dict(cmd, region, 'start', int)
            _check_response_dict(cmd, region, 'end', int)
            if region['end'] <= region['start']:
                raise sdk.exceptions.BadResponseError(f'Received a readonly memory region with incoherent start and end in message "{cmd}"')
            size = region['end'] - region['start'] + 1
            if size <= 0:
                raise sdk.exceptions.BadResponseError(f'Got a readonly memory region with an invalid size "{cmd}"')
            readonly_regions.append(sdk.MemoryRegion(
                start=region['start'],
                size=size
            ))

        if response['device_info']['address_size_bits'] not in get_args(sdk.AddressSize):
            raise sdk.exceptions.BadResponseError(f"Unexpected address size {response['device_info']['address_size_bits']}")

        device_info = sdk.DeviceInfo(
            device_id=response['device_info']['device_id'],
            display_name=response['device_info']['display_name'],
            max_tx_data_size=response['device_info']['max_tx_data_size'],
            max_rx_data_size=response['device_info']['max_rx_data_size'],
            max_bitrate_bps=response['device_info']['max_bitrate_bps'],
            rx_timeout_us=response['device_info']['rx_timeout_us'],
            heartbeat_timeout=float(response['device_info']['heartbeat_timeout_us']) * 1e-6,
            address_size_bits=cast(sdk.AddressSize, response['device_info']['address_size_bits']),
            protocol_major=response['device_info']['protocol_major'],
            protocol_minor=response['device_info']['protocol_minor'],
            supported_features=sdk.SupportedFeatureMap(
                memory_write=response['device_info']['supported_feature_map']['memory_write'],
                datalogging=response['device_info']['supported_feature_map']['datalogging'],
                user_command=response['device_info']['supported_feature_map']['user_command'],
                sixtyfour_bits=response['device_info']['supported_feature_map']['_64bits'],
            ),
            forbidden_memory_regions=forbidden_regions,
            readonly_memory_regions=readonly_regions
        )

    sfd: Optional[sdk.SFDInfo] = None
    if response['loaded_sfd'] is not None:
        _check_response_dict(cmd, response, 'loaded_sfd.firmware_id', str)
        timestamp = _fetch_dict_val(response, 'loaded_sfd.metadata.generation_info.time', int, None)
        metadata = sdk.SFDMetadata(
            author=_fetch_dict_val(response, 'loaded_sfd.metadata.author', str, None),
            project_name=_fetch_dict_val(response, 'loaded_sfd.metadata.project_name', str, None),
            version=_fetch_dict_val(response, 'loaded_sfd.metadata.version', str, None),
            generation_info=sdk.SFDGenerationInfo(
                python_version=_fetch_dict_val(response, 'loaded_sfd.metadata.generation_info.python_version', str, None),
                scrutiny_version=_fetch_dict_val(response, 'loaded_sfd.metadata.generation_info.scrutiny_version', str, None),
                system_type=_fetch_dict_val(response, 'loaded_sfd.metadata.generation_info.system_type', str, None),
                timestamp=datetime.fromtimestamp(timestamp) if timestamp is not None else None
            )
        )

        sfd = sdk.SFDInfo(
            firmware_id=response['loaded_sfd']['firmware_id'],
            metadata=metadata
        )

    _check_response_dict(cmd, response, 'device_datalogging_status.datalogger_state', str)
    _check_response_dict(cmd, response, 'device_datalogging_status.completion_ratio', [NoneType, float])

    def _datalogging_status(api_val: api_typing.DataloggerState) -> sdk.DataloggerState:
        if api_val == API.DataloggingStatus.UNAVAILABLE:
            return sdk.DataloggerState.NA
        elif api_val == API.DataloggingStatus.STANDBY:
            return sdk.DataloggerState.Standby
        elif api_val == API.DataloggingStatus.WAITING_FOR_TRIGGER:
            return sdk.DataloggerState.WaitForTrigger
        elif api_val == API.DataloggingStatus.ACQUIRING:
            return sdk.DataloggerState.Acquiring
        elif api_val == API.DataloggingStatus.DATA_READY:
            return sdk.DataloggerState.DataReady
        elif api_val == API.DataloggingStatus.ERROR:
            return sdk.DataloggerState.Error
        raise sdk.exceptions.BadResponseError('Unsupported datalogger state "{api_val}"')

    datalogging = sdk.DataloggingInfo(
        completion_ratio=response['device_datalogging_status']['completion_ratio'],
        state=_datalogging_status(response['device_datalogging_status']['datalogger_state'])
    )

    def _link_type(api_val: api_typing.LinkType) -> sdk.DeviceLinkType:
        if api_val == 'none':
            return sdk.DeviceLinkType.NA
        if api_val == 'serial':
            return sdk.DeviceLinkType.Serial
        if api_val == 'dummy' or api_val == 'thread_safe_dummy':
            return sdk.DeviceLinkType.Dummy
        if api_val == 'udp':
            return sdk.DeviceLinkType.UDP
        raise sdk.exceptions.BadResponseError('Unsupported device link type "{api_val}"')

    link_type = _link_type(response['device_comm_link']['link_type'])

    link_config: Optional[sdk.SupportedLinkConfig]
    if link_type == sdk.DeviceLinkType.NA:
        link_config = None
    elif link_type == sdk.DeviceLinkType.UDP:
        udp_config = cast(api_typing.UdpLinkConfig, response['device_comm_link']['link_config'])
        _check_response_dict(cmd, response, 'device_comm_link.link_config.host', str)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.port', int)
        link_config = sdk.UDPLinkConfig(
            host=udp_config['host'],
            port=udp_config['port'],
        )
    elif link_type == sdk.DeviceLinkType.Serial:
        serial_config = cast(api_typing.SerialLinkConfig, response['device_comm_link']['link_config'])
        _check_response_dict(cmd, response, 'device_comm_link.link_config.portname', str)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.baudrate', int)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.stopbits', str)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.databits', int)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.parity', str)

        api_stopbits = serial_config['stopbits']
        if api_stopbits not in ('1', '1.5', '2'):
            raise sdk.exceptions.BadResponseError(f'Unsupported stop bit value "{api_stopbits}" in message {cmd}')

        api_parity = serial_config['parity']
        if api_parity not in ('none', 'even', 'odd', 'mark', 'space'):
            raise sdk.exceptions.BadResponseError(f'Unsupported parity value "{api_parity}" in message {cmd}')

        api_databits = serial_config['databits']
        if api_databits not in (5, 6, 7, 8):
            raise sdk.exceptions.BadResponseError(f'Unsupported number of databits value "{api_databits}" in message {cmd}')

        link_config = sdk.SerialLinkConfig(
            port=serial_config['portname'],
            baudrate=serial_config['baudrate'],
            stopbits=cast(sdk.SerialStopBits, api_stopbits),
            parity=cast(sdk.SerialParity, api_parity),
            databits=cast(sdk.SerialDataBits, api_databits)
        )
    else:
        raise RuntimeError('Unsupported device link type "{link_type}"')

    _check_response_dict(cmd, response, 'device_comm_link.link_type', str)
    device_link = sdk.DeviceLinkInfo(
        type=link_type,
        config=link_config
    )

    return sdk.ServerInfo(
        device_comm_state=_device_status_from_api(response['device_status']),
        device_session_id=response['device_session_id'],
        datalogging=datalogging,
        device=device_info,
        sfd=sfd,
        device_link=device_link
    )


def parse_watchable_update(response: api_typing.S2C.WatchableUpdate) -> List[WatchableUpdate]:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.WATCHABLE_UPDATE

    outlist: List[WatchableUpdate] = []

    _check_response_dict(cmd, response, 'updates', list)

    for element in response['updates']:
        _check_response_dict(cmd, element, 'id', str)
        _check_response_dict(cmd, element, 'value', [float, int, bool])
        outlist.append(WatchableUpdate(
            server_id=element['id'],
            value=element['value'],
        ))

    return outlist


def parse_write_value_response(response: api_typing.S2C.WriteValue) -> WriteConfirmation:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.WRITE_WATCHABLE_RESPONSE

    _check_response_dict(cmd, response, 'request_token', str)
    _check_response_dict(cmd, response, 'count', int)

    return WriteConfirmation(
        request_token=response['request_token'],
        count=response['count']
    )


def parse_write_completion(response: api_typing.S2C.WriteCompletion) -> WriteCompletion:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.INFORM_WRITE_COMPLETION

    _check_response_dict(cmd, response, 'watchable', str)
    _check_response_dict(cmd, response, 'success', bool)
    _check_response_dict(cmd, response, 'request_token', str)
    _check_response_dict(cmd, response, 'timestamp', float)
    _check_response_dict(cmd, response, 'batch_index', int)

    return WriteCompletion(
        request_token=response['request_token'],
        watchable=response['watchable'],
        success=response['success'],
        timestamp=datetime.fromtimestamp(response['timestamp']),
        batch_index=response['batch_index']
    )


def parse_get_installed_sfds_response(response: api_typing.S2C.GetInstalledSFD) -> Dict[str, sdk.SFDInfo]:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.GET_INSTALLED_SFD_RESPONSE

    output: Dict[str, sdk.SFDInfo] = {}
    _check_response_dict(cmd, response, 'sfd_list', dict)

    for firmware_id, sfd_content in response['sfd_list'].items():
        timestamp = _fetch_dict_val(sfd_content, 'generation_info.time', int, None)
        metadata = sdk.SFDMetadata(
            author=_fetch_dict_val(sfd_content, 'author', str, None),
            project_name=_fetch_dict_val(sfd_content, 'project_name', str, None),
            version=_fetch_dict_val(sfd_content, 'version', str, None),
            generation_info=sdk.SFDGenerationInfo(
                python_version=_fetch_dict_val(sfd_content, 'generation_info.python_version', str, None),
                scrutiny_version=_fetch_dict_val(sfd_content, 'generation_info.scrutiny_version', str, None),
                system_type=_fetch_dict_val(sfd_content, 'generation_info.system_type', str, None),
                timestamp=datetime.fromtimestamp(timestamp) if timestamp is not None else None
            )
        )

        output[firmware_id] = sdk.SFDInfo(
            firmware_id=firmware_id,
            metadata=metadata
        )

    return output


def parse_memory_read_completion(response: api_typing.S2C.ReadMemoryComplete) -> MemoryReadCompletion:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.INFORM_MEMORY_READ_COMPLETE

    _check_response_dict(cmd, response, 'request_token', str)
    _check_response_dict(cmd, response, 'success', bool)
    _check_response_dict(cmd, response, 'data', str)

    data = _fetch_dict_val_no_none(response, 'data', str, "")
    try:
        data_bin = b64decode(data, validate=True)
    except binascii.Error as e:
        raise sdk.exceptions.BadResponseError(f"Server returned a invalid base64 data block. {e}")

    detail_msg = _fetch_dict_val(response, 'detail_msg', str, "")

    return MemoryReadCompletion(
        request_token=_fetch_dict_val_no_none(response, 'request_token', str, ""),
        success=_fetch_dict_val_no_none(response, 'success', bool, False),
        data=data_bin,
        error=detail_msg if detail_msg is not None else "",
        timestamp=time.time()
    )
