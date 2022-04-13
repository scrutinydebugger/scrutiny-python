import argparse
from .base_command import BaseCommand
import scrutiny.core.firmware_id as firmware_id
import hashlib
import mmap
import os
import logging

class GetFirmwareId(BaseCommand):
    _cmd_name_ = 'get-firmware-id'
    _brief_ = 'Extract a unique hash from a binary firmware used for device identification.'
    _group_ = 'Build Toochain'

    DEFAULT_NAME = 'firmwareid'
    BUF_SIZE = 0x10000

    def __init__(self, args):
        self.args = args
        self.parser = argparse.ArgumentParser( prog = self.get_prog() )
        self.parser.add_argument('filename', help='The binary fimware to read')
        self.parser.add_argument('--output', default=None, help='The output path of the firmwareid file')
        self.parser.add_argument('--apply', action='store_true', help='When set, tag the firmware binary file with the new firmware-id hash by replacing the compiled placeholder.')

    def run(self):
        args = self.parser.parse_args(self.args)
        filename = os.path.normpath(args.filename)
        
        if args.output is None:
            output_file = None
        elif os.path.isdir(args.output):
            output_file = os.path.join(args.output, self.DEFAULT_NAME)
        else:
            output_file = args.output

        with open(filename,"rb") as f:  
            s = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            pos = s.find(firmware_id.PLACEHOLDER);
            if pos == -1:
                raise Exception("Binary file does not contains Scrutiny placeholder. Either it is already tagged or the file hasn't been compiled with a full scrutiny-lib")
            
            logging.debug('Found scrutiny placeholder at address 0x%08x' % pos)
            sha256 = hashlib.sha256()
            while True:
                data = f.read(self.BUF_SIZE)
                if not data:
                    break
                sha256.update(data)
            thehash = sha256.hexdigest()
            thehash_bin = bytes.fromhex(thehash)

        if output_file is None:
            print(thehash, flush=True, end='')
        else:
            with open(output_file, 'w') as f:
                f.write(thehash)

        if args.apply:
            with open(filename,"rb+") as f:
                f.seek(pos)
                f.write(thehash_bin)
                logging.debug('Wrote new hash %s at address 0x%08x' % (thehash, pos))



