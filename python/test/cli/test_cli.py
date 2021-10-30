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

from scrutiny.cli import CLI

class TestCLI(unittest.TestCase):

    def test_make_metadata(self):
        with tempfile.TemporaryDirectory() as tempdirname:
            cli = CLI()
            filename = os.path.join(tempdirname, 'testfile.json')
            cli.run(['make-metadata', '--version', '1.2.3.4', '--project-name', 'testname', '--author', 'unittest', '--output', filename ])
            with open(filename, 'r') as f:
                metadata = json.loads(f.read())

        self.assertEqual(metadata['version'], '1.2.3.4')
        self.assertEqual(metadata['author'], 'unittest')
        self.assertEqual(metadata['project-name'], 'testname')

        self.assertEqual(metadata['generation-info']['scrutiny-version'], scrutiny.__version__)
        self.assertEqual(metadata['generation-info']['system-type'], platform.system())
        self.assertEqual(metadata['generation-info']['python-version'], platform.python_version())
        self.assertGreater(metadata['generation-info']['time'], datetime.datetime.now().timestamp()-5)
        self.assertLess(metadata['generation-info']['time'], datetime.datetime.now().timestamp()+5)


        with tempfile.TemporaryDirectory() as tempdirname:
            cli = CLI(tempdirname)
            filename = os.path.join(tempdirname, 'metadata.json')   # default name
            cli.run(['make-metadata', '--version', '1.2.3.4', '--project-name', 'testname', '--author', 'unittest' ])
            with open(filename, 'r') as f:
                metadata = json.loads(f.read())

        self.assertEqual(metadata['version'], '1.2.3.4')
        self.assertEqual(metadata['author'], 'unittest')
        self.assertEqual(metadata['project-name'], 'testname')

    def test_get_firmware_id(self):
        with tempfile.TemporaryDirectory() as tempdirname:
            cli = CLI()
            testsuite_path = os.path.dirname(__file__)
            demo_bin = os.path.join(testsuite_path, 'files', 'demobin.elf')
            with open(os.path.join(testsuite_path, 'files', 'demobin_firmwareid')) as f:
                demobin_firmware_id = f.read()
            temp_bin = os.path.join(tempdirname, 'demobin.elf')
            shutil.copyfile(demo_bin, temp_bin)

            # Write firmware id to stdout and compare with reference
            old_stdout = sys.stdout
            sys.stdout = mystdout = StringIO()
            cli.run(['get-firmware-id', temp_bin])  
            sys.stdout = old_stdout
            firmwareid = mystdout.getvalue()
            self.assertEqual(firmwareid, demobin_firmware_id)

            # Write firmware id to file and compare with reference
            output_file = os.path.join(tempdirname, 'temp_firmwareid')
            cli.run(['get-firmware-id', temp_bin, '--output', output_file])  # Write firmware id to file  
            with open(output_file) as f:
                outputted_firmwareid = f.read()
            self.assertEqual(outputted_firmwareid, demobin_firmware_id)

            # Write the firmware id to the demobin and catch its from stdout. Make sure file has changed
            old_stdout = sys.stdout
            sys.stdout = mystdout = StringIO()
            with open(temp_bin, 'rb') as f:
                tempbin_content = f.read()
            cli.run(['get-firmware-id', temp_bin, '--apply'])
            sys.stdout = old_stdout
            firmwareid = mystdout.getvalue()
            with open(temp_bin, 'rb') as f:
                tempbin_modified_content = f.read()
            self.assertNotEqual(tempbin_modified_content, tempbin_content)
            self.assertEqual(firmwareid, demobin_firmware_id)

            