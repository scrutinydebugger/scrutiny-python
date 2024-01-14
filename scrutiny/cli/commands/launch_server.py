#    launch_server.py
#        CLI Command to launch the scrutiny server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import argparse
import logging

from .base_command import BaseCommand
from typing import Optional, List


class LaunchServer(BaseCommand):
    _cmd_name_ = 'launch-server'
    _brief_ = 'Launch an instance of the server'
    _group_ = 'Server'

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('--config', default=None, help='Configuration file used by the server')
        self.parser.add_argument('--log_websockets', default='error', metavar='LEVEL', help="Verbosity level of websockets module")

    def run(self) -> Optional[int]:
        from scrutiny.server.server import ScrutinyServer

        args = self.parser.parse_args(self.args)

        # For server, we will add more details to logging message.
        format_string = '%(asctime)s.%(msecs)03d [%(levelname)s] <%(name)s> %(message)s'
        time_format = r'%Y-%m-%d %H:%M:%S'
        logging.getLogger().handlers[0].setFormatter(logging.Formatter(format_string, time_format))

        websockets_loggers = ['websockets.server', 'websockets.protocol', 'asyncio']
        logging_level = getattr(logging, args.log_websockets.upper())
        for name in websockets_loggers:
            logging.getLogger(name).setLevel(logging_level)

        success = True
        server = ScrutinyServer(args.config)
        try:
            server.run()
        except Exception:
            # The server logs its own error in run(). No need to print it twice.
            # We will return a non-success error code. It will be picked up by the CLI.
            success = False

        return 0 if success else -1
