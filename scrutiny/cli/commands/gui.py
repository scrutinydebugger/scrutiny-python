#    gui.py
#        Command to start the GUI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import argparse
import sys

from .base_command import BaseCommand
from typing import Optional, List, Any, Dict, cast

from scrutiny.gui import DEFAULT_SERVER_PORT

class GUI(BaseCommand):
    _cmd_name_ = 'gui'
    _brief_ = 'Launch an instance of the Graphical User Interface'
    _group_ = 'User interface'

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument("--debug-layout", action='store_true', default=False, help="Enable GUI diagnostic rendering")
        self.parser.add_argument("--auto-connect", action='store_true', default=False, help="Try to connect to a server as soon as the GUI is ready")
        self.parser.add_argument("--no-opengl", action='store_true', default=False, help="Disable OpenGL accelerations")
        self.parser.add_argument("--local-server",  default=None, type=int, help="Starts and connect to a local server listening on the given port")

    def run(self) -> Optional[int]:
        from scrutiny.gui.gui import ScrutinyQtGUI

        args = self.parser.parse_args(self.args)

        gui = ScrutinyQtGUI(
            debug_layout=args.debug_layout,
            auto_connect=(args.auto_connect) or (args.local_server is not None),
            opengl_enabled=not args.no_opengl,
            local_server_starting_port=args.local_server,
        )
    
        return gui.run([])
