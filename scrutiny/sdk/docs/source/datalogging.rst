.. _page_datalogging:

Datalogging
===========

Usage of the SDK watchables as described in :ref:`Accessing variables<page_accessing_variables>` is done through polling and the update rate is limited by the bandwidth 
of the communication link between the server and the device (Serial, TCP, CAN, etc). Therefore, monitoring a value in Python is not a reliable way to catch a 
fast event in the firmware since two polling events may be spaced by several milliseconds.

Datalogging (or `Embedded Graphs`) solve that problem by requesting the device to record a certain set of watchable in a circular buffer until a certain event occurs. 
It effectively transform the embedded device into a scope. 

The condition that stop the circular acquisition is called the `Trigger condition` and may be of many type.
Once the trigger condition is fulfilled, the acquisition finishes (immediately or after a specified amount of time) and the data is returned to the server to be saved into a database. 
A client can then download and display that data under the form of a graph.


Configuring the datalogger
--------------------------

The first step before configuring the datalogger is knowing what the device is capable of in terms of datalogging. We need information such as :
 - Is datalogging even supported?
 - What are the sampling rates?
 - What is the size of the buffer?
 - How many signal can I log?
 - etc

Getting that information is done through :meth:`ScrutinyClient.get_datalogging_capabilities<scrutiny.sdk.client.ScrutinyClient.get_datalogging_capabilities>` 
and returns a :class:`DataloggingCapabilities<scrutiny.sdk.datalogging.DataloggingCapabilities>`

.. automethod:: scrutiny.sdk.client.ScrutinyClient.get_datalogging_capabilities

-----

.. autoclass:: scrutiny.sdk.datalogging.DataloggingCapabilities
    :exclude-members: __init__, __new__
    :members:

-----

Configuring and arming the datalogger is possible with the :meth:`ScrutinyClient.start_datalog<scrutiny.sdk.client.ScrutinyClient.start_datalog>` method
which takes a :class:`sdk.DataloggingConfig<scrutiny.sdk.datalogging.DataloggingConfig>` as sole argument. 

.. automethod:: scrutiny.sdk.client.ScrutinyClient.start_datalog

.. autoclass:: scrutiny.sdk.datalogging.DataloggingConfig
    :members:
    :exclude-members: __new__


-----

.. autoclass:: scrutiny.sdk.datalogging.TriggerCondition
    :members:
    :exclude-members: __init__, __new__

-----

.. autoclass:: scrutiny.sdk.datalogging.XAxisType
    :members:
    :exclude-members: __init__, __new__

-----

.. autoclass:: scrutiny.sdk.datalogging.AxisDefinition
    :members:
    :exclude-members: __init__, __new__
-----

.. autoclass:: scrutiny.sdk.datalogging.SamplingRate
    :members:
    :exclude-members: __init__, __new__