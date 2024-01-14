#    export_datalog.py
#        Extract a datalogging acquisition and export it into a common format, such as CSV
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import argparse
import logging

from .base_command import BaseCommand
from typing import Optional, List


class ExportDatalog(BaseCommand):
    _cmd_name_ = 'export-datalog'
    _brief_ = 'Export a datalogging acquisition to a file'
    _group_ = 'Datalogging'

    parser: argparse.ArgumentParser
    parsed_args: Optional[argparse.Namespace] = None

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('reference_id', help='The acquisition reference ID')
        self.parser.add_argument('--csv', help='Output to CSV file')

    def run(self) -> Optional[int]:
        from scrutiny.server.datalogging.datalogging_storage import DataloggingStorage
        from scrutiny.core.sfd_storage import SFDStorage

        self.parsed_args = self.parser.parse_args(self.args)
        DataloggingStorage.initialize()

        # Check if at least one of the supported is selected
        if not self.parsed_args.csv:
            raise ValueError("At least one  export method must be specified")

        acquisition = DataloggingStorage.read(reference_id=self.parsed_args.reference_id)

        if self.parsed_args.csv:
            acquisition.to_csv(self.parsed_args.csv)

        return 0
