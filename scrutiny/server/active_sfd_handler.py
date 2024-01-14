#    active_sfd_handler.py
#        Manage the loaded SFD file with which the client will interact.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import logging
import traceback

from scrutiny.core.firmware_description import FirmwareDescription
from scrutiny.core.sfd_storage import SFDStorage
from scrutiny.server.datastore.datastore_entry import EntryType
from scrutiny.server.device.device_handler import DeviceHandler
from scrutiny.server.datastore.datastore import Datastore
from scrutiny.server.datastore.datastore_entry import *
from scrutiny.server.datastore.entry_type import EntryType

from typing import Optional, List, Callable
from scrutiny.core.typehints import GenericCallback


class SFDLoadedCallback(GenericCallback):
    callback: Callable[[FirmwareDescription], None]


class SFDUnloadedCallback(GenericCallback):
    callback: Callable[[None], None]


class ActiveSFDHandler:
    """
    Handle which Scrutiny Firmware Description file (SFD) is loaded. Automatically load one
    when the DeviceHandler connects to a device and the device broadcast a firmware ID associated with 
    an installed SFD.

    When loaded, the SFD contents becomes available to the clients through the API, meaning variables and aliases.
    """
    logger: logging.Logger
    device_handler: DeviceHandler   # Reference to the device handler. We use it to know if a connection to a device is done
    datastore: Datastore            # Datastore that will be populated with the SFD content upon load
    autoload: bool                  # When True, automatically loads an SFD upon device connection

    sfd: Optional[FirmwareDescription]  # The actually loaded SFD
    previous_device_status: DeviceHandler.ConnectionStatus  # Device Handler status of previous loop
    requested_firmware_id: Optional[str]   # When this value is set, we received a request from the external world (the API) to manually load an SFD

    loaded_callbacks: List[SFDLoadedCallback]       # List of callbacks to call upon SFD loading
    unloaded_callbacks: List[SFDUnloadedCallback]   # List of callbacks to load upon SFD unloading

    def __init__(self, device_handler: DeviceHandler, datastore: Datastore, autoload:bool=True) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.device_handler = device_handler
        self.datastore = datastore
        self.autoload = autoload

        self.sfd = None
        self.previous_device_status = DeviceHandler.ConnectionStatus.UNKNOWN
        self.requested_firmware_id = None

        self.loaded_callbacks = []
        self.unloaded_callbacks = []

        self.reset_active_sfd()

    def register_sfd_loaded_callback(self, callback: SFDLoadedCallback) -> None:
        """Adds callback to be called upon Firmware Description load"""
        self.loaded_callbacks.append(callback)

    def register_sfd_unloaded_callback(self, callback: SFDUnloadedCallback) -> None:
        """Adds a callback to be called when a Firmware Descriptiopn is unloaded"""
        self.unloaded_callbacks.append(callback)

    def init(self) -> None:
        """Initialize the SFD handler. To be called at startup"""
        self.reset_active_sfd()

    def close(self) -> None:
        """Shutdown the SFD Handler"""
        pass

    def set_autoload(self, val: bool) -> None:
        """Set autoload. When True, the SFD Handler will automatically load an SFD upon connection with
        a device with a known firmware"""
        self.autoload = val

    def process(self) -> None:
        """To be called periodically"""
        device_status = self.device_handler.get_connection_status()

        if self.autoload:
            if device_status != DeviceHandler.ConnectionStatus.CONNECTED_READY:
                self.reset_active_sfd()     # Clear active SFD
            else:
                if self.sfd is None:    # if none loaded
                    verbose = self.previous_device_status != device_status
                    device_id = self.device_handler.get_device_id()
                    if device_id is not None:
                        self._load_sfd(device_id, verbose=verbose)   # Initiale loading. Will populate the datastore
                    else:
                        self.logger.critical('No device ID available when connected. This should not happen')

        if self.requested_firmware_id is not None:  # If the API requested to load an SFD
            self._load_sfd(self.requested_firmware_id)
            self.requested_firmware_id = None

        self.previous_device_status = device_status

    def request_load_sfd(self, firmware_id: str) -> None:
        """Request the SFD Handler to manually load an SFD. Autoload should be disabled to use this feature"""
        if not SFDStorage.is_installed(firmware_id):
            raise Exception('Firmware ID %s is not installed' % firmware_id)

        self.logger.debug("Requested to load SFD for firmware %s" % firmware_id)
        self.requested_firmware_id = firmware_id

    def _load_sfd(self, firmware_id: str, verbose:bool=True) -> None:
        """Loads a Scrutiny Firmware Description"""
        self.sfd = None
        # We only clear the entry types coming from the SFD.
        self.datastore.clear(EntryType.Var)
        self.datastore.clear(EntryType.Alias)

        if SFDStorage.is_installed(firmware_id):
            self.logger.info('Loading firmware description file (SFD) for firmware ID %s' % firmware_id)
            self.sfd = SFDStorage.get(firmware_id)

            # populate datastore
            for fullname, vardef in self.sfd.get_vars_for_datastore():
                try:
                    entry_var = DatastoreVariableEntry(display_path=fullname, variable_def=vardef)
                    self.datastore.add_entry(entry_var)
                except Exception as e:
                    self.logger.warning('Cannot add entry "%s". %s' % (fullname, str(e)))
                    self.logger.debug(traceback.format_exc())

            for fullname, alias in self.sfd.get_aliases_for_datastore():
                try:
                    refentry = self.datastore.get_entry_by_display_path(alias.get_target())
                    entry_alias = DatastoreAliasEntry(aliasdef=alias, refentry=refentry)
                    self.datastore.add_entry(entry_alias)
                except Exception as e:
                    self.logger.warning('Cannot add entry "%s". %s' % (fullname, str(e)))
                    self.logger.debug(traceback.format_exc())

            for callback in self.loaded_callbacks:
                try:
                    callback.__call__(self.sfd)
                except Exception as e:
                    self.logger.critical('Error in SFD Load callback. %s' % str(e))
                    self.logger.debug(traceback.format_exc())

        else:
            if verbose:
                self.logger.warning('No SFD file installed for device with firmware ID %s' % firmware_id)

    def get_loaded_sfd(self) -> Optional[FirmwareDescription]:
        """Returns the loaded Firmware Description. None is returned if none is loaded"""
        return self.sfd

    def reset_active_sfd(self) -> None:
        """Unload any SFD that is loaded and clear the datastore from any material coming from the SFD"""
        must_call_callback = (self.sfd is not None)

        self.sfd = None
        # We only clear the entry types coming from the SFD. (i.e. no RPV)
        self.datastore.clear(EntryType.Alias)
        self.datastore.clear(EntryType.Var)
        if must_call_callback:
            self.logger.debug('Triggering SFD Unload callback')
            for callback in self.unloaded_callbacks:
                try:
                    callback.__call__()
                except Exception as e:
                    self.logger.critical('Error in SFD Unload callback. %s' % str(e))
                    self.logger.debug(traceback.format_exc())
