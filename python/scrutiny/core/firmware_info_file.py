from zipfile import ZipFile
import os
import json
import logging

import scrutiny.core.firmware_id as firmware_id
from scrutiny.core.varmap import VarMap

class FirmwareInfoFile:
    varmap_filename = 'varmap.json'
    metadata_filename = 'metadata.json'
    firmwareid_filename = 'firmwareid'

    REQUIRED_FILES = [
        firmwareid_filename,
        metadata_filename,
        varmap_filename
    ]

    def __init__(self, file_folder):
        if os.path.isdir(file_folder):
            self.load_from_folder(file_folder)
        elif os.path.isfile(file_folder):
            self.load_from_file(file_folder)
        
        self.validate()

    def load_from_folder(self, folder):
        if not os.path.isdir(folder):
            raise Exception("Folder %s does not exist" % folder)

        for file in self.REQUIRED_FILES:
            if not os.path.isfile(os.path.join(folder,file)):
                raise Exception('Missing %s' % file)

        metadata_file = os.path.join(folder, self.metadata_filename)
        with open(metadata_file) as f:
            self.metadata = json.loads(f.read())

        with open(os.path.join(folder, self.firmwareid_filename)) as f:
            self.firmwareid = bytes.fromhex(f.read())

        self.varmap = VarMap(os.path.join(folder, self.varmap_filename))

    def load_from_file(self, filename):
        with ZipFile(filename, mode='r') as fif:
            with fif.open(self.firmwareid_filename) as f:
                self.firmwareid = bytes.fromhex(f.read().decode('ascii'))

            with fif.open(self.metadata_filename) as f:
                self.metadata = json.loads(f.read())

            with fif.open(self.varmap_filename) as f:
                self.varmap = VarMap(f.read())

    def write(self, filename):
        with ZipFile(filename, mode='w') as outzip:
            outzip.writestr(self.firmwareid_filename, self.firmwareid.hex())
            outzip.writestr(self.metadata_filename, json.dumps(self.metadata, indent=4))
            outzip.writestr(self.varmap_filename, self.varmap.get_json() )

    def get_firmware_id(self, ascii=True):
        if ascii:
            return self.firmwareid.hex()
        else:
            return self.firmwareid

    def validate(self):
        if not hasattr(self, 'metadata') or not hasattr(self, 'varmap') or not hasattr(self, 'firmwareid'):
            raise Exception('FirmwareInfoFile not loaded correctly')

        self.validate_metadata()
        self.validate_firmware_id()
        self.varmap.validate()

    def validate_firmware_id(self):
        if len(self.firmwareid) != len(firmware_id.PLACEHOLDER):
            raise Exception('Firmware ID seems to be the wrong length. Found %d bytes, expected %d bytes' % (len(project_firmware_id), len(firmware_id.PLACEHOLDER)))

    def validate_metadata(self):
        if 'project-name' not in self.metadata or not self.metadata['project-name']:
            logging.warning('No project name defined in %s' % self.metadata_filename)

        if 'version' not in self.metadata or not self.metadata['version'] :
            logging.warning('No version defined in %s' % self.metadata_filename)

        if 'author' not in self.metadata or not self.metadata['author']:
            logging.warning('No author defined in %s' % self.metadata_filename)
