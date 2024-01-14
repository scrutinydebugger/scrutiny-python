#    cli.py
#        Provide the Command Line Interface.
#        Allow to launch specific functionality by invoking Scrutiny with command line arguments.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import os
import argparse
import logging
import traceback

from scrutiny.cli.commands import *

from typing import Optional, List, Type

class CLI:
    """Scrutiny Command Line Interface.
    All commands are executed through this class."""

    workdir:str
    default_log_level:str
    command_list:List[Type[BaseCommand]]
    parser:argparse.ArgumentParser


    def __init__(self, workdir:str='.', default_log_level:str='info'):
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
        self.parser.add_argument('--disable_loggers', help='list of loggers to disable', default=None, metavar='LOGGERS')

    def make_command_list_help(self) -> str:
        """Return a string meant to be displayed in the command line explaining the possible commands"""
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

    def run(self, args:List[str], except_failed:bool=False) -> int:
        """Run a command. Arguments must be passed as a list of strings (like they would be splitted in a shell)"""
        if len(args) > 0:   # The help might be for a subcommand, so we take it only if it'S the first argument.
            if args[0] in ['-h', '--help']:
                self.parser.print_help()
                return 0

        cargs, command_cargs = self.parser.parse_known_args(args)
        if cargs.command not in [cls.get_name() for cls in self.command_list]:
            if except_failed:
                raise Exception('Unknown command %s' % cargs.command)
            self.parser.print_help()
            return -1

        error = None
        try:
            logging_level_str = cargs.loglevel if cargs.loglevel else self.default_log_level
            logging_level = getattr(logging, logging_level_str.upper())
            format_string = ""
            if logging_level == logging.DEBUG:
                format_string += "%(relativeCreated)s "    
            format_string += '[%(levelname)s] %(message)s'
            logging.basicConfig(level=logging_level, filename=cargs.logfile, format=format_string)
            if cargs.disable_loggers is not None:
                for logger_name in cargs.disable_loggers.split(','):
                    logging.getLogger(logger_name).disabled = True

            for cmd in self.command_list:
                if cmd.get_name() == cargs.command:
                    cmd_instance = cmd(command_cargs, requested_log_level=cargs.loglevel)
                    break

            current_workdir = os.getcwd()
            os.chdir(self.workdir)
            code:Optional[int] = 0
            try:
                code = cmd_instance.run()  # Existence of cmd_instance is guaranteed as per above check of valid name
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
            logging.debug('Command : scrutiny ' + ' '.join(args))
            logging.debug(error_stack_strace)

        assert code is not None
        return code
