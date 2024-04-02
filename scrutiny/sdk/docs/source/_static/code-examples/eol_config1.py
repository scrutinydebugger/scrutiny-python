from scrutiny.sdk.client import ScrutinyClient

hostname = 'localhost'
port = 1234
client = ScrutinyClient()
with client.connect(hostname, port, wait_status=True):    # Establish a websocket connection and wait for a first server status update
    client.wait_device_ready(timeout=5)
    
    # The following watch uses "aliases". For HIL testing, it is a good practice to keep 
    # the interface to the firmware abstracted to ensure the validity of this script across version of firmwares.
    # Aliases are defined in the SFD, the byproduct of the SCrutiny post-build toolchain.

    eeprom_config_size  = client.watch('/alias/eeprom_configurator/size')   # Maps to /var/global/eeprom_configurator/m_size
    eeprom_config_addr  = client.watch('/alias/eeprom_configurator/addr')   # Maps to /var/global/eeprom_configurator/m_addr
    eeprom_config_cmd   = client.watch('/alias/eeprom_configurator/cmd')    # Maps to /var/global/eeprom_configurator/m_cmd
    
    eeprom_config_return_code = client.watch('/alias/eeprom_configurator/return_code')      # Maps to /var/global/eeprom_configurator/m_last_return_code
  
    assembly_header_model       = client.watch('/alias/eeprom_configurator/assembly_header/model')      # Maps to /var/global/eeprom_configurator/m_assembly_header/model
    assembly_header_version     = client.watch('/alias/eeprom_configurator/assembly_header/version')    # Maps to /var/global/eeprom_configurator/m_assembly_header/version
    assembly_header_revision    = client.watch('/alias/eeprom_configurator/assembly_header/revision')   # Maps to /var/global/eeprom_configurator/m_assembly_header/revision
    assembly_header_serial      = client.watch('/alias/eeprom_configurator/assembly_header/serial')     # Maps to /var/global/eeprom_configurator/m_assembly_header/serial

    client.wait_new_value_for_all()
    
    print("Writing the assembly information into the device EEPROM")

    with client.batch_write():
        # Order of write is respected. Block until completion at exit of "with" block
        assembly_header_model.value = 1
        assembly_header_version.value = 2
        assembly_header_revision.value = 3
        assembly_header_serial.value = 0x12345678
        eeprom_config_addr.value = 0
        eeprom_config_cmd.value = 3     # WriteAssemblyHeader  
        # eeprom_config_cmd.value = 'WriteAssemblyHeader'   # With enum support

    eeprom_config_cmd.wait_value(0, timeout=5)  # The device will set this back to None once finished      
    # eeprom_config_cmd.wait_value('None', timeout=2)   # With enum support

    # Request the server for an update. Make sure we do not read an old value
    # We have no control on the order in which the values a polled by the server.
    eeprom_config_return_code.force_refresh() 

    assert eeprom_config_return_code.value_int == 0, "Write operation failed"

    print("Successfully written")
