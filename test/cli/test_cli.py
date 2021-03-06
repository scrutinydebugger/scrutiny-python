#    test_cli.py
#        Test the Command Line Interface
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2022 Scrutiny Debugger

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
from scrutiny.core.sfd_storage import SFDStorage
from test.artifacts import get_artifact
from test import SkipOnException
from scrutiny.cli import CLI
from scrutiny.exceptions import EnvionmentNotSetUpException


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
            cli.run(['make-metadata', '--version', '1.2.3.4', '--project-name', 'testname',
                    '--author', 'unittest', '--output', filename], except_failed=True)
            with open(filename, 'r') as f:
                metadata = json.loads(f.read())

        self.assertEqual(metadata['version'], '1.2.3.4')
        self.assertEqual(metadata['author'], 'unittest')
        self.assertEqual(metadata['project_name'], 'testname')

        self.assertEqual(metadata['generation_info']['scrutiny_version'], scrutiny.__version__)
        self.assertEqual(metadata['generation_info']['system_type'], platform.system())
        self.assertEqual(metadata['generation_info']['python_version'], platform.python_version())
        self.assertGreater(metadata['generation_info']['time'], datetime.datetime.now().timestamp() - 5)
        self.assertLess(metadata['generation_info']['time'], datetime.datetime.now().timestamp() + 5)

        with tempfile.TemporaryDirectory() as tempdirname:
            cli = CLI(tempdirname)
            filename = os.path.join(tempdirname, 'metadata.json')   # default name
            cli.run(['make-metadata', '--version', '1.2.3.4', '--project-name', 'testname', '--author', 'unittest'], except_failed=True)
            with open(filename, 'r') as f:
                metadata = json.loads(f.read())

        self.assertEqual(metadata['version'], '1.2.3.4')
        self.assertEqual(metadata['author'], 'unittest')
        self.assertEqual(metadata['project_name'], 'testname')

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
                cli.run(['get-firmware-id', temp_bin], except_failed=True)
                firmwareid = stdout.read()
            self.assertEqual(firmwareid, demobin_firmware_id)

            # Write firmware id to file and compare with reference
            output_file = os.path.join(tempdirname, 'temp_firmwareid')
            cli.run(['get-firmware-id', temp_bin, '--output', output_file], except_failed=True)  # Write firmware id to file
            with open(output_file) as f:
                outputted_firmwareid = f.read()
            self.assertEqual(outputted_firmwareid, demobin_firmware_id)

            # Write the firmware id to the demobin and catch its from stdout. Make sure file has changed
            with RedirectStdout() as stdout:
                with open(temp_bin, 'rb') as f:
                    tempbin_content = f.read()
                cli.run(['get-firmware-id', temp_bin, '--apply'], except_failed=True)
                firmwareid = stdout.read()
            with open(temp_bin, 'rb') as f:
                tempbin_modified_content = f.read()
            self.assertNotEqual(tempbin_modified_content, tempbin_content)
            self.assertEqual(firmwareid, demobin_firmware_id)

    # Read a demo firmware binary and make varmap file. We don't check the content, just that it is valid varmap.
    @SkipOnException(EnvionmentNotSetUpException)
    def test_elf2varmap(self):
        cli = CLI()
        demobin_path = get_artifact('demobin.elf')

        with RedirectStdout() as stdout:
            cli.run(['elf2varmap', demobin_path], except_failed=True)
            VarMap(stdout.read())  # make sure the output is loadable. Don't check content, there's another test suite for that

        with tempfile.TemporaryDirectory() as tempdirname:
            outputfile = os.path.join(tempdirname, 'varmap.json')
            cli.run(['elf2varmap', demobin_path, '--output', outputfile], except_failed=True)
            VarMap(outputfile)  # make sure the output is loadable. Don't check content, there's another test suite for that

    # Test all commands related to manipulating Scrutiny Firmware Description
    @SkipOnException(EnvionmentNotSetUpException)
    def test_make_sfd_and_install(self):
        with tempfile.TemporaryDirectory() as tempdirname:
            with SFDStorage.use_temp_folder():
                cli = CLI()
                demo_bin = get_artifact('demobin.elf')
                temp_bin = os.path.join(tempdirname, 'demobin.elf')
                sfd_name = os.path.join(tempdirname, 'myfile.sfd')
                shutil.copyfile(demo_bin, temp_bin)

                with open(get_artifact('demobin_firmwareid')) as f:
                    demobin_firmware_id = f.read()

                cli.run(['make-metadata', '--version', '1.2.3.4', '--project-name', 'testname',
                        '--author', 'unittest', '--output', tempdirname], except_failed=True)
                cli.run(['get-firmware-id', temp_bin, '--output', tempdirname, '--apply'], except_failed=True)
                cli.run(['elf2varmap', temp_bin, '--output', tempdirname], except_failed=True)
                cli.run(['uninstall-sfd', demobin_firmware_id, '--quiet'], except_failed=True)
                self.assertFalse(SFDStorage.is_installed(demobin_firmware_id))

                cli.run(['make-sfd', tempdirname, sfd_name, '--install'], except_failed=True)     # install while making
                self.assertTrue(SFDStorage.is_installed(demobin_firmware_id))
                cli.run(['uninstall-sfd', demobin_firmware_id, '--quiet'], except_failed=True)    # uninstall
                self.assertFalse(SFDStorage.is_installed(demobin_firmware_id))
                cli.run(['install-sfd', sfd_name], except_failed=True)                            # install with dedicated command
                self.assertTrue(SFDStorage.is_installed(demobin_firmware_id))
                sfd = SFDStorage.get(demobin_firmware_id)
                self.assertEqual(sfd.get_firmware_id(ascii=True), demobin_firmware_id)  # Load and check id.
                cli.run(['uninstall-sfd', demobin_firmware_id, '--quiet'], except_failed=True)    # cleanup

    def test_list_sfd(self):
        cli = CLI()
        sfd1_filename = get_artifact('test_sfd_1.sfd')
        sfd2_filename = get_artifact('test_sfd_2.sfd')

        with SFDStorage.use_temp_folder():
            sfd1 = SFDStorage.install(sfd1_filename, ignore_exist=True)
            sfd2 = SFDStorage.install(sfd2_filename, ignore_exist=True)

            with RedirectStdout() as stdout:
                cli.run(['list-sfd'])  # Make sure no exception is raised
                nbline = stdout.read().count('\n')
                self.assertGreaterEqual(nbline, 3)  # 2 SFD + total number

            SFDStorage.uninstall(sfd1.get_firmware_id())
            SFDStorage.uninstall(sfd2.get_firmware_id())
