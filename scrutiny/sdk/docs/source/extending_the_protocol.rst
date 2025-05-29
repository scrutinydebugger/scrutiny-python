Extending the protocol
======================

The server and the device communicate through a binary protocol, designed exclusively for Scrutiny.
This protocol is half-duplex and operates in a command-based fashion. Each request has a command ID (7bits) and a subcommand ID (8bits). 

In order to allow a user to share that communication channel with Scrutiny without interfering, it is possible to encapsulate data into a dedicated 
Scrutiny command called ``UserCommand``. This command ID solely activates a user-defined callback in the firmware, 
passing the subfunction and data to this callback.

It is possible to send a ``UserCommand`` through the python :abbr:`SDK (Software Development Kit)`. 
The device's response will then be relayed directly back to the client.

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.user_command

-----

.. autoclass:: scrutiny.sdk.UserCommandResponse
    :exclude-members: __init__, __new__
    :members:
    :member-order: bysource
