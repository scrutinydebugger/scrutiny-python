#    launch_gui.py
#        CLI command to launch the Graphical User Interface
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

import argparse
import logging
import traceback
import os

from .base_command import BaseCommand
from typing import Optional, List


class LaunchGUI(BaseCommand):
    _cmd_name_ = 'launch-gui'
    _brief_ = 'Launch an instance of the GUI client'
    _group_ = 'GUI'

    GUI_ENV_VAR = 'SCRUTINY_GUI_WEBAPP'

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('--webapp_folder', default=None,
                                 help="The GUI webapp distribution folder. Will use environment variable %s if unset" % self.GUI_ENV_VAR)
        self.parser.add_argument('--method', default="browser", choices=[
                                 'cef', 'browser'], help='The method used to launch the GUI. "cef": Uses Chromium Embedded Framework. "browser": Launch the GUI in a web browser using the webbrowser python module')
        self.parser.add_argument('--config', default=None, help='Configuration file used by the GUI')
        self.parser.add_argument('--port', default=0, help='Port used by local webserver when GUI is launched in a web browser')

    def run(self) -> Optional[int]:
        from scrutiny.gui.gui_client import GUIClient, LaunchMethod

        args = self.parser.parse_args(self.args)
        success = True
        method = args.method.strip().lower()
        if method == "cef":
            launch_method = LaunchMethod.CEF
        elif method == "browser":
            launch_method = LaunchMethod.WEB_BROWSER
        else:
            raise ValueError('Unknown launch method %s' % args.method)

        webapp_folder = args.webapp_folder
        if webapp_folder is None:
            webapp_folder = os.environ.get(self.GUI_ENV_VAR, None)
        if webapp_folder is None:
            raise ValueError("Cannot find GUI install folder. Please specify one in the CLI or set the environment variable %s" % self.GUI_ENV_VAR)

        gui = GUIClient(webapp_folder, config_filename=args.config, launch_method=launch_method, http_server_port=int(args.port))
        try:
            gui.run()
        except Exception as e:
            logging.critical('GUI error. ' + str(e))
            logging.debug(traceback.format_exc())
            success = False

        return 0 if success else -1
