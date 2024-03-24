#    get_var_memrange.py
#        Simple tool to get the memory ranges of the .elf sections that contains the variables.
#        Used to generate Memdumps for unit testing
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from elftools.elf.elffile import ELFFile
from scrutiny.core.bintools import elftools_stubs

import sys

sections = ['.data', '.bss', '.rodata']

with open(sys.argv[1], 'rb') as f:
    ef = ELFFile(f)

    for section_name in sections:
        section = ef.get_section_by_name(section_name)
        if section is not None:
            print('%s %s ' % (section.header['sh_addr'], section.header['sh_size']), end="")
