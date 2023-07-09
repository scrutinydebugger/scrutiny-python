
import scrutiny.sdk.definitions as sdk_definitions
import scrutiny.sdk.exceptions as sdk_exceptions
from typing import *
from scrutiny.core.basic_types import *
from scrutiny.server.api.API import API
from scrutiny.server.api import typing as api_typing
from dataclasses import dataclass
from datetime import datetime


@dataclass
class WatchableConfiguration:
    watchable_type: sdk_definitions.WatchableType
    datatype: EmbeddedDataType
    server_id: str


@dataclass
class WatchableUpdate:
    server_id: str
    value: Union[bool, int, float]


T = TypeVar('T', str, int, float)


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
        raise sdk_exceptions.BadResponseError(f'Missing field {part_name} in message "{cmd}"')

    if len(next_parts) > 0:
        if not isinstance(d, dict):
            raise sdk_exceptions.BadResponseError(f'Field {part_name} is expected to be a dictionary in message "{cmd}"')

        _check_response_dict(cmd, d[key], '.'.join(next_parts), types, part_name)
    else:

        if not isinstance(d[key], types):
            gotten_type = d[key].__class__.__name__
            typename = "(%s)" % ', '.join([t.__name__ for t in types])
            raise sdk_exceptions.BadResponseError(
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
            raise sdk_exceptions.BadResponseError(f'Field {key} cannot be None')
        return wanted_type(d[key])
    else:
        return _fetch_dict_val(d[key], '.'.join(next_parts), wanted_type=wanted_type, default=default)


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
        raise sdk_exceptions.NameNotFoundError(f'No watchable element matches the path {requested_path} on the server')

    if total > 1:
        raise sdk_exceptions.BadResponseError(f"More than one item were returned by the server that matched the path {requested_path}")

    if response['done'] != True:
        raise sdk_exceptions.BadResponseError(f"done field should be True")

    _check_response_dict(cmd, response, 'content.alias', list)
    _check_response_dict(cmd, response, 'content.rpv', list)
    _check_response_dict(cmd, response, 'content.var', list)

    watchable_type: sdk_definitions.WatchableType = sdk_definitions.WatchableType.NA
    content: Any = None
    WatchableTypeKey = Literal['rpv', 'alias', 'var']

    typekey: WatchableTypeKey
    if response['qty']['alias'] == 1:
        watchable_type = sdk_definitions.WatchableType.Alias
        typekey = 'alias'
    elif response['qty']['rpv']:
        watchable_type = sdk_definitions.WatchableType.RuntimePulishedValue
        content = response['content']['rpv']
        typekey = 'rpv'
    elif response['qty']['var']:
        watchable_type = sdk_definitions.WatchableType.Variable
        typekey = 'var'
    else:
        raise sdk_exceptions.BadResponseError('Unknown watchable type')

    key: WatchableTypeKey
    for key in get_args(WatchableTypeKey):
        expected_count = 1 if key == typekey else 0
        if len(response['content'][key]) != expected_count:
            raise sdk_exceptions.BadResponseError("Incoherent element quantity in API response.")

    content = cast(dict, response['content'][typekey][0])
    keyprefix = f'content.{typekey}[0]'
    _check_response_dict(cmd, content, 'id', str, keyprefix)
    _check_response_dict(cmd, content, 'display_path', str, keyprefix)
    _check_response_dict(cmd, content, 'datatype', str, keyprefix)

    if content['datatype'] not in API.APISTR_2_DATATYPE:
        raise sdk_exceptions.BadResponseError(f"Unknown datatype {content['datatype']}")

    datatype = EmbeddedDataType(API.APISTR_2_DATATYPE[content['datatype']])

    if requested_path != content['display_path']:
        raise sdk_exceptions.BadResponseError(
            f"The display path of the element returned by the server does not matched the requested path. Got {content['display_path']} but expected {requested_path}")

    if not isinstance(content['id'], str):
        raise sdk_exceptions.BadResponseError(f"Invalid server id received for watchable {requested_path}")

    return WatchableConfiguration(
        watchable_type=watchable_type,
        datatype=datatype,
        server_id=content['id']
    )


def parse_inform_server_status(response: api_typing.S2C.InformServerStatus) -> sdk_definitions.ServerInfo:
    """Parse the inform_server_status message"""

    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.INFORM_SERVER_STATUS
    NoneType: Type = type(None)

    _check_response_dict(cmd, response, 'device_status', str)
    _check_response_dict(cmd, response, 'device_session_id', (str, NoneType))

    def _device_status_from_api(api_val: api_typing.DeviceCommStatus) -> sdk_definitions.DeviceCommState:
        if api_val == API.DeviceCommStatus.UNKNOWN:
            return sdk_definitions.DeviceCommState.NA
        if api_val == API.DeviceCommStatus.DISCONNECTED:
            return sdk_definitions.DeviceCommState.Disconnected
        if api_val == API.DeviceCommStatus.CONNECTING:
            return sdk_definitions.DeviceCommState.Connecting
        if api_val == API.DeviceCommStatus.CONNECTED:
            return sdk_definitions.DeviceCommState.Connecting   # This is not a mistake Connected->Connecting, for sdk simplicity
        if api_val == API.DeviceCommStatus.CONNECTED_READY:
            return sdk_definitions.DeviceCommState.ConnectedReady
        raise sdk_exceptions.BadResponseError('Unsupported device communication status "{api_val}"')

    _check_response_dict(cmd, response, 'device_info', (dict, NoneType))
    device_info: Optional[sdk_definitions.DeviceInfo] = None
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

        forbidden_regions: List[sdk_definitions.MemoryRegion] = []
        for region in response['device_info']['forbidden_memory_regions']:
            _check_response_dict(cmd, region, 'start', int)
            _check_response_dict(cmd, region, 'end', int)
            if region['end'] <= region['start']:
                raise sdk_exceptions.BadResponseError(f'Received a forbidden memory region with incoherent start and end in message "{cmd}"')
            size = region['end'] - region['start'] + 1
            if size <= 0:
                raise sdk_exceptions.BadResponseError(f'Got a forbidden memory region with an invalid size "{cmd}"')
            forbidden_regions.append(sdk_definitions.MemoryRegion(
                start=region['start'],
                size=size
            ))

        readonly_regions: List[sdk_definitions.MemoryRegion] = []
        for region in response['device_info']['readonly_memory_regions']:
            _check_response_dict(cmd, region, 'start', int)
            _check_response_dict(cmd, region, 'end', int)
            if region['end'] <= region['start']:
                raise sdk_exceptions.BadResponseError(f'Received a readonly memory region with incoherent start and end in message "{cmd}"')
            size = region['end'] - region['start'] + 1
            if size <= 0:
                raise sdk_exceptions.BadResponseError(f'Got a readonly memory region with an invalid size "{cmd}"')
            readonly_regions.append(sdk_definitions.MemoryRegion(
                start=region['start'],
                size=size
            ))

        if response['device_info']['address_size_bits'] not in get_args(sdk_definitions.AddressSize):
            raise sdk_exceptions.BadResponseError(f"Unexpected address size {response['device_info']['address_size_bits']}")

        device_info = sdk_definitions.DeviceInfo(
            device_id=response['device_info']['device_id'],
            display_name=response['device_info']['display_name'],
            max_tx_data_size=response['device_info']['max_tx_data_size'],
            max_rx_data_size=response['device_info']['max_rx_data_size'],
            max_bitrate_bps=response['device_info']['max_bitrate_bps'],
            rx_timeout_us=response['device_info']['rx_timeout_us'],
            heartbeat_timeout=float(response['device_info']['heartbeat_timeout_us']) * 1e-6,
            address_size_bits=cast(sdk_definitions.AddressSize, response['device_info']['address_size_bits']),
            protocol_major=response['device_info']['protocol_major'],
            protocol_minor=response['device_info']['protocol_minor'],
            supported_features=sdk_definitions.SupportedFeatureMap(
                memory_write=response['device_info']['supported_feature_map']['memory_write'],
                datalogging=response['device_info']['supported_feature_map']['datalogging'],
                user_command=response['device_info']['supported_feature_map']['user_command'],
                sixtyfour_bits=response['device_info']['supported_feature_map']['_64bits'],
            ),
            forbidden_memory_regions=forbidden_regions,
            readonly_memory_regions=readonly_regions
        )

    sfd: Optional[sdk_definitions.SFDInfo] = None
    if response['loaded_sfd'] is not None:
        _check_response_dict(cmd, response, 'loaded_sfd.firmware_id', str)
        timestamp = _fetch_dict_val(response, 'loaded_sfd.metadata.generation_info.time', int, None)
        metadata = sdk_definitions.SFDMetadata(
            author=_fetch_dict_val(response, 'loaded_sfd.metadata.author', str, None),
            project_name=_fetch_dict_val(response, 'loaded_sfd.metadata.project_name', str, None),
            version=_fetch_dict_val(response, 'loaded_sfd.metadata.version', str, None),
            generation_info=sdk_definitions.SFDGenerationInfo(
                python_version=_fetch_dict_val(response, 'loaded_sfd.metadata.generation_info.python_version', str, None),
                scrutiny_version=_fetch_dict_val(response, 'loaded_sfd.metadata.generation_info.scrutiny_version', str, None),
                system_type=_fetch_dict_val(response, 'loaded_sfd.metadata.generation_info.system_type', str, None),
                timestamp=datetime.fromtimestamp(timestamp) if timestamp is not None else None
            )
        )

        sfd = sdk_definitions.SFDInfo(
            firmware_id=response['loaded_sfd']['firmware_id'],
            metadata=metadata
        )

    _check_response_dict(cmd, response, 'device_datalogging_status.datalogger_state', str)
    _check_response_dict(cmd, response, 'device_datalogging_status.completion_ratio', [NoneType, float])

    def _datalogging_status(api_val: api_typing.DataloggerState) -> sdk_definitions.DataloggerState:
        if api_val == API.DataloggingStatus.UNAVAILABLE:
            return sdk_definitions.DataloggerState.NA
        elif api_val == API.DataloggingStatus.STANDBY:
            return sdk_definitions.DataloggerState.Standby
        elif api_val == API.DataloggingStatus.WAITING_FOR_TRIGGER:
            return sdk_definitions.DataloggerState.WaitForTrigger
        elif api_val == API.DataloggingStatus.ACQUIRING:
            return sdk_definitions.DataloggerState.Acquiring
        elif api_val == API.DataloggingStatus.DATA_READY:
            return sdk_definitions.DataloggerState.DataReady
        elif api_val == API.DataloggingStatus.ERROR:
            return sdk_definitions.DataloggerState.Error
        raise sdk_exceptions.BadResponseError('Unsupported datalogger state "{api_val}"')

    datalogging = sdk_definitions.DataloggingInfo(
        completion_ratio=response['device_datalogging_status']['completion_ratio'],
        state=_datalogging_status(response['device_datalogging_status']['datalogger_state'])
    )

    def _link_type(api_val: api_typing.LinkType) -> sdk_definitions.DeviceLinkType:
        if api_val == 'none':
            return sdk_definitions.DeviceLinkType.NA
        if api_val == 'serial':
            return sdk_definitions.DeviceLinkType.Serial
        if api_val == 'dummy' or api_val == 'thread_safe_dummy':
            return sdk_definitions.DeviceLinkType.Dummy
        if api_val == 'udp':
            return sdk_definitions.DeviceLinkType.UDP
        raise sdk_exceptions.BadResponseError('Unsupported device link type "{api_val}"')

    link_type = _link_type(response['device_comm_link']['link_type'])

    link_config: Optional[sdk_definitions.SupportedLinkConfig]
    if link_type == sdk_definitions.DeviceLinkType.NA:
        link_config = None
    elif link_type == sdk_definitions.DeviceLinkType.UDP:
        udp_config = cast(api_typing.UdpLinkConfig, response['device_comm_link']['link_config'])
        _check_response_dict(cmd, response, 'device_comm_link.link_config.host', str)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.port', int)
        link_config = sdk_definitions.UDPLinkConfig(
            host=udp_config['host'],
            port=udp_config['port'],
        )
    elif link_type == sdk_definitions.DeviceLinkType.Serial:
        serial_config = cast(api_typing.SerialLinkConfig, response['device_comm_link']['link_config'])
        _check_response_dict(cmd, response, 'device_comm_link.link_config.portname', str)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.baudrate', int)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.stopbits', str)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.databits', int)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.parity', str)

        api_stopbits = serial_config['stopbits']
        if api_stopbits not in ('1', '1.5', '2'):
            raise sdk_exceptions.BadResponseError(f'Unsupported stop bit value "{api_stopbits}" in message {cmd}')

        api_parity = serial_config['parity']
        if api_parity not in ('none', 'even', 'odd', 'mark', 'space'):
            raise sdk_exceptions.BadResponseError(f'Unsupported parity value "{api_parity}" in message {cmd}')

        api_databits = serial_config['databits']
        if api_databits not in (5, 6, 7, 8):
            raise sdk_exceptions.BadResponseError(f'Unsupported number of databits value "{api_databits}" in message {cmd}')

        link_config = sdk_definitions.SerialLinkConfig(
            port=serial_config['portname'],
            baudrate=serial_config['baudrate'],
            stopbits=cast(sdk_definitions.SerialStopBits, api_stopbits),
            parity=cast(sdk_definitions.SerialParity, api_parity),
            databits=cast(sdk_definitions.SerialDataBits, api_databits)
        )
    else:
        raise RuntimeError('Unsupported device link type "{link_type}"')

    _check_response_dict(cmd, response, 'device_comm_link.link_type', str)
    device_link = sdk_definitions.DeviceLinkInfo(
        type=link_type,
        config=link_config
    )

    return sdk_definitions.ServerInfo(
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
