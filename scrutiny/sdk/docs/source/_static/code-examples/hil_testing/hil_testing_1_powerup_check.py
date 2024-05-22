from scrutiny.sdk.client import ScrutinyClient

hostname = 'localhost'
port = 1234
client = ScrutinyClient()
with client.connect(hostname, port, wait_status=True):    # Establish a websocket connection and wait for a first server status update
    client.wait_device_ready(timeout=5)
    
    # The following watch uses "aliases". For HIL testing, it is a good practice to keep 
    # the interface to the firmware abstracted to ensure the validity of this script across version of firmwares.
    # Aliases are defined in the SFD, the byproduct of the SCrutiny post-build toolchain.

    run_app = client.watch('/alias/app/run_app')                    # Maps to /var/static/main.cpp/run_app
    psu_state = client.watch('/alias/power_supply/state')           # Maps to /var/global/power_supply/m_actual_state
    psu_last_state = client.watch('/alias/power_supply/last_state') # Maps to /var/global/power_supply/m_last_state

    io_psu_ready = client.watch('/alias/ios/inputs/psu_ready')      # Maps to /var/global/inputs_outputs/in/psu_ready
    io_submodule1_ready = client.watch('/alias/ios/inputs/submodule1_ready')    # Maps to /var/global/inputs_outputs/in/submodule1_ready
    io_psu_voltage_line1 = client.watch('/alias/ios/inputs/psu_voltage_line1')  # Maps to /var/global/inputs_outputs/in/psu_voltage_line1
    io_psu_voltage_line2 = client.watch('/alias/ios/inputs/psu_voltage_line2')  # Maps to /var/global/inputs_outputs/in/psu_voltage_line2

    client.wait_new_value_for_all()
    
    # Start of test sequence
    assert io_psu_ready.value_bool == False
    assert io_submodule1_ready.value_bool == False
    assert io_psu_voltage_line1.value_float < 0.5
    assert io_psu_voltage_line2.value_float < 0.5

    run_app.value = True

    psu_state.wait_value('DONE_OK', timeout=2) # string are passed as enum, will convert to a value of 0
    assert io_psu_ready.value_bool == True
    assert io_submodule1_ready.value_bool == True
    assert io_psu_voltage_line1.value_float > 4.75
    assert io_psu_voltage_line2.value_float > 11.5

    print("Test passed")
