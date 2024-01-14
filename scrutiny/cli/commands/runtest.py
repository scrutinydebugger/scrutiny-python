#    runtest.py
#        CLI Command to launch the python unit tests
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import argparse
from .base_command import BaseCommand
import unittest
import logging
from typing import Optional, List
import traceback


class RunTest(BaseCommand):
    _cmd_name_ = 'runtest'
    _brief_ = 'Run unit tests'
    _group_ = 'Development'

    requested_log_level: Optional[str]
    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('--module', default=None, help='The test module to run. All if not specified')
        self.parser.add_argument('--verbosity', default=2, help='Verbosity level of the unittest module')
        self.parser.add_argument('--root', default=None, help='Path to the test root folder')
        self.requested_log_level = requested_log_level

    def run(self) -> Optional[int]:
        import scrutiny
        import os
        import sys
        success = -1

        args = self.parser.parse_args(self.args)
        if args.root is not None:
            test_root = os.path.abspath(os.path.realpath(args.root))
            if not os.path.isdir(test_root):
                raise FileNotFoundError("Folder %s does not exists" % test_root)
        else:
            test_root = os.path.realpath(os.path.join(os.path.dirname(scrutiny.__file__), '../test'))
        sys.path.insert(0, test_root)   # So that "import test" correctly load scrutiny test env if cpython has its own unit tests available in the path

        format_string = ""
        logging_level_str = self.requested_log_level if self.requested_log_level else "critical"
        logging_level = getattr(logging, logging_level_str.upper())
        if logging_level == logging.DEBUG:
            format_string += "%(relativeCreated)0.3f "
        format_string += '[%(levelname)s] <%(name)s> %(message)s'
        logging.getLogger().handlers[0].setFormatter(logging.Formatter(format_string))
        logging.getLogger().setLevel(logging_level)

        import test  # load the test module.
        if not hasattr(test, '__scrutiny__'):   # Make sure this is Scrutiny Test folder (in case we run from install dir)
            if args.root is None:
                logging.getLogger(self._cmd_name_).critical(
                    'No scrutiny unit tests available in %s. Consider passing a test folder with --root if you run the tests from an installed module' % test_root)
            else:
                logging.getLogger(self._cmd_name_).critical('No unit tests available in %s' % test_root)
        else:
            try:
                loader = unittest.TestLoader()
                if args.module is None:
                    suite = loader.discover(test_root)
                else:
                    suite = loader.loadTestsFromName(args.module)

                result = unittest.TextTestRunner(verbosity=int(args.verbosity)).run(suite)
                success = len(result.errors) == 0 and len(result.failures) == 0
            except Exception:
                # Exception are printed as errors, but errors are disabled in the unit test to avoid confusion on negative test
                # So unrecoverable error such as importError and syntax errors needs to be printed
                traceback.print_exc(file=sys.stderr)
                success = False
        return 0 if success else -1
