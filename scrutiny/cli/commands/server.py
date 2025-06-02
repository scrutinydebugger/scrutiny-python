#    server.py
#        Command that launches the Scrutiny server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

__all__ = ['Server']

import argparse
import logging

from .base_command import BaseCommand
from scrutiny.tools.typing import *


class Server(BaseCommand):
    _cmd_name_ = 'server'
    _brief_ = 'Launch an instance of the server'
    _group_ = 'Server'

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('--config', default=None, help='Configuration file used by the server')
        self.parser.add_argument('--port', default=None, required=False, help='TCP port used to listen or clients')
        self.parser.add_argument('--options', metavar='OPTION', nargs='*', help="Server configuration passed by the CLI."
                                 " Specified as a list of key=value where key can be a nested dict where the a dot (.) represent a nesting level. 'a.b.c=val'"
                                 "Overrides file configuration if specified.")

    def str_to_dict(self, path: str, val: Any, separator: str = '.') -> Dict[Any, Any]:
        parts = path.split(separator)
        if len(parts) == 0:
            raise ValueError(f"Invalid dict path string '{path}'")

        d: Dict[Any, Any] = {}
        ref = d
        for i in range(len(parts)):
            if i < len(parts) - 1:
                ref[parts[i]] = {}
                ref = ref[parts[i]]
            else:
                ref[parts[i]] = val

        return d

    def run(self) -> Optional[int]:
        from scrutiny.server.server import ScrutinyServer, ServerConfig
        from scrutiny.tools import update_dict_recursive

        args = self.parser.parse_args(self.args)
        if args.options is None:
            args.options = []

        if args.port is not None:
            args.options.append(f'api.client_interface_config.port={args.port}')    # Append should override in case of duplicate

        # For the server, we will add more details to logging message.
        format_string = '%(asctime)s.%(msecs)03d [%(levelname)s] <%(name)s> %(message)s'
        time_format = r'%Y-%m-%d %H:%M:%S'
        logging.getLogger().handlers[0].setFormatter(logging.Formatter(format_string, time_format))

        extra_configs: Dict[Any, Any] = {}
        if args.options is not None:
            for o in args.options:
                parts = o.split('=')
                if len(parts) != 2:
                    raise ValueError("Command line options must have the format 'name=value'")
                update_dict_recursive(extra_configs, self.str_to_dict(parts[0], parts[1], separator='.'))

        success = True
        server = ScrutinyServer(args.config, additional_config=cast(ServerConfig, extra_configs))
        try:
            server.run()
        except Exception:
            # The server logs its own error in run(). No need to print it twice.
            # We will return a non-success error code. It will be picked up by the CLI.
            success = False

        return 0 if success else 1
