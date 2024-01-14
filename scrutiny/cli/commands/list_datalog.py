#    list_datalog.py
#        List all the datalogging acquisition stored on this server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import argparse

from .base_command import BaseCommand
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class DisplayEntry:
    index: str
    reference_id: str
    acq_name: str
    firmware_fullname: str
    dataseries_name: List[str]
    acq_time: str


@dataclass
class DisplayFieldSize:
    index: int = 0
    reference_id: int = 0
    acq_name: int = 0
    firmware_fullname: int = 0
    dataseries_name: int = 0
    acq_time: int = 0

    def update(self, entry: DisplayEntry) -> None:
        self.index = max(self.index, len(entry.index))
        self.reference_id = max(self.reference_id, len(entry.reference_id))
        self.acq_name = max(self.acq_name, len(entry.acq_name))
        self.firmware_fullname = max(self.firmware_fullname, len(entry.firmware_fullname))
        self.acq_time = max(self.acq_time, len(entry.acq_time))
        for name in entry.dataseries_name:
            self.dataseries_name = max(self.dataseries_name, len(name))


class ListDatalog(BaseCommand):
    _cmd_name_ = 'list-datalog'
    _brief_ = 'List all the acquisition stored in the server database'
    _group_ = 'Datalogging'

    parser: argparse.ArgumentParser
    parsed_args: Optional[argparse.Namespace] = None

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('--firmware', action="store_true", help='Show the firmware used to generate this graph')
        self.parser.add_argument('--multiline', action="store_true", help='Print each acquisition signals on its own line')

    def run(self) -> Optional[int]:
        from scrutiny.server.datalogging.datalogging_storage import DataloggingStorage
        from scrutiny.core.sfd_storage import SFDStorage

        self.parsed_args = self.parser.parse_args(self.args)
        DataloggingStorage.initialize()
        acquisitions = DataloggingStorage.list()
        all_entries: List[DisplayEntry] = []
        sizes = DisplayFieldSize()
        index = 0
        for reference_id in acquisitions:
            acq = DataloggingStorage.read(reference_id)
            dataseries_name = [ydata.series.name for ydata in acq.ydata]
            if not self.parsed_args.multiline:
                dataseries_name = [','.join(dataseries_name)]

            entry = DisplayEntry(
                index=str(index),
                reference_id=reference_id,
                acq_name=acq.name if acq.name else "",
                firmware_fullname='%s (<Unknown firmware>)' % acq.firmware_id,
                dataseries_name=dataseries_name,
                acq_time=acq.acq_time.strftime(r'%Y-%m-%d %H:%M:%S')
            )
            index += 1

            if SFDStorage.is_installed(acq.firmware_id):
                firmware_meta = SFDStorage.get_metadata(acq.firmware_id)
                entry.firmware_fullname = "%s (%s V%s)" % (acq.firmware_id, firmware_meta['project_name'], firmware_meta['version'])
            sizes.update(entry)
            all_entries.append(entry)

        if len(all_entries) == 0:
            print("No acquisitions")
        else:
            header = DisplayEntry(
                index='#',
                acq_name="Name",
                dataseries_name=['Signals'],
                firmware_fullname='Firmware',
                reference_id='ID',
                acq_time='Time'
            )
            sizes.update(header)

            print()  # Ensure new line
            self.print_line(header, sizes)
            all_entries.sort(key=lambda x: x.acq_time)
            index = 0
            for entry in all_entries:
                entry.index = str(index)
                self.print_line(entry, sizes)
                index += 1

        return 0

    def print_line(self, entry: DisplayEntry, sizes: DisplayFieldSize) -> None:
        assert self.parsed_args is not None
        SEPARATOR_SIZE = 4
        delta = sizes.index - len(str(entry.index))
        print(str(entry.index) + ' ' * (delta + SEPARATOR_SIZE), end="")

        delta = sizes.acq_time - len(str(entry.acq_time))
        print(str(entry.acq_time) + ' ' * (delta + SEPARATOR_SIZE), end="")

        delta = sizes.acq_name - len(entry.acq_name)
        print(entry.acq_name + ' ' * (delta + SEPARATOR_SIZE), end="")

        delta = sizes.reference_id - len(entry.reference_id)
        print(entry.reference_id + ' ' * (delta + SEPARATOR_SIZE), end="")

        if (self.parsed_args.firmware):
            delta = sizes.firmware_fullname - len(entry.firmware_fullname)
            print(entry.firmware_fullname + ' ' * (delta + SEPARATOR_SIZE), end="")

        if len(entry.dataseries_name) > 0:
            delta = sizes.dataseries_name - len(entry.dataseries_name[0])
            print(entry.dataseries_name[0] + ' ' * (delta + SEPARATOR_SIZE), end="")

        for i in range(1, len(entry.dataseries_name)):
            name = entry.dataseries_name[i]
            total_offset = sizes.acq_time + sizes.acq_name + sizes.reference_id + 3 * SEPARATOR_SIZE
            if self.parsed_args.firmware:
                total_offset += sizes.firmware_fullname + SEPARATOR_SIZE
            print()
            print(' ' * total_offset + name, end="")

        print()
