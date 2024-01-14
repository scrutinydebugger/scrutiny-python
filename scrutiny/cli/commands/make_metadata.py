#    make_metadata.py
#        CLI Command to generate the metadata file that will be included in a Scrutiny Firmware
#        Description file
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import argparse
from .base_command import BaseCommand
import json
import os
import datetime
import platform
from typing import Optional, List


class MakeMetadata(BaseCommand):
    _cmd_name_ = 'make-metadata'
    _brief_ = 'Generate a .json file containing the metadata used inside a SFD (Scrutiny Firmware Description)'
    _group_ = 'Build Toolchain'

    DEFAULT_NAME = 'metadata.json'

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())

        self.parser.add_argument('--output', default=None,
                                 help='Output filename. If a directory is given, the file will defautly be name "%s" ' % self.DEFAULT_NAME)
        self.parser.add_argument('--project-name', default='',
                                 help='A project name to be displayed in the GUI when connecting to a device that match the Firmware Info File that includes this metadata')
        self.parser.add_argument('--author', default='', help='The author of the project. For display in the GUI only.')
        self.parser.add_argument('--version', default='', help='Version of the project, for display in the GUI only.')

    def run(self) -> Optional[int]:
        import scrutiny
        from scrutiny.core.firmware_description import MetadataType
        args = self.parser.parse_args(self.args)

        if args.output is None:
            output_file = self.DEFAULT_NAME
        elif os.path.isdir(args.output):
            output_file = os.path.join(args.output, self.DEFAULT_NAME)
        else:
            output_file = args.output

        try:
            scrutiny_version = scrutiny.__version__
        except Exception:
            scrutiny_version = '0.0.0'

        metadata: MetadataType = {
            'project_name': args.project_name,
            'author': args.author,
            'version': args.version,
            'generation_info': {
                'time': round(datetime.datetime.now().timestamp()),
                'python_version': platform.python_version(),
                'scrutiny_version': scrutiny_version,
                'system_type': platform.system()
            }
        }

        with open(output_file, 'w') as f:
            f.write(json.dumps(metadata, indent=4))

        return 0
