import argparse
import logging
import traceback

from .base_command import BaseCommand
from scrutiny.gui.gui_client import GUIClient
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
        self.parser.add_argument('--config', default=None, help='Configuration file used by the GUI')

    def run(self) -> Optional[int]:
        args = self.parser.parse_args(self.args)
        success = True
        gui = GUIClient(args.config)
        try:
            gui.run()
        except Exception as e:
            logging.critical(str(e))
            logging.debug(traceback.format_exc())
            succes = False

        return 0 if success else -1
