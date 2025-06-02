#    sfd_storage.py
#        Declaration of the server-wide SFD storage
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['SFDStorage']

import os
from scrutiny.server.globals import get_server_storage
from scrutiny.core.sfd_storage_manager import SFDStorageManager

SFDStorage = SFDStorageManager(os.path.join(get_server_storage(), 'sfd_storage'))
