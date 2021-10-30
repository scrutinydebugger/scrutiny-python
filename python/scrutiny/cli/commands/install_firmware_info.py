import argparse

from .base_command import BaseCommand
from scrutiny.core.sfi_storage import SFIStorage

class InstallFirmwareInfo(BaseCommand):
    _cmd_name_ = 'install-firmware-info'
    _brief_ = 'Install a Firmware Info file globally for the current user so that it can be loaded automatically upon connection with a device.'
    _group_ = 'Server'

    def __init__(self, args):
        self.args = args
        self.parser = argparse.ArgumentParser(prog = self.get_prog() )
        self.parser.add_argument('file',  help='Scrutiny Firmware Information (SFI) file to be installed')

    def run(self):
        args = self.parser.parse_args(self.args)
        SFIStorage.install(args.file)
        