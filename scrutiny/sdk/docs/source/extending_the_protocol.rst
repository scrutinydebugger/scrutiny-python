Extending the protocol
======================

The communication protocol between the server and the device is a fully custom binary protocol developed specifically for Scrutiny. 
This protocol is a half-duplex, command-based protocol. Each request has a command ID (7bits) and a subcommand ID (8bits). 

In order to allow a user to share that communication channel with Scrutiny without interfering, it is possible to encapsulate data into a dedicated 
Scrutiny command called ``UserCommand``. This command ID does nothing else than triggers a user-written callback in the firmware. 
The subfunction and data are passed to that callback . 

It is possible to send a ``UserCommand`` through the python :abbr:`SDK (Software Development Kit)` and the device response will be carried all the way back to the client.

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.user_command

-----

.. autoclass:: scrutiny.sdk.UserCommandResponse
    :exclude-members: __init__, __new__
    :members:
    :member-order: bysource