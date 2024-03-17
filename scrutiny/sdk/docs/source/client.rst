Client
======

The :class:`ScrutinyClient<scrutiny.sdk.ScrutinyClient>` object is the main tool to interact with the server. The client is fully synchronous and every methods will either 
block until the operation is fully completed or a `future` object will be returned which can be waited for.

.. autoclass:: scrutiny.sdk.client.ScrutinyClient

-----



Server interaction
------------------

The following methods are used to interact with the server only. Calling them will have no effect on a potentially 
connected device and will succeeds regardless if a device is connected or not.

.. automethod:: scrutiny.sdk.client.ScrutinyClient.connect

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.disconnect

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.wait_server_status_update

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.get_server_status

-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.get_installed_sfds

-----



Using the device variables
--------------------------

The following methods are used to interact with the variables/SFD of the firmware of a connected device.
They will fail if no device is connected.

For more details, read the :ref:`Accessing variables<page_accessing_variables>` page

.. automethod:: scrutiny.sdk.client.ScrutinyClient.watch
    
-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.unwatch
    
-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.wait_new_value_for_all
    
-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.batch_write
    
-----



Raw access to the device memory
-------------------------------

In some case, it might be useful to access the device raw memory without using a variable/SFD

.. automethod:: scrutiny.sdk.client.ScrutinyClient.read_memory
    
-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.write_memory



Datalogging
-----------

The following methods are used to control the datalogging feature of a device. They can be used to acquire a graph programmatically.
For more details, read the :ref:`Datalogging<page_datalogging>` page


.. automethod:: scrutiny.sdk.client.ScrutinyClient.get_datalogging_capabilities
    
-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.start_datalog
    
-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.list_stored_datalogging_acquisitions
    
-----

.. automethod:: scrutiny.sdk.client.ScrutinyClient.read_datalogging_acquisition
    
-----


Device configuration
--------------------

.. automethod:: scrutiny.sdk.client.ScrutinyClient.configure_device_link

-----

User command
------------

.. automethod:: scrutiny.sdk.client.ScrutinyClient.user_command
