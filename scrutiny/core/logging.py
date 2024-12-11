__all__ = [
    'DUMPDATA_LOGLEVEL'
]

import logging
DUMPDATA_LOGLEVEL = logging.DEBUG-1
logging.addLevelName(DUMPDATA_LOGLEVEL, "DUMPDATA")
