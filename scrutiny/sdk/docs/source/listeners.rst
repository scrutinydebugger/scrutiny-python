Listeners
=========

Introduction
------------

Synchronous access to watchables (variables, aliases, and :abbr:`RPVs (Runtime Published Value)`), as outlined in the 
:ref:`Accessing Variables<page_accessing_variables>` section, can be useful. 
However, it has certain limitations, especially when monitoring multiple values simultaneously.

Accessing watchables (variables, aliases and :abbr:`RPVs (Runtime Published Value)`) in a synchronous manner as depicted in 
:ref:`Accessing Variables<page_accessing_variables>` can be useful, but has some limitations when comes to monitoring multiple value at the same time. 

For example, if one wants to log a list of watchables, it would required to continuously loop and monitor the 
:attr:`udpate_counter<scrutiny.sdk.watchable_handle.WatchableHandle.update_counter>` property to detect changes. 
However, this approach does not guarantee that all changes will be noticed by the user thread.
In addition to being unreliable, this technique will cause unnecessary CPU usage.

To address this issue, the :class:`Client<scrutiny.sdk.client.ScrutinyClient>` object can function as a `Notifier`. 
It informs a list of listeners when it receives a value update broadcast from the server.
Registering a listener is done through :meth:`register_listener<scrutiny.sdk.client.ScrutinyClient.register_listener>`

.. automethod:: scrutiny.sdk.client.ScrutinyClient.register_listener

-----

Using a listener
----------------

The first step in using a listener is to subscribe watchables to it by calling :meth:`subscribe()<scrutiny.sdk.listeners.BaseListener.subscribe>`.

.. automethod:: scrutiny.sdk.listeners.BaseListener.subscribe


Once this is done, the listener can be started, after which, subscribing to new watchables is not allowed.
Each listener has a :meth:`start()<scrutiny.sdk.listeners.BaseListener.start>` and a :meth:`stop()<scrutiny.sdk.listeners.BaseListener.stop>` method.

.. automethod:: scrutiny.sdk.listeners.BaseListener.start

-----

.. automethod:: scrutiny.sdk.listeners.BaseListener.stop


:meth:`start()<scrutiny.sdk.listeners.BaseListener.start>` can be used is a ``with`` statement like so

.. code-block:: python

    from scrutiny.sdk.client import ScrutinyClient
    from scrutiny.sdk.listeners.text_stream_listener import TextStreamListener
    import time

    client = ScrutinyClient()
    with client.connect('localhost', 1234):
        listener = TextStreamListener()     # TextStreamListener prints all updates to stdout by default
        client.register_listener(listener)  # Attach to the client

        some_var_1 = client.watch('/var/global/some_var')
        the_other_var = client.watch('/var/static/main.cpp/the_other_var')

        listener.subscribe([some_var_1, the_other_var]) # Tells the listener which watchable to listen for
        with listener.start():  # Start the listener
            # setup() has been called from the listener thread
            time.sleep(5)
        # teardown() has been called from the listener thread

        print("We are done")
    # Client is automatically disconnected


-----

Internal behavior
-----------------

A listener runs in a separate thread and awaits value updates by monitoring a queue that is fed by the 
:class:`client<scrutiny.sdk.client.ScrutinyClient>` object. 
The Python ``queue`` object internally utilizes `condition variables`, which results in a scheduler switch between 
the executing thread occurring in just microseconds.

When the update notification reaches the listener, they are forwarded to the listener-specific 
:meth:`receive()<scrutiny.sdk.listeners.BaseListener.receive>` method.


.. image:: _static/listener_threads.png
    :width: 90%
    :align: center


Once the user thread invokes the :meth:`start()<scrutiny.sdk.listeners.BaseListener.start>` method, the listener thread is started
and the :meth:`setup()<scrutiny.sdk.listeners.BaseListener.setup>` method is called from within this new thread.

If :meth:`start()<scrutiny.sdk.listeners.BaseListener.start>` succeeds and :meth:`setup()<scrutiny.sdk.listeners.BaseListener.setup>` 
is invoked, the :meth:`teardown()<scrutiny.sdk.listeners.BaseListener.teardown>` method is guaranteed to be called, 
irrespective of whether an exception is raised within the :meth:`setup()<scrutiny.sdk.listeners.BaseListener.setup>` 
or :meth:`receive()<scrutiny.sdk.listeners.BaseListener.receive>`.

The :meth:`teardown()<scrutiny.sdk.listeners.BaseListener.teardown>` is called from the listener thread if the user calls
the :meth:`stop()<scrutiny.sdk.listeners.BaseListener.stop>` method or if an exception occur during setup or while listening.

-----


Writing a Listener
------------------

To write a listener, one must create a class that inherits the :class:`BaseListener<scrutiny.sdk.listeners.BaseListener>` class and implements
the :meth:`receive()<scrutiny.sdk.listeners.BaseListener.receive>` method.  

.. autoclass:: scrutiny.sdk.listeners.BaseListener
    :exclude-members: __new__, setup, teardown, start, stop, receive, subscribe
    :members:
    :member-order: bysource

-----

.. automethod:: scrutiny.sdk.listeners.BaseListener.receive

-----

The element passed to :meth:`receive()<scrutiny.sdk.listeners.BaseListener.receive>` are immutable :class:`ValueUpdate<scrutiny.sdk.listeners.ValueUpdate>`
objects that represents the update content.

.. autoclass:: scrutiny.sdk.listeners.ValueUpdate
    :exclude-members: __new__, __init__
    :members:
    :member-order: bysource

-----

Two optional methods can be overriden to perform a :meth:`setup<scrutiny.sdk.listeners.BaseListener.setup>` and/or 
a :meth:`teardown<scrutiny.sdk.listeners.BaseListener.teardown>`. If not overriden, these 2 methods will do nothing by default.

.. automethod:: scrutiny.sdk.listeners.BaseListener.setup

-----

.. automethod:: scrutiny.sdk.listeners.BaseListener.teardown

-----

Available listeners
-------------------

There is a few listeners already available in the Scrutiny SDK.

TextStreamListener
##################

.. autoclass:: scrutiny.sdk.listeners.text_stream_listener.TextStreamListener
    :exclude-members: __new__


BufferedReaderListener
######################

.. autoclass:: scrutiny.sdk.listeners.buffered_reader_listener.BufferedReaderListener
    :exclude-members: __new__
    :members: get_queue


CSVFileListener
###############

.. autoclass:: scrutiny.sdk.listeners.csv_file_listener.CSVFileListener
    :exclude-members: __new__

-----

.. autoclass:: scrutiny.sdk.listeners.csv_file_listener.CSVConfig 
    :exclude-members: __new__, __init__
    :members:
    :member-order: bysource
