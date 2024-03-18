Getting Started
===============

Installing the SDK
------------------

.. note::

    TODO

Quick introduction
------------------

Using the Scrutiny Python SDK starts by creating a :class:`ScrutinyClient<scrutiny.sdk.client.ScrutinyClient>` object and connecting it to a running server.

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
 
Most operation with the Python SDK are synchronized, meaning they will block until completion. When relevant for performance, some operations will return a reference to a ``future`` 
object that can be waited for when necessary.

Operation that fails throws an exception. All exception defined in the Scrutiny SDK inherits the :class:`sdk.ScrutinySDKException<scrutiny.sdk.ScrutinySDKException>`. 

See the :ref:`Exceptions page<page_exceptions>`

