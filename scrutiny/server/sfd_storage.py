
__all__ = ['SFDStorage']

import os
from scrutiny.server.globals import get_server_storage
from scrutiny.core.sfd_storage_manager import SFDStorageManager

SFDStorage = SFDStorageManager(os.path.join(get_server_storage(), 'sfd_storage'))
