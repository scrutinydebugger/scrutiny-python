#    datalog_info.py
#        Command that return some information about datalogging such as storage location,
#        size, number of acquisitions
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import argparse

from .base_command import BaseCommand
from typing import Optional, List
from dataclasses import dataclass
from typing import List, Optional, Union


@dataclass
class OutputTableRow:
    title: str
    value: Union[int, str]


def sizeof_fmt(num:float, suffix:str="B") -> str:
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


class DatalogInfo(BaseCommand):
    _cmd_name_ = 'datalog-info'
    _brief_ = 'Show the actual status of the datalogging database'
    _group_ = 'Datalogging'

    parser: argparse.ArgumentParser
    parsed_args: Optional[argparse.Namespace] = None

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None) -> None:
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())

    def run(self) -> Optional[int]:
        from scrutiny.server.datalogging.datalogging_storage import DataloggingStorage

        table_output: List[OutputTableRow] = []

        self.parsed_args = self.parser.parse_args(self.args)
        DataloggingStorage.initialize()
        acquisitions = DataloggingStorage.list()
        timerange = DataloggingStorage.get_timerange()
        db_hash = DataloggingStorage.get_db_hash()
        date_format = r"%Y-%m-%d %H:%M:%S"

        table_output.append(OutputTableRow(title="Acquisitions count", value=len(acquisitions)))
        table_output.append(OutputTableRow(title="Oldest acquisition", value="N/A" if timerange is None else timerange[0].strftime(date_format)))
        table_output.append(OutputTableRow(title="Newest acquisition", value="N/A" if timerange is None else timerange[1].strftime(date_format)))
        table_output.append(OutputTableRow(title="Storage location", value=DataloggingStorage.get_db_filename()))
        table_output.append(OutputTableRow(title="Storage size", value=sizeof_fmt(DataloggingStorage.get_size())))
        table_output.append(OutputTableRow(title="Storage structure hash", value="N/A" if db_hash is None else "%s" % db_hash))

        col_size_title = 0
        for line in table_output:
            col_size_title = max(col_size_title, len(line.title))

        for line in table_output:
            padding = col_size_title - len(line.title)
            print("  %s:%s  %s" % (line.title, " " * padding, line.value))

        return 0
