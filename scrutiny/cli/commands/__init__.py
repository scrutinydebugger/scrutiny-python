__all__ = [
    'BaseCommand',
    'MakeSFD',
    'GetFirmwareId',
    'TagFirmwareID',
    'MakeMetadata',
    'InstallSFD',
    'UninstallSFD',
    'ListSFD',
    'Elf2VarMap',
    'LaunchServer',
    'RunTest',
    'AddAlias',
    'DeleteDatalog',
    'ListDatalog',
    'ExportDatalog',
    'DatalogInfo',
    'get_all_commands',
    'get_commands_by_groups'
]

from .base_command import BaseCommand
from .make_sfd import MakeSFD
from .get_firmware_id import GetFirmwareId
from .tag_firmware_id import TagFirmwareID
from .make_metadata import MakeMetadata
from .install_sfd import InstallSFD
from .uninstall_sfd import UninstallSFD
from .list_sfd import ListSFD
from .elf2varmap import Elf2VarMap
from .launch_server import LaunchServer
from .runtest import RunTest
from .add_alias import AddAlias
from .delete_datalog import DeleteDatalog
from .list_datalog import ListDatalog
from .export_datalog import ExportDatalog
from .datalog_info import DatalogInfo

from typing import List, Dict, Type


def get_all_commands() -> List[Type[BaseCommand]]:
    """Return a list of class object. One for each possible CLI command"""
    return BaseCommand.__subclasses__()


def get_commands_by_groups() -> Dict[str, List[Type[BaseCommand]]]:
    """Return all possible CLI command, grouped in a dictionnary by group string"""
    commands = get_all_commands()
    groups: Dict[str, List[Type[BaseCommand]]] = {}
    for cmd in commands:
        if cmd.get_group() not in groups:
            groups[cmd.get_group()] = []
        groups[cmd.get_group()].append(cmd)
    return groups
