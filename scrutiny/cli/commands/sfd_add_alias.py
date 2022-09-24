#    sfd_add_alias.py
#        Defines the sfd-add-alias command used to embed an alias file into an SFD file in
#        the making
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import argparse
from .base_command import BaseCommand
from typing import Optional, List
import logging
import os
import json

class SFDAddAlias(BaseCommand):
    _cmd_name_ = 'sfd-add-alias'
    _brief_ = 'Append an alias file to a SFD work folder'
    _group_ = 'Build Toochain'

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('alias_file', help='The input alias file in .json format')
        self.parser.add_argument('folder', help='Folder containing the firmware description files.')

    def run(self) -> Optional[int]:
        from scrutiny.core.firmware_description import FirmwareDescription, AliasDefinition

        args = self.parser.parse_args(self.args)
        varmap = FirmwareDescription.read_varmap_from_filesystem(args.folder)
        target_alias_file = os.path.join(args.folder, FirmwareDescription.alias_file)
        all_alliases = {}
        if os.path.isfile(target_alias_file):
            with open(target_alias_file, 'rb') as f:
                all_alliases = FirmwareDescription.read_aliases(f)
            
        with open(args.alias_file, 'rb') as f:
            new_aliases = FirmwareDescription.read_aliases(f)
        
        for k in new_aliases:
            alias = new_aliases[k]
            assert k == alias.get_fullpath()
            try:
                varmap.get_var(alias.get_target())
                if k in all_alliases:
                    logging.error('Duplicate alias with path %s' % k)
                else:
                    all_alliases[alias.get_fullpath()] = alias 

            except:
                logging.error('Alias %s refers to non-existent variable %s' % (alias.get_fullpath(), alias.get_target()))

        all_alias_dict = {}
        for k in all_alliases:
            all_alias_dict[k] = all_alliases[k].to_dict()

        with open(target_alias_file, 'wb') as f:
            f.write(json.dumps(all_alias_dict).encode('utf8'))

        return 0
