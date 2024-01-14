#    add_alias.py
#        Defines the add-alias command used to embed an alias file into an SFD file in the
#        making
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import argparse
from .base_command import BaseCommand
from typing import Optional, List
import logging
import os
import traceback


class AddAlias(BaseCommand):
    _cmd_name_ = 'add-alias'
    _brief_ = 'Append an alias to a SFD file or in making SFD work folder. Definition can be passed with a file or command line arguments.'
    _group_ = 'Build Toolchain'

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.logger = logging.getLogger('CLI')
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument(
            'destination', help='Where to add the alias. Can be an SFD file, a folder of a in making SFD file or a firmware ID to alter an already installed SFD file.')
        self.parser.add_argument('--file', help='The input alias file in .json format')

        self.parser.add_argument('--fullpath', help='The alias fullpath')
        self.parser.add_argument('--target', help='The target of the alias')
        self.parser.add_argument('--gain', help='The gain to apply when reading the alias')
        self.parser.add_argument('--offset', help='The offset to apply when reading the alias')
        self.parser.add_argument('--min', help='The minimum value for this alias')
        self.parser.add_argument('--max', help='The maximum value for this alias')

    def run(self) -> Optional[int]:
        from scrutiny.core.firmware_description import FirmwareDescription
        from scrutiny.core.alias import Alias
        from scrutiny.core.sfd_storage import SFDStorage

        args = self.parser.parse_args(self.args)

        if args.fullpath is not None and args.file is not None:
            raise Exception('Alias must be defined by a file (--file) or command line parameters (--fullpath + others), but not both.')

        all_alliases = {}
        if os.path.isdir(args.destination):
            varmap = FirmwareDescription.read_varmap_from_filesystem(args.destination)
            target_alias_file = os.path.join(args.destination, FirmwareDescription.alias_file)

            if os.path.isfile(target_alias_file):
                with open(target_alias_file, 'rb') as f:
                    all_alliases = FirmwareDescription.read_aliases(f, varmap)
        elif os.path.isfile(args.destination):
            sfd = FirmwareDescription(args.destination)
            varmap = sfd.varmap
            all_alliases = sfd.get_aliases()
        elif SFDStorage.is_installed(args.destination):
            sfd = SFDStorage.get(args.destination)
            varmap = sfd.varmap
            all_alliases = sfd.get_aliases()
        else:
            raise Exception('Inexistent destination for alias %s' % args.destination)

        if args.file is not None:
            with open(args.file, 'rb') as f:
                new_aliases = FirmwareDescription.read_aliases(f, varmap)
        elif args.fullpath is not None:
            if args.target is None:
                raise Exception('No target specified')

            alias = Alias(
                fullpath=args.fullpath,
                target=args.target,
                gain=args.gain,
                offset=args.offset,
                min=args.min,
                max=args.max
            )

            new_aliases = {}
            new_aliases[alias.get_fullpath()] = alias
        else:
            raise Exception('Alias must be defined through a file or command line by specifying the --target option.')

        for k in new_aliases:
            alias = new_aliases[k]
            assert k == alias.get_fullpath()

            try:
                alias.validate()
            except Exception as e:
                self.logger.error('Alias %s is invalid. %s' % (alias.get_fullpath(), str(e)))
                continue

            try:
                alias.set_target_type(FirmwareDescription.get_alias_target_type(alias, varmap))
            except Exception as e:
                self.logger.error('Cannot deduce type of alias %s referring to %s. %s' % (alias.get_fullpath(), alias.get_target(), str(e)))
                self.logger.debug(traceback.format_exc())
                continue

            if k in all_alliases:
                self.logger.error('Duplicate alias with path %s' % k)
                continue

            all_alliases[alias.get_fullpath()] = alias

        if os.path.isdir(args.destination):
            with open(target_alias_file, 'wb') as f:
                f.write(FirmwareDescription.serialize_aliases(all_alliases))

        elif os.path.isfile(args.destination):
            sfd.append_aliases(new_aliases)
            sfd.write(args.destination)

        elif SFDStorage.is_installed(args.destination):
            SFDStorage.install_sfd(sfd, ignore_exist=True)

        return 0
