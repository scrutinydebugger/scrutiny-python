#    test_elf_dwarf_var_extractor.py
#        Test the extraction of dwarf symbols from a .elf file
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2021 Scrutiny Debugger

import re
from test import ScrutinyUnitTest


class TestElf2VarMap(ScrutinyUnitTest):

    def test_unique_cu_name(self):
        from scrutiny.core.bintools.elf_dwarf_var_extractor import ElfDwarfVarExtractor
        unique_name_regex = re.compile(r'cu(\d+)_(.+)')

        a, b, c, d, e, f = object(), object(), object(), object(), object(), object()

        fullpath_cu_tuple_list = [
            ('/aaa/bbb/ccc', a),
            ('/aaa/bbb/ddd', b),
            ('/aaa/xxx/ccc', c),
            ('/aaa/bbb/ccc/ddd/x', d),
            ('/aaa/bbb/ccc/ddd/x', e),
            ('/ccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc/ddd/x', f)  # Name too long
        ]

        display_name_cu = ElfDwarfVarExtractor.make_unique_display_name(fullpath_cu_tuple_list)
        objmap = {}
        for item in display_name_cu:
            objmap[item[1]] = item[0]

       # self.assertEqual(objmap[a], 'bbb_ccc')
        self.assertEqual(objmap[c], 'xxx_ccc')
        self.assertEqual(objmap[b], 'ddd')
        self.assertTrue(unique_name_regex.match(objmap[d]))
        self.assertTrue(unique_name_regex.match(objmap[e]))
        self.assertTrue(unique_name_regex.match(objmap[f]))

        name_set = set()
        for obj in objmap:
            name = objmap[obj]
            self.assertNotIn(name, name_set, 'Duplicate name %s' % name)
            name_set.add(name)


if __name__ == '__main__':
    import unittest
    unittest.main()
