#    cli.py
#        Provide the Command Line Interface.
#        Allow to launch specific functionality by invoking Scrutiny with command line arguments.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

import os
import argparse
import logging
import traceback

from scrutiny.cli.commands import *


class CLI:

    def __init__(self, workdir='.', default_log_level='info'):
        self.workdir = workdir
        self.default_log_level = default_log_level

        self.command_list = get_all_commands()  # comes from commands module
        self.parser = argparse.ArgumentParser(
            prog='scrutiny',
            epilog=self.make_command_list_help(),
            add_help=False,
            formatter_class=argparse.RawTextHelpFormatter
        )
        self.parser.add_argument('command', help='Command to execute')
        self.parser.add_argument('--loglevel', help='Log level to use', default=None, metavar='LEVEL')
        self.parser.add_argument('--logfile', help='File to write logs', default=None, metavar='FILENAME')

    def make_command_list_help(self):
        msg = "Here are the possible commands\n\n"
        commands = get_commands_by_groups()
        groups = list(commands.keys())
        if '' in groups:
            groups.remove('')  # Put ungrouped commands at the end
            groups.append('')

        for group in groups:
            longest_cmd_name = 0    # Use that to align commands brief description
            group_name = group if group else 'Others'
            msg += "\n--- %s ---\n" % group_name
            for cmd in commands[group]:
                if len(cmd.get_name()) > longest_cmd_name:
                    longest_cmd_name = len(cmd.get_name())

            for cmd in commands[group]:
                padding_length = longest_cmd_name + 4 - len(cmd.get_name())
                msg += "    - %s:%s%s\n" % (cmd.get_name(), ' ' * padding_length, cmd.get_brief())

        return msg

    def run(self, args, except_failed=False):
        code = 0
        if len(args) > 0:
            if args[0] in ['-h', '--help']:
                self.parser.print_help()
                return 0

        args, command_cargs = self.parser.parse_known_args(args)
        if args.command not in [cls.get_name() for cls in self.command_list]:
            if except_failed:
                raise Exception('Unknown command %s' % args.command)
            self.parser.print_help()
            return -1

        error = None
        try:
            logging_level_str = args.loglevel if args.loglevel else self.default_log_level
            logging_level = getattr(logging, logging_level_str.upper())
            format_string = '[%(levelname)s] %(message)s'
            logging.basicConfig(level=logging_level, filename=args.logfile, format=format_string)

            for cmd in self.command_list:
                if cmd.get_name() == args.command:
                    cmd_instance = cmd(command_cargs, requested_log_level=args.loglevel)
                    break

            current_workdir = os.getcwd()
            os.chdir(self.workdir)
            code = 0
            try:
                code = cmd_instance.run()  # Existance of cmd_instance is garanteed as per above check of valid name
                if code is None:
                    code = 0
            except Exception as e:
                error = e
            finally:
                os.chdir(current_workdir)

            if error is not None:
                raise error
        except Exception as e:
            if except_failed:
                raise e
            error = e
            error_stack_strace = traceback.format_exc()

        if error is not None:
            code = 1
            logging.error(str(error))
            logging.debug(error_stack_strace)

        return code
