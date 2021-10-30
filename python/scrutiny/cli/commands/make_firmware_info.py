import argparse
from .base_command import BaseCommand
from scrutiny.core.firmware_info_file import FirmwareInfoFile
from scrutiny.core.sfi_storage import SFIStorage

class MakeFirmwareInfo(BaseCommand):
    _cmd_name_ = 'make-firmware-info'
    _brief_ = 'Generates a Firmware Information File from a given folder containing the required files.'
    _group_ = 'Build Toochain'

    def __init__(self, args):
        self.args = args
        self.parser = argparse.ArgumentParser( prog = self.get_prog() )
        self.parser.add_argument('folder',  help='Folder containing the firmware description files.')
        self.parser.add_argument('output',  help='Destination file')
        self.parser.add_argument('--install', action="store_true",  help='Install the firmwre info file after making it')

    def run(self):
        args = self.parser.parse_args(self.args)
        fif = FirmwareInfoFile(args.folder)
        fif.write(args.output)

        if args.install:
            SFIStorage.install(args.output)
