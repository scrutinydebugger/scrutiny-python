#    gui.py
#        Command to start the GUI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = ['GUI']

import argparse
import os

from .base_command import BaseCommand
from scrutiny.tools.typing import *

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
        self.parser.add_argument("--local-server-port", default=DEFAULT_SERVER_PORT, type=int, help="Set the listening port for the local server")
        self.parser.add_argument("--start-local-server", default=False, action='store_true', help="Starts a local server")
        self.parser.add_argument("--theme", default=None, choices=['default', 'fusion'], help="The GUI theme to use")

    def run(self) -> Optional[int]:
        from scrutiny.gui.gui import ScrutinyQtGUI, SupportedTheme

        args = self.parser.parse_args(self.args)

        theme_str: Optional[str] = os.environ.get('SCRUTINY_THEME', None)

        theme = SupportedTheme.Fusion
        if args.theme is not None:
            theme_str = args.theme

        if theme_str is not None:
            if theme_str == 'fusion':
                theme = SupportedTheme.Fusion
            elif theme_str == 'default':
                theme = SupportedTheme.Default

        gui = ScrutinyQtGUI(
            debug_layout=args.debug_layout,
            auto_connect=args.auto_connect,
            opengl_enabled=not args.no_opengl,
            local_server_port=args.local_server_port,
            start_local_server=args.start_local_server,
            theme=theme
        )

        return gui.run([])
