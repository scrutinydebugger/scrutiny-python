import re
from bisect import bisect

class Memdump:

    def __init__(self, filename=None):
        self.memchunk = {}
        self.sorted_keys = []
        if filename is not None:
            self.load(filename)

    def load(self, filename):
        """
        Load a memdump file formatted this way

        0x00401060:    31ED4989D15E4889E24883E4F0505449
        0x00401070:    C7C0E017400048C7C18017400048C7C7
        0x00401080:    57164000FF15662F0000F40F1F440000
        0x00401090:    C3662E0F1F8400000000000F1F440000
        0x004010A0:    B870404000483D704040007413B80000
        0x004010B0:    00004885C07409BF70404000FFE06690
        """
        line_regex = re.compile(r'0x([0-9a-fA-F]+)\s*:\s*([0-9a-fA-F]+)')
        with open(filename, 'r') as f:
            lines = f.readlines()
            for line in lines:
                m = line_regex.match(line)
                if m:
                    addr = int(m.group(1), 16)
                    data = bytes.fromhex(m.group(2))

                    x = bisect(self.sorted_keys, addr)

                    if x > 0: 
                        start_addr = self.sorted_keys[x-1]
                        if start_addr + len(self.memchunk[start_addr]) == addr:
                            self.memchunk[start_addr] += data
                        else:
                            self.memchunk[addr] = data
                            self.sorted_keys.insert(x, addr) 
                    else:
                        self.memchunk[addr] = data
                        self.sorted_keys.insert(x, addr)



    def read(self, addr, length):
        
        x = bisect(self.sorted_keys, addr)
        if x <= 0:
            raise ValueError('Address out of range')

        addr_start = self.sorted_keys[x-1]
        offset = addr-addr_start

        if offset + length >  len(self.memchunk[addr_start]):
            raise ValueError('Length too long')

        return self.memchunk[addr_start][offset:offset+length]

    def write(self, addr, data):
        keys = list(self.memchunk.keys())
        x = bisect(self.sorted_keys, addr)
        self.sorted_keys.insert(x,addr)
        self.memchunk[addr] = data
        self.agglomerate(addr)

    def agglomerate(self, last_written=None):
        done = False
        while not done:
            done = True
            keys = self.sorted_keys
            for i in range(len(keys)):
                if i < len(keys)-1:
                    if keys[i] + len(self.memchunk[keys[i]]) >= keys[i+1]-1:

                        if last_written is None or last_written not in [keys[i], keys[i+1]]:
                            raise Exception('Data consistency broken in region %x to %x' % (keys[i], keys[i+1]))

                        new_size = max(keys[i]+len(self.memchunk[keys[i]]), keys[i+1]+len(self.memchunk[keys[i+1]]), )
                        new_data = b'\x00'*new_size
                        diff_addr = keys[i+1]-keys[i]
                        addr1 = keys[i]
                        addr2 = keys[i+1]
                        data1 = self.memchunk[addr1]
                        data2 = self.memchunk[addr2]
                        size1 = len(data1)
                        size2 = len(data2)

                        if last_written == addr1:
                            new_data = data1
                            ntoadd = max(0, addr2+size2-addr1-size1)
                            new_data +=  data2[size2-ntoadd:]
                        else:
                            new_data = data2
                            new_data = data1[0: max(0, diff_addr)] + new_data
                            new_data += data1[diff_addr+size2:]

                        del self.memchunk[keys[i+1]]
                        del self.sorted_keys[i+1]
                        self.memchunk[keys[i]] = new_data
                        done = False
                        break
