Getting Started
===============

Installing the SDK
------------------

The easiest way to get the Scrutiny Python SDK is to use pip.

.. code-block:: bash

    pip install scrutiny

After the installation, the :abbr:`SDK (Software Development Kit)` should be usable as well as the :abbr:`CLI (Command Line Interface)`.

.. note:: 

    The long term plan is to also distribute Scrutiny through an installer that will include the GUI as well as the Python virtual environment. 
    Until this point is reached, install through the command line is the best option

-----

Quick introduction
------------------

Using the Scrutiny Python :abbr:`SDK (Software Development Kit)` starts by creating a :class:`ScrutinyClient<scrutiny.sdk.client.ScrutinyClient>` object and connecting it to a running server.

.. code-block:: python

    from scrutiny import sdk
    from scrutiny.sdk.client import ScrutinyClient

    hostname = 'localhost'
    port = 1234
    client = ScrutinyClient()
    with client.connect(hostname, port, wait_status=True):    # Establish a websocket connection and wait for a first server status update
        print("Connected to server")
        server_status = client.get_server_status()       # Status is dynamic and updated by a background thread. Get an immutable reference
        if server_status.device_comm_state == sdk.DeviceCommState.ConnectedReady:
            print(f"Connected to device {server_status.device.display_name} ({server_status.device.session_id})")   
        else:
            print("No device connected to the server")
 
Most operation with the Python :abbr:`SDK (Software dEvelopment Kit)` are synchronized, meaning they will block until completion. When relevant for performance, some operations will return a reference to a ``future`` 
object that can be waited for when necessary.

Operations that fail raise an exception. All exceptions defined in the Scrutiny SDK inherit the :class:`sdk.ScrutinySDKException<scrutiny.sdk.ScrutinySDKException>`. 

See the :ref:`Exceptions page<page_exceptions>`

-----

.. autoclass:: scrutiny.sdk.client.ScrutinyClient
    :exclude-members: __new__
