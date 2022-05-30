#    active_sfd_handler.py
#        Manage the loaded SFD file with which the client will interracts.
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import logging
import enum

from scrutiny.core import FirmwareDescription
from scrutiny.core.sfd_storage import SFDStorage
from scrutiny.server.device import DeviceHandler
from scrutiny.server.datastore import DatastoreEntry

from typing import Optional



class ActiveSFDHandler:

    sfd:Optional[FirmwareDescription]
    device_status:DeviceHandler.ConnectionStatus
    previous_device_status:DeviceHandler.ConnectionStatus

    def __init__(self, device_handler, datastore, autoload=True):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.device_handler = device_handler
        self.datastore = datastore
        self.autoload = autoload

        self.sfd = None
        self.device_status = DeviceHandler.ConnectionStatus.UNKNOWN
        self.previous_device_status = DeviceHandler.ConnectionStatus.UNKNOWN
        self.requested_firmware_id = None

        self.reset_active_sfd()

    def init(self):
        self.reset_active_sfd()

    def close(self):
        pass

    def process(self):
        device_status = self.device_handler.get_connection_status()

        if self.autoload:
            if device_status != DeviceHandler.ConnectionStatus.CONNECTED_READY:
                self.reset_active_sfd()
            else:
                if self.sfd is None:
                    verbose = self.previous_device_status != self.device_status
                    device_id = self.device_handler.get_device_id()
                    if device_id is not None:
                        self.load_sfd(device_id, verbose=verbose)
                    else:
                        self.logger.critical('No device ID available when connected. This should not happen')

        if self.requested_firmware_id is not None:
            self.load_sfd(self.requested_firmware_id)
            self.requested_firmware_id = None

        self.previous_device_status = device_status

    def request_load_sfd(self, firmware_id:str) -> None:
        if not SFDStorage.is_installed(firmware_id):
            raise Exception('Firmware ID %s is not installed' % firmware_id )

        self.requested_firmware_id = firmware_id

    def load_sfd(self, firmware_id:str, verbose=True) -> None:
        self.sfd = None
        self.datastore.clear()

        if SFDStorage.is_installed(firmware_id):
            self.logger.info('Loading firmware description file (SFD) for firmware ID %s' % firmware_id)
            self.sfd = SFDStorage.get(firmware_id)

            # populate datastore
            for fullname, vardef in self.sfd.get_vars_for_datastore():
                entry = DatastoreEntry(entry_type = DatastoreEntry.EntryType.Var, display_path = fullname, variable_def = vardef)
                self.datastore.add_entry(entry)

        else:
            if verbose:
                self.logger.warning('No SFD file installed for device with firmware ID %s' % firmware_id)

    def get_loaded_sfd(self) -> Optional[FirmwareDescription]:
        return self.sfd

    def reset_active_sfd(self):
        self.sfd = None
        self.datastore.clear()

