Getting Started
===============

Using the Scrutiny Python SDK starts by creating a :class:`ScrutinyClient<scrutiny.sdk.client.ScrutinyClient>` object and connecting it to a running server.

.. code-block:: python

    from scrutiny.sdk.client import ScrutinyClient

    hostname = 'localhost'
    port = 1234
    client = ScrutinyClient()
    with client.connect(hostname, port, wait_status=True):    # Establish a websocket connection and wait for a first server status update
        print("Connected to server")
        server_status = client.get_server_status()       # Status is dynamic and updated by a background thread. Get an immutable reference
        if server_status.device_session_id is not None:
            print(f"Connected to device {server_status.device.display_name} ({server_status.device.session_id})")   
        else:
            print("No device connected")
 