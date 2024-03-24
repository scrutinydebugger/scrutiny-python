Scrutiny Firmware Description (SFD)
===================================

A Scrutiny Firmware Description (SFD) is a file generated during the build step of the embedded firmware. This file contains 

a. The devices static and global variables discovered from the debug symbols (include address, size, type, endinaness)
b. A firmware ID used to match the SFD with the firmware
c. Some metadata about the firmware such as a name, project version, author, build date, etc.
d. Alias definitions

The :abbr:`SFD (Scrutiny Firmware Description)` must be installed on the server with the :abbr:`CLI (Command Line Interface)` using the ``install-sfd`` command. 

Upon connection with a device, the server will automatically load the correct :abbr:`SFD (Scrutiny Firmware Description)` based on the firmware ID broadcasted by the device

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