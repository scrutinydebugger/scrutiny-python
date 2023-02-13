#    clear_datalogging_storage.py
#        Make sure that we can read and write to the datalogging storage
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

import argparse

from .base_command import BaseCommand
from typing import Optional, List


class ClearDataloggingStorage(BaseCommand):
    _cmd_name_ = 'clear-datalogging-storage'
    _brief_ = 'Delete the datalogging storage'
    _group_ = 'Server'

    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args

    def run(self) -> Optional[int]:
        from scrutiny.server.datalogging.datalogging_storage import DataloggingStorage

        DataloggingStorage.clear_all()
        return 0
