
__all__ = ['SFDStorage']

import os
from scrutiny.server.globals import SERVER_STORAGE
from scrutiny.core.sfd_storage_manager import SFDStorageManager

SFDStorage = SFDStorageManager(os.path.join(SERVER_STORAGE, 'sfd_storage'))
