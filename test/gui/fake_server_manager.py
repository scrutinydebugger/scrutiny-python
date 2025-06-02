#    fake_server_manager.py
#        A stubbed Server MAnager for unit test purpose
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2021 Scrutiny Debugger

import logging
from PySide6.QtCore import Signal, QObject
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.gui.core.server_manager import ServerConfig
from scrutiny import sdk

from scrutiny.tools.typing import *

enum_rpv_a_c = sdk.EmbeddedEnum("EnumAC", {'aaa' : 0, 'bbb': 1, 'ccc': 2})

DUMMY_DATASET_RPV = {
    '/rpv/rpv.a/rpv.a.a' : sdk.WatchableConfiguration(server_id='rpv.a.a', watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/rpv/rpv.a/rpv.a.b' : sdk.WatchableConfiguration(server_id='rpv.a.b', watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/rpv/rpv.a/rpv.a.c' : sdk.WatchableConfiguration(server_id='rpv.a.c', watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.uint32, enum=enum_rpv_a_c),
    '/rpv/rpv.b/rpv.b.a' : sdk.WatchableConfiguration(server_id='rpv.b.a', watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/rpv/rpv.b/rpv.b.b' : sdk.WatchableConfiguration(server_id='rpv.b.b', watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/rpv/rpv.b/rpv.b.c' : sdk.WatchableConfiguration(server_id='rpv.b.c', watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None),
}

DUMMY_DATASET_ALIAS = {
    '/alias/alias.a/alias.a.a' : sdk.WatchableConfiguration(server_id='alias.a.a', watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/alias/alias.a/alias.a.b' : sdk.WatchableConfiguration(server_id='alias.a.b', watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/alias/alias.a/alias.a.c' : sdk.WatchableConfiguration(server_id='alias.a.c', watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/alias/alias.b/alias.b.a' : sdk.WatchableConfiguration(server_id='alias.b.a', watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/alias/alias.b/alias.b.b' : sdk.WatchableConfiguration(server_id='alias.b.b', watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/alias/alias.b/alias.b.c' : sdk.WatchableConfiguration(server_id='alias.b.c', watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
}

DUMMY_DATASET_VAR = {
    '/var/var.a/var.a.a' : sdk.WatchableConfiguration(server_id='var.a.a', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/var.a/var.a.b' : sdk.WatchableConfiguration(server_id='var.a.b', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/var.a/var.a.c' : sdk.WatchableConfiguration(server_id='var.a.c', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/var.b/var.b.a' : sdk.WatchableConfiguration(server_id='var.b.a', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/var.b/var.b.b' : sdk.WatchableConfiguration(server_id='var.b.b', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/var.b/var.b.c' : sdk.WatchableConfiguration(server_id='var.b.c', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
}


class FakeServerManager:
    class _Signals(QObject):    # QObject required for signals to work
        """Signals offered to the outside world"""
        started = Signal()
        starting = Signal()
        stopping = Signal()
        stopped = Signal()
        server_connected = Signal()
        server_disconnected = Signal()
        device_ready = Signal()
        device_disconnected = Signal()
        datalogging_state_changed = Signal()
        sfd_loaded = Signal()
        sfd_unloaded = Signal()
        registry_changed = Signal()
        status_received = Signal()

    _started: bool
    _server_connected: bool
    _device_connected: bool
    _sfd_loaded: bool

    def __init__(self, watchable_registry:WatchableRegistry):
        self._signals = self._Signals()
        self._registry = watchable_registry

        self._started = False
        self._server_connected = False
        self._device_connected = False
        self._sfd_loaded = False
        self._logger = logging.getLogger(self.__class__.__name__)

    @property
    def signals(self) -> _Signals:
        """The events exposed to the application"""
        return self._signals

    @property
    def registry(self) -> WatchableRegistry:
        """The watchable registry containing a definition of all the watchables available on the server"""
        return self._registry


    def start(self, config:ServerConfig) -> None:
        self._signals.starting.emit()        
        self._started = True
        self._signals.started.emit()
        self._signals.server_connected.emit()

        if self.registry.clear():
            self._signals.registry_changed.emit()


    def stop(self) -> None:
        self._signals.stopping.emit()
        self._started = False
        self._signals.stopped.emit()

        if self.registry.clear():
            self._signals.registry_changed.emit()

    def simulate_server_connect(self):
        if not self._started:
            return 
        need_signal = not self._server_connected
        self._server_connected = True
        if need_signal:
            self._signals.server_connected.emit()
        
        if self.registry.clear():
            self._signals.registry_changed.emit()

        if self._device_connected:
            self.simulate_device_ready()
        if self._sfd_loaded:
            self.simulate_sfd_loaded()

    def simulate_server_disconnected(self):
        if not self._started:
            return 
        need_signal = self._server_connected
        self._server_connected = False
        if need_signal:
            self._signals.server_disconnected.emit()
        
        if self.registry.clear():
            self._signals.registry_changed.emit()
    
    def is_running(self) -> bool:
        return self._started
    
    def simulate_device_ready(self) -> None:
        if not self._server_connected:
            return
        self._device_connected = True
        self._signals.device_ready.emit()
        self.registry.clear_content_by_type(sdk.WatchableType.RuntimePublishedValue)
        self.registry.write_content({
            sdk.WatchableType.RuntimePublishedValue : DUMMY_DATASET_RPV
        })
        self._signals.registry_changed.emit()

    def simulate_device_disconnect(self) -> None:
        if not self._server_connected:
            return
        self._device_connected = False
        self._signals.device_disconnected.emit()
        self.registry.clear_content_by_type(sdk.WatchableType.RuntimePublishedValue)
        self._signals.registry_changed.emit()

    def simulate_sfd_loaded(self) -> None:
        if not self._server_connected:
            return
        self._sfd_loaded = True
        self._signals.sfd_loaded.emit()
        self.registry.clear_content_by_type(sdk.WatchableType.Alias)
        self.registry.clear_content_by_type(sdk.WatchableType.Variable)
        self.registry.write_content({
            sdk.WatchableType.Variable : DUMMY_DATASET_VAR,
            sdk.WatchableType.Alias : DUMMY_DATASET_ALIAS,
        })
        self._signals.registry_changed.emit()

    def simulate_sfd_unloaded(self) -> None:
        if not self._server_connected:
            return
        self._sfd_loaded = False
        self._signals.sfd_unloaded.emit()
        self.registry.clear_content_by_type(sdk.WatchableType.Alias)
        self.registry.clear_content_by_type(sdk.WatchableType.Variable)
        self._signals.registry_changed.emit()
        
    def get_server_info(self) -> Optional[sdk.ServerInfo]:
        if not self._started:
            return None
        
        if not self._server_connected:
            return None
        
        datalogging = None
        device_comm_state = sdk.DeviceCommState.Disconnected
        device_session_id = None
        if self._device_connected:
            datalogging = sdk.DataloggingInfo(completion_ratio=0, state=sdk.DataloggerState.Standby)
            device_comm_state = sdk.DeviceCommState.ConnectedReady
            device_session_id='aaa'

        sfd_firmware_id = None
        if self._sfd_loaded:
            sfd_firmware_id = 'bbb'

        info = sdk.ServerInfo(
            device_link=sdk.DeviceLinkInfo(
                type=sdk.DeviceLinkType.NONE,
                config=sdk.NoneLinkConfig(),
                operational=True
            ),
            datalogging=datalogging,
            device_comm_state=device_comm_state,
            device_session_id=device_session_id,
            sfd_firmware_id=sfd_firmware_id
        )

        return info

    def qt_write_watchable_value(self, fqn:str, value:Union[str, int, float, bool], callback:Callable[[Optional[Exception]], None]) -> None:
        pass
        
