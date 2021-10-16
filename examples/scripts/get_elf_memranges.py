from elftools.elf.elffile import ELFFile
import sys

sections = ['.text', '.data', '.bss', '.rodata']

if len(sys.argv) < 2:
    raise Exception('Missing filename')
    
with open(sys.argv[1], 'rb') as f:
    ef = ELFFile(f)

    for section_name in sections:
        section = ef.get_section_by_name(section_name)
        if section is not None:
            print('%s %s ' % (section.header['sh_addr'], section.header['sh_size']), end ="")