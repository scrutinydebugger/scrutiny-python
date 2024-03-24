.. _page_accessing_variables:

Accessing variables
===================

In the SDK, Variables, Aliases, :abbr:`RPV (Runtime Published Values)` are presented to the client side through an interface called a ``watchable``, e.g. something you can watch.

.. list-table:: Watchable types
    :widths: auto

    * - Variable
      - A variable maps to a static or global variable declared in the embedded device firmware. The variable address, type, size and endianness is defined in the loaded :abbr:`SFD (Scrutiny Firmware Description)`
      - Yes
    * - Runtime Published Values (RPV)
      - Readable and writable elements identified by a numerical ID (16 bits) and declared by the device during the handshake phase with the server.
      - No
    * - Alias
      - Abstract writable/readable entity that maps to either a variable or a :abbr:`RPV (Runtime Published Values)`. Used to keep a consistent firmware interface with existing scripts using this SDK
      - Yes

-----

Basics
------

The first step to access a watchable, is to first tell the server that we want to subscribe to update event on that watchable.
To do so, we use the :meth:`watch<scrutiny.sdk.client.ScrutinyClient.watch>` method and specify the path of the watchable. The path
depends on the firmware and must generally be known in advance. It is possible to query the server for the list of available watchable, this is what the GUI does.

For a :abbr:`SDK (Software Development Kit)` based script, it's generally expected that the element that will be accessed are known and won't require a user input to select them.

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.watch

Once an element is being watched, the server starts polling for the value of that element. Each time the value is updated, the server broadcast a value update to all subscribers, 
in this case, our client. A background thread listen for those updates and changes the value referred to by the :class:`WatchableHandle<scrutiny.sdk.watchable_handle.WatchableHandle>`

-----

.. autoclass:: scrutiny.sdk.watchable_handle.WatchableHandle
    :exclude-members: __new__
    :member-order: bysource
    :members: display_path, name, type, datatype, value, value_bool, value_int, value_float, last_update_timestamp, last_write_timestamp, update_counter

-----

After getting a handle to the watchable, the :attr:`value<scrutiny.sdk.watchable_handle.WatchableHandle.value>` property and its derivative (
:attr:`value_int<scrutiny.sdk.watchable_handle.WatchableHandle.value_int>`, 
:attr:`value_float<scrutiny.sdk.watchable_handle.WatchableHandle.value_float>`, 
:attr:`value_bool<scrutiny.sdk.watchable_handle.WatchableHandle.value_bool>`) are automatically updated. The values are invalid until their first update, 
meaning that after the call to :meth:`watch<scrutiny.sdk.client.ScrutinyClient.watch>`, there is a period of time where accessing the 
:attr:`value<scrutiny.sdk.watchable_handle.WatchableHandle.value>`
property will raise a :class:`InvalidValueError<scrutiny.sdk.exceptions.InvalidValueError>`.

One can wait for a single watchable update with :meth:`WatchableHandle.wait_update<scrutiny.sdk.watchable_handle.WatchableHandle.wait_update>` or wait for all watched variable by Calling
:meth:`ScrutinyClient.wait_new_value_for_all<scrutiny.sdk.client.ScrutinyClient.wait_new_value_for_all>`

.. code-block:: python

    import time

    w1 = client.watch('/alias/my_alias1')
    w2 = client.watch('/rpv/x1234')
    w3 = client.watch('/var/main.cpp/some_func/some_var')
    client.wait_new_value_for_all() # Make sure all watchables have their first value available

    while w1.value_bool:            # Value updated by a background thread 
        print(f"w2 = {w2.value}")   # Value updated by a background thread
        time.sleep(0.1)
    
    w3.value = 123  # Blocking write. This statement blocks until the device has confirmed that the variable is correctly written (or raise on failre).

.. note:: 

    Reading and writing a watchable may raise an exceptions.

    - Reading : When value is unavailable. This will happen if 
        a. The watchable has never been updated (small window of time after subscription)
        b. The server disconnects
        c. The device is disconnects

    - Writing : When the value cannot be written. This will happen if 
        a. The server disconnects
        b. The device is disconnects
        c. Writing is actively denied by the device. (Communication error or protected memory region)
        d. Timeout: The write confirmation takes more time than the client ``write_timeout``

As we can see in the example above, accesses to the device is done in a fully synchronized fashion. Therefore, a script that uses the Scrutiny Python SDK
can be seen as a thread running on the embedded device, but with slow memory access time.

-----

Detecting a value change
------------------------

When developing a script that uses the SDK, it is common to have some back and forth between the device and the script. A good example would be the case of a test sequence,
one could write a sequence that looks like this

1. Write a GPIO
2. Wait for another GPIO to change its value
3. Start an EEPROM clear sequence
4. Wait for the sequence to finish

Each time the value is updated by the server, the :attr:`WatchableHandle.update_counter<scrutiny.sdk.watchable_handle.WatchableHandle.update_counter>` gets incremented. 
Looking for this value is helpful to detect a change. 
Two methods can help the user to wait for remote event. :meth:`WatchableHandle.wait_update<scrutiny.sdk.watchable_handle.WatchableHandle.wait_update>` and 
:meth:`WatchableHandle.wait_value<scrutiny.sdk.watchable_handle.WatchableHandle.wait_value>`

It is important to mention that the server does not continuously stream the values of the variables, but rather stream changes in value. 
Therefore, :meth:`wait_update<scrutiny.sdk.watchable_handle.WatchableHandle.wait_update>` may raise a timeout if the value never changes 
on the device, even if the server has polled the device many times since then.

.. automethod:: scrutiny.sdk.watchable_handle.WatchableHandle.wait_update

-----

.. automethod:: scrutiny.sdk.watchable_handle.WatchableHandle.wait_value

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.wait_new_value_for_all

-----

Batch writing
-------------

Writing multiples values in a row is inefficient because of the device access latency. For speed optimization, it is possible to group multiple write operation into 
a batched request using :meth:`ScrutinyClient.batch_write<scrutiny.sdk.client.ScrutinyClient.batch_write>`. 

When doing a batch write, multiple write request queued and sent to the server in a single API call. 
Then the server executes all write operation, in the correct order, and confirms the completion of the full batch. 

It is possible to do multiple writes to the same watchable in the same batch. The server will ensure that a write operation is completed and confirmed by the device
before initiating the following

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.batch_write

-----

Example 
#######

.. code-block:: python

    w1 = client.watch('/alias/my_alias1')
    w2 = client.watch('/rpv/x1234')
    w3 = client.watch('/var/main.cpp/some_func/some_var')
    try:
        with client.batch_write(timeout=3):
            w1.value = 1.234
            w2.value = 0x11223344
            w2.value = 0x55667788
            w3.value = 2.345
            w1.value = 3.456
            # Exiting the with block will block until the batch completion or failure (with an exception)

        print("Batch writing successfully completed")
    except ScrutinySDKException as e:
        print(f"Failed to complete a batch write. {e}")


-----

Accessing the raw memory
------------------------

In certain case, it can be useful to access the device memory directly without the layer of interpretation in the server that converts the data into a coherent value.
Such case could be 

- Dumping a data buffer
- Uploading a firmware
- Pushing a ROM image
- etc

For those cases, one can use :meth:`ScrutinyClient.read_memory<scrutiny.sdk.client.ScrutinyClient.read_memory>` and :meth:`ScrutinyClient.write_memory<scrutiny.sdk.client.ScrutinyClient.write_memory>`
to access the memory

.. automethod:: scrutiny.sdk.client.ScrutinyClient.read_memory

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.write_memory

