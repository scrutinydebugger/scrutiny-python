import re
from bisect import bisect

class Memdump:
    """
    Allow to interract with a  memdump file in a format similar to

    0x00401060:    31ED4989D15E4889E24883E4F0505449
    0x00401070:    C7C0E017400048C7C18017400048C7C7
    0x00401080:    57164000FF15662F0000F40F1F440000
    0x00401090:    C3662E0F1F8400000000000F1F440000
    0x004010A0:    B870404000483D704040007413B80000
    0x004010B0:    00004885C07409BF70404000FFE06690
    """
    def __init__(self, filename):
        line_regex = re.compile(r'0x([0-9a-fA-F]+)\s*:\s*([0-9a-fA-F]+)')
        self.memchunk = {}
        self.keys = []

        with open(filename, 'r') as f:
            lines = f.readlines()
            for line in lines:
                m = line_regex.match(line)
                if m:
                    addr = int(m.group(1), 16)
                    data = bytes.fromhex(m.group(2))

                    x = bisect(self.keys, addr)

                    if x > 0: 
                        start_addr = self.keys[x-1]
                        if start_addr + len(self.memchunk[start_addr]) == addr:
                            self.memchunk[start_addr] += data
                        else:
                            self.keys.insert(x, addr)
                            self.memchunk[addr] = data
                    else:
                        self.keys.insert(x, addr)
                        self.memchunk[addr] = data

    def read(self, addr, length):
        x = bisect(self.keys, addr)
        if x <= 0:
            raise ValueError('Address out of range')

        addr_start = self.keys[x-1]
        offset = addr-addr_start

        if offset + length >  len(self.memchunk[addr_start]):
            raise ValueError('Length too long')

        return self.memchunk[addr_start][offset:offset+length]
