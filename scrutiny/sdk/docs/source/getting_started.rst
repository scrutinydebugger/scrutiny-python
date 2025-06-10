Getting Started
===============

Installing the SDK
------------------

The easiest way to get the Scrutiny Python SDK is to use pip.

.. code-block:: bash

    pip install scrutinydebugger

After the installation, the :abbr:`SDK (Software Development Kit)` should be usable as well as all the other features (:abbr:`CLI (Command Line Interface)`, :abbr:`GUI (Graphical User Interface)`, Server)`.

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
    with client.connect(hostname, port, wait_status=True):    # Establish a connection and wait for a first server status update
        print("Connected to server")
        server_status = client.get_server_status()       # Status is dynamic and updated by a background thread. Get an immutable reference
        if server_status.device_comm_state == sdk.DeviceCommState.ConnectedReady:
            print(f"Connected to device {server_status.device.display_name} ({server_status.device.session_id})")   
        else:
            print("No device connected to the server")
 
Most operations with the Python :abbr:`SDK (Software Development Kit)` are synchronized, meaning they will block until completion. When relevant for performance, some operations will return a reference to a ``future`` 
object that can be waited for when necessary.

Operations that fail raise an exception. All exceptions defined in the Scrutiny SDK inherit the :class:`sdk.ScrutinySDKException<scrutiny.sdk.exceptions.ScrutinySDKException>`. 

See the :ref:`Exceptions page<page_exceptions>`

-----

.. autoclass:: scrutiny.sdk.client.ScrutinyClient
    :exclude-members: __new__

-----

Some methods will return an instance of a :class:`PendingRequest<scrutiny.sdk.pending_request.PendingRequest>`. These instances are handled to follow the progress of
an operation that may take long time to execute.

.. autoclass:: scrutiny.sdk.pending_request.PendingRequest
    :exclude-members: __new__, __init__
    :member-order: bysource
    :members:
