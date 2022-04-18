#    test_cli.py
#        Test the Command Line Interface
#
#   - License : MIT - See LICENSE file.
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny)
#
#   Copyright (c) 2021-2022 scrutinydebugger

import os
import unittest
import tempfile
import json
import platform
import scrutiny
import datetime
import shutil
from io import StringIO
import sys
from scrutiny.core.varmap import VarMap
from scrutiny.core.sfi_storage import SFIStorage
from test.artifacts import get_artifact

from scrutiny.cli import CLI


class RedirectStdout:
    def __enter__(self):
        self.old_stdout = sys.stdout
        sys.stdout = self.mystdout = StringIO()
        return self

    def __exit__(self, *args):
        sys.stdout = self.old_stdout

    def read(self):
        return self.mystdout.getvalue()


class TestCLI(unittest.TestCase):

    # Generate some metadata file from command line in temp folder and make sure its content is good
    def test_make_metadata(self):
        with tempfile.TemporaryDirectory() as tempdirname:
            cli = CLI()
            filename = os.path.join(tempdirname, 'testfile.json')
            cli.run(['make-metadata', '--version', '1.2.3.4', '--project-name', 'testname', '--author', 'unittest', '--output', filename])
            with open(filename, 'r') as f:
                metadata = json.loads(f.read())

        self.assertEqual(metadata['version'], '1.2.3.4')
        self.assertEqual(metadata['author'], 'unittest')
        self.assertEqual(metadata['project-name'], 'testname')

        self.assertEqual(metadata['generation-info']['scrutiny-version'], scrutiny.__version__)
        self.assertEqual(metadata['generation-info']['system-type'], platform.system())
        self.assertEqual(metadata['generation-info']['python-version'], platform.python_version())
        self.assertGreater(metadata['generation-info']['time'], datetime.datetime.now().timestamp() - 5)
        self.assertLess(metadata['generation-info']['time'], datetime.datetime.now().timestamp() + 5)

        with tempfile.TemporaryDirectory() as tempdirname:
            cli = CLI(tempdirname)
            filename = os.path.join(tempdirname, 'metadata.json')   # default name
            cli.run(['make-metadata', '--version', '1.2.3.4', '--project-name', 'testname', '--author', 'unittest'])
            with open(filename, 'r') as f:
                metadata = json.loads(f.read())

        self.assertEqual(metadata['version'], '1.2.3.4')
        self.assertEqual(metadata['author'], 'unittest')
        self.assertEqual(metadata['project-name'], 'testname')

    # Extract firmware id from demo binary file and validate the behaviour of the CLI
    def test_get_firmware_id(self):
        with tempfile.TemporaryDirectory() as tempdirname:
            cli = CLI()
            demo_bin = get_artifact('demobin.elf')
            with open(get_artifact('demobin_firmwareid')) as f:
                demobin_firmware_id = f.read()
            temp_bin = os.path.join(tempdirname, 'demobin.elf')
            shutil.copyfile(demo_bin, temp_bin)

            # Write firmware id to stdout and compare with reference
            with RedirectStdout() as stdout:
                cli.run(['get-firmware-id', temp_bin])
                firmwareid = stdout.read()
            self.assertEqual(firmwareid, demobin_firmware_id)

            # Write firmware id to file and compare with reference
            output_file = os.path.join(tempdirname, 'temp_firmwareid')
            cli.run(['get-firmware-id', temp_bin, '--output', output_file])  # Write firmware id to file
            with open(output_file) as f:
                outputted_firmwareid = f.read()
            self.assertEqual(outputted_firmwareid, demobin_firmware_id)

            # Write the firmware id to the demobin and catch its from stdout. Make sure file has changed
            with RedirectStdout() as stdout:
                with open(temp_bin, 'rb') as f:
                    tempbin_content = f.read()
                cli.run(['get-firmware-id', temp_bin, '--apply'])
                firmwareid = stdout.read()
            with open(temp_bin, 'rb') as f:
                tempbin_modified_content = f.read()
            self.assertNotEqual(tempbin_modified_content, tempbin_content)
            self.assertEqual(firmwareid, demobin_firmware_id)

    # Read a demo firmware binary and make varmap file. We don't check the content, just that it is valid varmap.
    def test_elf2varmap(self):
        cli = CLI()
        demobin_path = get_artifact('demobin.elf')

        with RedirectStdout() as stdout:
            cli.run(['elf2varmap', demobin_path])
            VarMap(stdout.read())  # make sure the output is loadable. Don't check content, there's another test suite for that

        with tempfile.TemporaryDirectory() as tempdirname:
            outputfile = os.path.join(tempdirname, 'varmap.json')
            cli.run(['elf2varmap', demobin_path, '--output', outputfile])
            VarMap(outputfile)  # make sure the output is loadable. Don't check content, there's another test suite for that

    # Test all commands related to manipulating Scrutiny Firmware Info
    def test_make_sfi_and_install(self):
        with tempfile.TemporaryDirectory() as tempdirname:
            cli = CLI()
            demo_bin = get_artifact('demobin.elf')
            temp_bin = os.path.join(tempdirname, 'demobin.elf')
            sfi_name = os.path.join(tempdirname, 'myfile.sfi')
            shutil.copyfile(demo_bin, temp_bin)

            with open(get_artifact('demobin_firmwareid')) as f:
                demobin_firmware_id = f.read()

            cli.run(['make-metadata', '--version', '1.2.3.4', '--project-name', 'testname', '--author', 'unittest', '--output', tempdirname])
            cli.run(['get-firmware-id', temp_bin, '--output', tempdirname, '--apply'])
            cli.run(['elf2varmap', temp_bin, '--output', tempdirname])
            cli.run(['uninstall-firmware-info', demobin_firmware_id, '--quiet'])
            self.assertFalse(SFIStorage.is_installed(demobin_firmware_id))

            cli.run(['make-firmware-info', tempdirname, sfi_name, '--install'])     # install while making
            self.assertTrue(SFIStorage.is_installed(demobin_firmware_id))
            cli.run(['uninstall-firmware-info', demobin_firmware_id, '--quiet'])    # uninstall
            self.assertFalse(SFIStorage.is_installed(demobin_firmware_id))
            cli.run(['install-firmware-info', sfi_name])                            # install with dedicated command
            self.assertTrue(SFIStorage.is_installed(demobin_firmware_id))
            sfi = SFIStorage.get(demobin_firmware_id)
            self.assertEqual(sfi.get_firmware_id(ascii=True), demobin_firmware_id)  # Load and check id.

            cli.run(['uninstall-firmware-info', demobin_firmware_id, '--quiet'])    # cleanup
