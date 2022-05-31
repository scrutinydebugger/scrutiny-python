#    list_sfd.py
#        Print a list of all installed Scrutiny Firmware Description files (SFD) installed
#        on this system
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import argparse
from .base_command import BaseCommand
from scrutiny.core.firmware_description import FirmwareDescription
from scrutiny.core.sfd_storage import SFDStorage
from typing import Optional, List
import logging
import traceback
import time 

class PrintableSFDEntry:
    firmware_id:Optional[str]
    create_time:Optional[int]
    scrutiny_version:Optional[str]
    project_name: str
    version: str
    author:str

    def __init__(self):
        self.firmware_id = None
        self.create_time = None
        self.scrutiny_version = None
        self.project_name = 'No Name'
        self.version = 'No version'
        self.author = 'No author'


    def __str__(self):
        create_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.create_time))
        line = '%s %s (%s)\tScrutiny %s \t Created on %s' % (self.project_name, self.version, self.firmware_id, self.scrutiny_version, create_time_str)
        return line


class ListSFD(BaseCommand):
    _cmd_name_ = 'list-sfd'
    _brief_ = 'List all installed SFD'
    _group_ = 'Server'

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())

    def run(self) -> Optional[int]:
        sfd_list:List[PrintableSFDEntry] = []
        args = self.parser.parse_args(self.args)
        firmware_id_list = SFDStorage.list()
        for firmware_id in firmware_id_list:
            try:
                metadata = SFDStorage.get_metadata(firmware_id)
                entry = PrintableSFDEntry()
                entry.firmware_id = firmware_id
                entry.create_time = metadata['generation_info']['time']
                entry.scrutiny_version = metadata['generation_info']['scrutiny_version']
                str(entry) # Make sure it can be rendered. Otherwise exception will be raised
                
                try:
                    entry.project_name = metadata['project_name']
                except:
                    pass

                try:
                    entry.version = metadata['version']
                except:
                    pass

                try:
                    entry.author = metadata['author']
                except:
                    pass

                sfd_list.append(entry)

            except Exception as e:  
                logging.warning('Cannot read SFD with firmware ID %s. %s' % (firmware_id, str(e)))
                logging.debug(traceback.format_exc())

        print('Number of valid SFD installed: %d' % len(sfd_list))
        
        sfd_list.sort(key=lambda x: (x.project_name, x.version, x.create_time))

        for entry in sfd_list:
            print(entry)

        return 0
