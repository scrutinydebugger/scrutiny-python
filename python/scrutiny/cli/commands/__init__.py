from .base_command import BaseCommand
from .make_firmware_info import MakeFirmwareInfo
from .get_firmware_id import GateFirmwareId
from .make_metadata import MakeMetadata

def get_all_commands():
    return BaseCommand.__subclasses__()

def get_commands_by_groups():
    commands = get_all_commands()
    groups = {}
    for cmd in commands:
        if cmd.get_group() not in groups:
            groups[cmd.get_group()] = []
        groups[cmd.get_group()].append(cmd)
    return groups