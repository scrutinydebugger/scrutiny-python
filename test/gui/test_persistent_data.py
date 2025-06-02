#    test_persistent_data.py
#        A test suite that tests the GUI persistent data mechanisms
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

from test.gui.base_gui_test import ScrutinyBaseGuiTest
from scrutiny.gui.core.persistent_data import AppPersistentDataManager, AppPersistentDataManager
from tempfile import TemporaryDirectory
from pathlib import Path
import json


class TestGuiPreferences(ScrutinyBaseGuiTest):
    def test_save_load(self):
        with TemporaryDirectory() as d:
            manager = AppPersistentDataManager(Path(d))
            xxx = manager.get_namespace('XXX')
            yyy = manager.get_namespace('YYY')

            xxx.set_bool('xxx_keybool', True)
            xxx.set_int('xxx_keyint', 123)
            xxx.set_float('xxx_keyfloat', 3.14159)

            xxx.set_str('xxx_keystr', "hello")

            yyy.set_bool('yyy_keybool', False)
            yyy.set_int('yyy_keyint', 2222)
            yyy.set_float('yyy_keyfloat', 1.2)
            yyy.set_str('yyy_keystr', "hello2")

            manager.save()

            manager2 = AppPersistentDataManager(Path(d))
            xxx = manager2.get_namespace('XXX')
            yyy = manager2.get_namespace('YYY')

            v = xxx.get_bool('xxx_keybool', default=False)
            self.assertIsInstance(v, bool)
            self.assertEqual(v, True)

            v = xxx.get_int('xxx_keyint', default=1)
            self.assertIsInstance(v, int)
            self.assertEqual(v, 123)

            v = xxx.get_float('xxx_keyfloat', default=2.2)
            self.assertIsInstance(v, float)
            self.assertEqual(v, 3.14159)

            v = xxx.get_str('xxx_keystr', default="")
            self.assertIsInstance(v, str)
            self.assertEqual(v, "hello")

            v = yyy.get_bool('yyy_keybool', default=True)
            self.assertIsInstance(v, bool)
            self.assertEqual(v, False)

            v = yyy.get_int('yyy_keyint', default=1)
            self.assertIsInstance(v, int)
            self.assertEqual(v, 2222)

            v = yyy.get_float('yyy_keyfloat', default=2.1)
            self.assertIsInstance(v, float)
            self.assertEqual(v, 1.2)

            v = yyy.get_str('yyy_keystr', default="")
            self.assertIsInstance(v, str)
            self.assertEqual(v, "hello2")

    def test_bad_values(self):
        class TestClass:
            pass
        obj = TestClass()
        with TemporaryDirectory() as d:
            manager = AppPersistentDataManager(Path(d))

            for v in [2, None, 'asd', 3.14, obj]:
                with self.assertRaises(TypeError, msg=f"v={v}"):
                    manager.global_namespace().set_bool('boolval', v)

            for v in [None, 'asd', True, obj]:
                with self.assertRaises(TypeError, msg=f"v={v}"):
                    manager.global_namespace().set_float('floatval', v)

            for v in [None, True, 'asd', 3.14, obj]:
                with self.assertRaises(TypeError, msg=f"v={v}"):
                    manager.global_namespace().set_int('aaa', v)

            for v in [2, None, True, 3.14, obj]:
                with self.assertRaises(TypeError, msg=f"v={v}"):
                    manager.global_namespace().set_str('aaa', v)

    def test_clear_on_corrupted(self):
        with TemporaryDirectory() as d:
            manager = AppPersistentDataManager(Path(d))
            manager.global_namespace().set("asdasd", "hello")
            self.assertEqual(manager.global_namespace().get('asdasd'), 'hello')
            manager.save()

            with open(manager.get_storage_file(), 'w') as f:
                f.write("I am not json")

            manager2 = AppPersistentDataManager(Path(d))
            self.assertIsNone(manager2.global_namespace().get('asdasd'))

    def test_clear_empty_namespaces(self):
        with TemporaryDirectory() as d:
            manager = AppPersistentDataManager(Path(d))
            manager.get_namespace("asd")
            manager.save()

            with open(manager.get_storage_file(), 'r') as f:
                raw_json = json.load(f)

            self.assertNotIn('asd', raw_json)
