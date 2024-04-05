Scrutiny Firmware Description (SFD)
===================================

A Scrutiny Firmware Description (SFD) is a file that's generated during the firmware's build phase for embedded systems. This file includes:

a. The device's static and global variables, which are identified from the debug symbols (including address, size, type, endianness)
b. firmware ID, which is used to match the SFD with the corresponding firmware
c. Metadata about the firmware, such as its name, project version, author, build date, etc.
d. Alias definitions

The :abbr:`SFD (Scrutiny Firmware Description)` must be installed on the server using the ``install-sfd`` command with the :abbr:`CLI (Command Line Interface)`. 

When a device connects, the server will automatically load the appropriate :abbr:`SFD (Scrutiny Firmware Description)` based on the 
firmware ID that the device broadcasts.

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.get_installed_sfds

-----

.. autoclass:: scrutiny.sdk.SFDInfo
    :exclude-members: __new__, __init__
    :members:
    :member-order: bysource

-----

.. autoclass:: scrutiny.sdk.SFDMetadata
    :exclude-members: __new__, __init__
    :members:
    :member-order: bysource

-----

.. autoclass:: scrutiny.sdk.SFDGenerationInfo 
    :exclude-members: __new__, __init__
    :members:
    :member-order: bysource
