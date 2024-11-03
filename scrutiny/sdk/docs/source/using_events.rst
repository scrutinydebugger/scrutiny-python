.. _page_using_events:

Using Events
============

The design of the :class:`client<scrutiny.sdk.client.ScrutinyClient>`, and the SDK in general, is synchronous.
A synchronous design is generally wanted for automation script, but in some other case, like a User Interface, an asynchronous design can be preferable.

The SDK has no integration with any asynchronous library (asyncio, or 3rd parties one), but an optional event queue is offered to allow such custom integration.

.. note:: The Scrutiny GUI is built using QT. The SDK event queue is read in a thread and used to trigger QT signals, 
    making the bridge between the synchronous and asynchronous worlds.

-----


-----
