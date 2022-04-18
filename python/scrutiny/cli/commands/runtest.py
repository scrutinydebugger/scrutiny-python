#    runtest.py
#        CLI Command to launch the python unit tests
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import argparse
from .base_command import BaseCommand
import unittest
import logging


class RunTest(BaseCommand):
    _cmd_name_ = 'runtest'
    _brief_ = 'Run unit tests'
    _group_ = 'Development'

    def __init__(self, args):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('--module', default=None, help='The test module to run. All if not specified')
        self.parser.add_argument('--verbosity', default=2, help='Verbosity level of the unittest module')

    def run(self):
        args = self.parser.parse_args(self.args)

        format_string = '[%(levelname)s] <%(name)s> %(message)s'
        logging.getLogger().handlers[0].setFormatter(logging.Formatter(format_string))

        loader = unittest.TestLoader()
        if args.module is None:
            suite = loader.discover('test')
        else:
            suite = loader.loadTestsFromName(args.module)

        unittest.TextTestRunner(verbosity=int(args.verbosity)).run(suite)
