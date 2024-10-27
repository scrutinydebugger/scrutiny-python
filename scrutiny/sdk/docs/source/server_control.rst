Server Control
==============

Establishing a connection
-------------------------

The communication with the server is done through a websocket. One can call :meth:`connect()<scrutiny.sdk.client.ScrutinyClient.connect>` 
and :meth:`disconnect()<scrutiny.sdk.client.ScrutinyClient.disconnect>`.  It is also possible to use :meth:`connect()<scrutiny.sdk.client.ScrutinyClient.connect>`
in a ``with`` block

.. automethod:: scrutiny.sdk.client.ScrutinyClient.connect

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.disconnect

-----

Example
#######

.. code-block:: python

    with client.connect('localhost', 1234):
        pass # Do something

    # disconnect automatically called

-----

Getting the server status
-------------------------

Upon establishing a connection with a client, and at regular intervals thereafter, the server broadcasts a status. 
This status is a data structure that encapsulates all the pertinent information about what is happening at the other end of the websocket. 
It includes:

- The type of connection used by the device
- Details about the device if one is connected
- The state of the datalogger within the device
- The loaded :abbr:`SFD (Scrutiny Frimware Description)` and its metadata if any
- etc.

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.get_server_status

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.wait_server_status_update

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.wait_device_ready

-----

.. autoclass:: scrutiny.sdk.ServerInfo
    :exclude-members: __init__, __new__
    :members:
    :member-order: bysource

-----

.. autoclass:: scrutiny.sdk.DeviceCommState
    :exclude-members: __init__, __new__
    :members:
    :member-order: bysource

-----

.. autoclass:: scrutiny.sdk.DeviceInfo
    :exclude-members: __init__, __new__
    :members:
    :member-order: bysource

-----

.. autoclass:: scrutiny.sdk.DeviceLinkInfo
    :exclude-members: __init__, __new__
    :members:
    :member-order: bysource

-----

.. autoclass:: scrutiny.sdk.SupportedFeatureMap
    :exclude-members: __init__, __new__
    :members:
    :member-order: bysource

-----

.. autoclass:: scrutiny.sdk.MemoryRegion
    :exclude-members: __init__, __new__
    :members:
    :member-order: bysource

-----

.. autoclass:: scrutiny.sdk.DataloggingInfo
    :exclude-members: __init__, __new__
    :members:
    :member-order: bysource

-----

.. autoclass:: scrutiny.sdk.DataloggerState
    :exclude-members: __init__, __new__
    :members:
    :member-order: bysource

-----

Configuring the device link
----------------------------

The device link is the communication channel between the server and the device. 

This link can be configured by the client. If a device is present, the server will automatically connect to it. If no device is found, the server will simply report 
that no device is connected

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.configure_device_link

-----

.. autoclass:: scrutiny.sdk.DeviceLinkType
    :exclude-members: __new__, __init__
    :members: 
    :member-order: bysource

-----

.. autoclass:: scrutiny.sdk.TCPLinkConfig
    :exclude-members: __new__, __init__
    :members:

-----

.. autoclass:: scrutiny.sdk.UDPLinkConfig
    :exclude-members: __new__, __init__
    :members:

-----

.. autoclass:: scrutiny.sdk.SerialLinkConfig
    :exclude-members: __new__, __init__
    :members:

.. autoclass:: scrutiny.sdk.SerialLinkConfig.StopBits
    :exclude-members: __new__, __init__
    :members:

.. autoclass:: scrutiny.sdk.SerialLinkConfig.DataBits
    :exclude-members: __new__, __init__
    :members:

.. autoclass:: scrutiny.sdk.SerialLinkConfig.Parity
    :exclude-members: __new__, __init__
    :members:    
    
-----

.. autoclass:: scrutiny.sdk.RTTLinkConfig
    :exclude-members: __new__, __init__, JLinkInterface
    :members:

-----

.. autoclass:: scrutiny.sdk.RTTLinkConfig.JLinkInterface
    :exclude-members: __new__, __init__
    :members:
    :member-order: bysource
