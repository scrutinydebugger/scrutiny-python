#    launch_gui.py
#        CLI command to launch the Graphical User Interface
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import argparse
import logging
import traceback

from .base_command import BaseCommand
from typing import Optional, List


class LaunchGUI(BaseCommand):
    _cmd_name_ = 'launch-gui'
    _brief_ = 'Launch an instance of the GUI client'
    _group_ = 'GUI'

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('--method', default=None, choices=[
                                 'cef', 'browser'], help='The method used to launch the GUI. "cef": Uses Chromium Embedded Framework. "browser": Launch the GUI in a web browser using the webbrowser python module')
        self.parser.add_argument('--config', default=None, help='Configuration file used by the GUI')
        self.parser.add_argument('--port', default=0, help='Port used by local webserver when GUI is launched in a web browser')

    def run(self) -> Optional[int]:
        from scrutiny.gui.gui_client import GUIClient, LaunchMethod

        args = self.parser.parse_args(self.args)
        success = True
        launch_method = LaunchMethod.NONE
        if args.method is not None:
            if args.method.strip().lower() == "cef":
                launch_method = LaunchMethod.CEF
            elif args.method.strip().lower() == "browser":
                launch_method = LaunchMethod.WEB_BROWSER
            else:
                raise ValueError('Unknown launch method %s' % args.method)

        gui = GUIClient(config_filename=args.config, launch_method=launch_method, http_server_port=int(args.port))
        try:
            gui.run()
        except Exception as e:
            logging.critical('GUI error. ' + str(e))
            logging.debug(traceback.format_exc())
            succes = False

        return 0 if success else -1
