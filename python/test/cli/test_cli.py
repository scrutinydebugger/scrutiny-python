import os
import unittest
import tempfile
import json
import platform
import scrutiny
import datetime

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
