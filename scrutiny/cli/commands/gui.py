#    gui.py
#        Command to start the GUI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import argparse
import logging

from .base_command import BaseCommand
from typing import Optional, List, Any, Dict, cast


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

    def run(self) -> Optional[int]:
        from scrutiny.gui.gui import ScrutinyQtGUI

        args = self.parser.parse_args(self.args)
        gui = ScrutinyQtGUI(debug_layout=args.debug_layout)
    
        return gui.run([])
