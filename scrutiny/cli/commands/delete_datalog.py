#    delete_datalog.py
#        Delete a single or all datalogging acquisitions
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2023 Scrutiny Debugger

__all__ = ['DeleteDatalog']

import argparse

from .base_command import BaseCommand
from scrutiny.tools.typing import *


class DeleteDatalog(BaseCommand):
    _cmd_name_ = 'delete-datalog'
    _brief_ = 'Delete one or all datalogging acquisitions'
    _group_ = 'Datalogging'

    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('--id', help='The ID of the datalogging acquisition')
        self.parser.add_argument('--all', action="store_true", help='Delete all datalogging acquisition')

    def run(self) -> Optional[int]:
        from scrutiny.server.datalogging.datalogging_storage import DataloggingStorage

        args = self.parser.parse_args(self.args)
        if args.all:
            DataloggingStorage.clear_all()
            self.getLogger().info("All datalogs deleted")
        elif args.id:
            DataloggingStorage.initialize()
            DataloggingStorage.delete(args.id)
            self.getLogger().info(f"Datalog {args.id} deleted")
        else:
            raise ValueError("An acquisition ID must be provided or --all")
        return 0
