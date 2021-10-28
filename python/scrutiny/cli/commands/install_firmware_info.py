import argparse
import appdirs
import os
import logging

from .base_command import BaseCommand
from scrutiny.core.firmware_info_file import FirmwareInfoFile

class InstallFirmwareInfo(BaseCommand):
    _cmd_name_ = 'install-firmware-info'
    _brief_ = 'Install a Firmware Info File globally for the current user so that it can be loaded automatically upon connection with a device.'
    _group_ = 'Server'

    def __init__(self, args):
        self.args = args
        self.parser = argparse.ArgumentParser(prog = self.get_prog() )
        self.parser.add_argument('file',  help='Firmware Information File to be installed')

    def run(self):
        args = self.parser.parse_args(self.args)

        fif = FirmwareInfoFile(args.file)
        data_dir = appdirs.user_data_dir('fif_storage', 'scrutiny')
        os.makedirs(data_dir, exist_ok=True)
        output_file = os.path.join(data_dir, fif.get_firmware_id(ascii=True))
        
        if os.path.isfile(output_file):
            logging.warning('A Firmware Information File with the same firmware ID was already installed. Overwriting.')

        fif.write(output_file)  # Write the Firmware Information File in storage folder with firmware ID as name
