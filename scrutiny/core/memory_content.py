#    memory_content.py
#        Provide a tool to manipulate non contiguous chunks of bytes with their addresses.
#        Represent a partial memory snapshot
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import re
from bisect import bisect, bisect_left
from typing import Dict, List, Union, Optional
import copy


class Cluster:
    """
    Represent a chunk of data with a location in memory.
    """
    __slots__ = 'start_addr', 'size', 'internal_data', 'has_data'

    start_addr: int
    size: int
    internal_data: Optional[bytearray]
    has_data: bool

    @property
    def data(self) -> bytearray:
        return self.read(0, self.size)

    def __init__(self, start_addr: int, size: int = 0, has_data: bool = True, data: Union[bytes, bytearray] = bytearray()) -> None:
        self.start_addr = start_addr
        self.size = size
        self.has_data = has_data
        if has_data:
            self.internal_data = bytearray(data)
        else:
            self.internal_data = None

    def read(self, offset: int, size: int) -> bytearray:
        if size < 0:
            raise ValueError('Cannot read a negative size')

        if offset < 0:
            raise IndexError('Offset cannot be negative %d' % offset)

        if offset + size > self.size:
            raise IndexError('Index out of range %d to %d' % (offset, offset + size))

        if self.has_data:
            assert self.internal_data is not None
            data_out = data_out = self.internal_data[offset:offset + size]
            if isinstance(data_out, int):
                data_out = bytearray([data_out])
        else:
            data_out = bytearray(b'\x00' * size)

        return data_out

    def write(self, data: Union[bytearray, bytes], offset: int = 0) -> None:
        if offset < 0:
            raise ValueError('Offset cannot be negative %d' % offset)

        if self.size - offset < len(data):
            raise Exception('Data too long for cluster')

        if self.has_data:
            assert self.internal_data is not None
            self.internal_data[offset:offset + len(data)] = data

    def shrink(self, new_size: int) -> None:
        self.size = new_size
        if self.has_data:
            assert self.internal_data is not None
            self.internal_data = self.internal_data[0:new_size]

    def extend(self, new_size: int, delta_data: Optional[Union[bytearray, bytes]] = None) -> None:
        delta_size = new_size - self.size
        if delta_size < 0:
            raise Exception('Cannot shrink cluster with extend() method')

        if self.has_data and delta_data is None:
            raise Exception('Missing data to extend cluster')

        if self.has_data:
            assert self.internal_data is not None
            if delta_data is None:
                delta_data = b'\x00' * delta_size

            if len(delta_data) != delta_size:
                raise Exception('Given data size does not match size fo given data')

            self.internal_data += delta_data
            self.size = new_size
        else:
            self.size = new_size
            # Discard data on purpose

    def __repr__(self) -> str:
        if self.has_data and self.internal_data is not None:
            data_string = '%d bytes of data' % len(self.internal_data)
        else:
            data_string = 'No Data'

        return '<Cluster: 0x%08X (size=0x%04x) - %s>' % (self.start_addr, self.size, data_string)

    def __len__(self) -> int:
        return self.size

    def __add__(self, other: "Cluster") -> "Cluster":
        new_cluster = copy.copy(self)
        if isinstance(other, bytes) or isinstance(other, bytearray):
            new_cluster.extend(new_cluster.size + len(other), delta_data=other)
        elif isinstance(other, Cluster):
            new_cluster.extend(self.size + other.size, delta_data=other.data)
        else:
            raise ValueError('Cannot add %s with %s' % (self.__class__.__name__, other.__class__.__name__))

        return new_cluster

    def __getitem__(self, key: Union[slice, int]) -> bytearray:
        if isinstance(key, slice):
            stop = key.stop
            if key.stop is None:
                stop = self.size
            if stop < 0:
                stop = self.size + stop
            read_size = stop - key.start
            offset = key.start
        else:
            offset = key
            read_size = 1

        return self.read(offset, read_size)


class MemoryContent:
    """
    MemoryContent creates a representation of a memory content. 
    It keeps many non-contiguous memory chunk with data. 
    Basic operation such as read,write, delete are possible.  

    All chunks of data that are contiguous are automatically agglomerated 
    into a single chunk

    We will use the agglomeration feature of this class to converts
    sparse subscription into a several contiguous read request for 
    communication optimization (avoid polling each variable individually).
    """

    clusters: Dict[int, Cluster]
    sorted_keys: List[int]          # Need 2 object to use bisect before python 3.10

    def __init__(self, filename: Optional[str] = None, retain_data: bool = True) -> None:
        self.clusters = {}
        self.sorted_keys = []
        self.retain_data = retain_data
        if filename is not None:
            self.load(filename)

    def load(self, filename: str) -> None:
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
                m = line_regex.match(line.strip())
                if m:
                    addr = int(m.group(1), 16)

                    if self.retain_data:
                        data = bytearray(bytes.fromhex(m.group(2)))
                        cluster = Cluster(start_addr=addr, size=len(data), data=data, has_data=True)
                    else:
                        size = len(m.group(2)) / 2
                        if size % 2 != 0:
                            raise Exception('Odd number of character')
                        size = int(size)
                        cluster = Cluster(start_addr=addr, size=size, has_data=False)

                    self.write_cluster(cluster)

    def read(self, addr: int, length: int) -> bytes:
        """
        Returns the data located at the address.
        Will raise an exception if no data exist in the section read
        """

        x = bisect(self.sorted_keys, addr)
        if x <= 0:
            raise ValueError('Address 0x%08x out of range' % (addr))

        addr_start = self.sorted_keys[x - 1]
        offset = addr - addr_start

        return self.clusters[addr_start].read(offset, length)

    def write(self, addr: int, data: Union[bytearray, bytes]) -> None:
        cluster = Cluster(start_addr=addr, size=len(data), data=data, has_data=self.retain_data)
        self.write_cluster(cluster)

    def write_cluster(self, cluster: Cluster) -> None:
        """
        Write data at a specific address.
        Can be read later on.
        """
        self.delete(cluster.start_addr, len(cluster))
        key_index = bisect(self.sorted_keys, cluster.start_addr)
        self.sorted_keys.insert(key_index, cluster.start_addr)
        self.clusters[cluster.start_addr] = cluster
        self.agglomerate(written_key_index=key_index)  # Giving written_key_index will limit the scope of the agglomeration for speed optimization

    def add_empty(self, addr: int, size: int) -> None:
        """
        Writes 0 bytes where requested.
        """
        if self.retain_data == True:
            data = b'\x00' * size
        else:
            data = b''

        cluster = Cluster(start_addr=addr, size=size, data=data, has_data=self.retain_data)
        self.write_cluster(cluster)

    def get_cluster_count(self) -> int:
        return len(self.clusters)

    def get_cluster_list_no_data_by_address(self) -> List[Cluster]:
        """
        Return a list of contiguous memory chunk that have data written.
        Each entry of the list is a Cluster object which have a start address and a length.
        Clusters are sorted by address.
        """
        cluster_list = [Cluster(start_addr=addr, size=len(self.clusters[addr]), has_data=False) for addr in self.clusters]
        cluster_list.sort(key=lambda x: x.start_addr)
        return cluster_list

    def get_cluster_list_no_data_by_size_desc(self) -> List[Cluster]:
        """
        Return a list of contiguous memory chunk that have data written.
        Each entry of the list is a Cluster object which have a start address and a length.
        Clusters are sorted by size.
        """
        cluster_list = [Cluster(start_addr=addr, size=len(self.clusters[addr]), has_data=False) for addr in self.clusters]
        cluster_list.sort(key=lambda x: x.size, reverse=True)
        return cluster_list

    def delete(self, addr: int, size: int) -> None:
        if size <= 0:
            return

        while True:
            if len(self.sorted_keys) == 0:
                break

            index = max(0, bisect(self.sorted_keys, addr) - 1)

            block_start = self.sorted_keys[index]
            block_end = block_start + len(self.clusters[block_start]) - 1

            if addr + size - 1 < block_start:    # out of bounds
                break

            start_in_block = addr <= block_end

            if not start_in_block:
                if index >= len(self.sorted_keys) - 1:    # Last block
                    break

            if start_in_block:
                cluster_to_edit_key = index
            else:
                if addr + size - 1 >= self.sorted_keys[index + 1]:    # Touches next block
                    cluster_to_edit_key = index + 1
                else:
                    break

            cluster_addr = self.sorted_keys[cluster_to_edit_key]
            cluster_len = len(self.clusters[cluster_addr])
            cluster_end = cluster_addr + cluster_len - 1

            to_delete_start = max(cluster_addr, addr)
            to_delete_end = min(cluster_end, addr + size - 1)

            # 4 types of deletion. Within the block. Around block. Partially in block (begin and end)
            if to_delete_start <= cluster_addr:
                if to_delete_end >= cluster_end:    # Around the block
                    del self.clusters[cluster_addr]
                    del self.sorted_keys[cluster_to_edit_key]
                else:
                    new_start_addr = to_delete_end + 1    # Partially in the block - begin
                    new_data_start_offset = size - (to_delete_start - addr)
                    new_size = len(self.clusters[cluster_addr]) - new_data_start_offset
                    new_cluster_data = self.clusters[cluster_addr][new_data_start_offset:]
                    del self.clusters[cluster_addr]
                    self.clusters[new_start_addr] = Cluster(start_addr=new_start_addr, size=new_size,
                                                            data=new_cluster_data, has_data=self.retain_data)
                    self.sorted_keys[cluster_to_edit_key] = new_start_addr
            else:
                if to_delete_end >= cluster_end:    # Partially in the block - end
                    new_size = to_delete_end - cluster_addr
                    self.clusters[cluster_addr].shrink(new_size)
                else:   # Within the block
                    new_chunk_start = to_delete_end + 1
                    new_chunk_offset = to_delete_end - cluster_addr + 1
                    new_chunk_size = cluster_end - to_delete_end
                    new_chunk_data = self.clusters[cluster_addr].read(new_chunk_offset, new_chunk_size)

                    new_size = to_delete_start - cluster_addr
                    self.clusters[cluster_addr].shrink(new_size)

                    self.sorted_keys.insert(cluster_to_edit_key + 1, new_chunk_start)
                    self.clusters[new_chunk_start] = Cluster(start_addr=new_chunk_start, size=new_chunk_size,
                                                             data=new_chunk_data, has_data=self.retain_data)

    def agglomerate(self, written_key_index: Optional[int] = None) -> None:
        if written_key_index is None:
            i = 0
        else:
            # Speed optimization if we know the range that might need agglomeration
            i = max(0, written_key_index - 1)

        merge_done = 0
        while i < len(self.sorted_keys):
            start_addr1 = self.sorted_keys[i]
            size1 = len(self.clusters[start_addr1])

            if i < len(self.sorted_keys) - 1:
                start_addr2 = self.sorted_keys[i + 1]
                size2 = len(self.clusters[start_addr2])

                if start_addr1 + size1 >= start_addr2:    # Need to agglomerate
                    new_size = size1 + size2
                    self.clusters[start_addr1] += self.clusters[start_addr2]
                    del self.clusters[start_addr2]
                    del self.sorted_keys[i + 1]
                    merge_done += 1

                    # If we just have written in a single block, we can assume that only 2
                    # blocks can be agglomerated (before and after). Speed up processing
                    if written_key_index is not None and merge_done >= 2:
                        break
                    # i stays the same. We reduced the array size instead.
                else:
                    i += 1
            else:
                i += 1
