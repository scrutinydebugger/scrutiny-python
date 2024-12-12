#    logging.py
#        Some global definition for logging
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = [
    'DUMPDATA_LOGLEVEL'
]

import logging
DUMPDATA_LOGLEVEL = logging.DEBUG-1
logging.addLevelName(DUMPDATA_LOGLEVEL, "DUMPDATA")
