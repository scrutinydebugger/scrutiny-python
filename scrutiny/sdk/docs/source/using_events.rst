.. _page_using_events:

Using Events
============

The design of the :class:`client<scrutiny.sdk.client.ScrutinyClient>`, and the :abbr:`SDK (Software Development Kit)` in general, is synchronous.
A synchronous design is generally preferred for automation scripts, but in some other cases, such as a user interface, an asynchronous design may be preferable.

The :abbr:`SDK (Software Development Kit)` has no integration with any asynchronous library (such as asyncio or third-party libraries), 
but an optional event queue is offered to allow for custom integration.  

.. note:: The Scrutiny :abbr:`GUI (Graphical User Interface)` is built using QT. 
    The :abbr:`SDK (Software Development Kit)` event queue is read in a thread and used to trigger QT signals, 
    making the bridge between the synchronous and asynchronous worlds.


Example
#######

.. literalinclude:: _static/code-examples/event_looping/event_looping.py
    :language: python
    :encoding: utf-8

-----

Methods
-------


.. automethod:: scrutiny.sdk.client.ScrutinyClient.listen_events
.. automethod:: scrutiny.sdk.client.ScrutinyClient.read_event
.. automethod:: scrutiny.sdk.client.ScrutinyClient.clear_event_queue


.. autoclass:: scrutiny.sdk.client.ScrutinyClient.Events
    :exclude-members: __new__, __init__, ConnectedEvent,DisconnectedEvent,DeviceReadyEvent,DeviceGoneEvent,SFDLoadedEvent,SFDUnLoadedEvent,DataloggerStateChanged,StatusUpdateEvent,DataloggingListChanged
    :members:
    :member-order: bysource



Events
------

.. autoclass:: scrutiny.sdk.client.ScrutinyClient.Events.ConnectedEvent
    :exclude-members: __new__, __init__
    :members:

.. autoclass:: scrutiny.sdk.client.ScrutinyClient.Events.DisconnectedEvent
    :exclude-members: __new__, __init__
    :members:

.. autoclass:: scrutiny.sdk.client.ScrutinyClient.Events.DeviceReadyEvent
    :exclude-members: __new__, __init__
    :members:

.. autoclass:: scrutiny.sdk.client.ScrutinyClient.Events.DeviceGoneEvent
    :exclude-members: __new__, __init__
    :members:

.. autoclass:: scrutiny.sdk.client.ScrutinyClient.Events.SFDLoadedEvent
    :exclude-members: __new__, __init__
    :members:

.. autoclass:: scrutiny.sdk.client.ScrutinyClient.Events.SFDUnLoadedEvent
    :exclude-members: __new__, __init__
    :members:

.. autoclass:: scrutiny.sdk.client.ScrutinyClient.Events.DataloggerStateChanged
    :exclude-members: __new__, __init__
    :members:

.. autoclass:: scrutiny.sdk.client.ScrutinyClient.Events.StatusUpdateEvent
    :exclude-members: __new__, __init__
    :members:

.. autoclass:: scrutiny.sdk.client.ScrutinyClient.Events.DataloggingListChanged
    :exclude-members: __new__, __init__
    :members:
