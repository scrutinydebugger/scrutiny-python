from scrutiny.sdk.client import ScrutinyClient
from scrutiny.sdk.watchable_handle import WatchableHandle
import io
import argparse

EEPROM_SIZE=4096    # Could come from a variable inside the eeprom driver.

# This class could be in a different file
class EepromConfiguration:
    client:ScrutinyClient
    size:WatchableHandle
    addr:WatchableHandle
    cmd:WatchableHandle
    return_code:WatchableHandle
    buffer_size:WatchableHandle

    def __init__(self, client:ScrutinyClient):
        self.client = client
        self.size  = client.watch('/alias/eeprom_configurator/size')   # Maps to /var/global/eeprom_configurator/m_size
        self.addr  = client.watch('/alias/eeprom_configurator/addr')   # Maps to /var/global/eeprom_configurator/m_addr
        self.cmd   = client.watch('/alias/eeprom_configurator/cmd')    # Maps to /var/global/eeprom_configurator/m_cmd
        self.return_code = client.watch('/alias/eeprom_configurator/return_code')      # Maps to /var/global/eeprom_configurator/m_last_return_code
        self.buffer = client.watch('/alias/eeprom_configurator/buffer')      # Maps to /var/global/eeprom_configurator/m_buffer
        self.buffer_size = client.watch('/alias/eeprom_configurator/buffer_size')      # Maps to /var/global/eeprom_configurator/m_buffer_size

        self.client.wait_new_value_for_all()


    def dump_eeprom(self, f:io.BufferedWriter) -> None:
        bufsize = self.buffer_size.value_int
        cursor=0
        while cursor < EEPROM_SIZE:
            size_to_read = min(bufsize, EEPROM_SIZE-cursor)
            with self.client.batch_write():
                self.addr.value = cursor
                self.value = size_to_read
                self.cmd.value_enum='Read'   # strings = enum value
            
            self.cmd.wait_value(0, timeout=5)   # self.cmd.wait_value('None', timeout=5)
            self.return_code.wait_update(timeout=3)

            if self.return_code.value_int != 0:
                raise RuntimeError(f"Failed to read the EEPROM data at addr={cursor} with size={size_to_read}")

            # self.buffer is a pointer, its value contains a memory address
            data = self.client.read_memory(self.buffer.value_int, size_to_read, timeout=5)  # Reads the content of the buffer
            f.write(data)
            cursor+=size_to_read

    

# dump_eeprom.py
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('filename', help="The output file")
    parser.add_argument('--host', default='localhost', help="The output file")
    parser.add_argument('--port', type=int, default=1234, help="The output file")
    args = parser.parse_args()
    client = ScrutinyClient()
    with client.connect(args.hostname, args.port, wait_status=True):    # Establish a connection and wait for a first server status update
        client.wait_device_ready(timeout=5)
        configurator = EepromConfiguration(client)
        
        with open(args.filename, 'wb') as f:
            configurator.dump_eeprom(f)
            print(f"Successfully dumped the device EEPROM content to {args.filename} ")


if __name__ == '__main__':
    main()
