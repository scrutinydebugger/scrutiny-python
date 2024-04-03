Use cases
=========

It may not be so obvious at first glance what is the purpose of the Scrutiny SDK and what can be achieved with it.

In this article, some typical interesting use cases will be explored

-----

HIL Testing
-----------

Hardware-In-the-Loop testing is certainly the most interesting feature enabled by the Python SDK.

Let's consider an hypothetical device where a hardware power-up sequence must be controlled by an onboard microcontroller. 
Upon startup, the firmware will initialise itself then launch the power-up sequence of other hardware modules using :abbr:`GPIO (General Purpose Input/Output)`.
Additional :abbr:`GPIO (General Purpose Input/Output)` may be used to get a feedback, an analog input too.

C++ Application
###############

The following piece of C++ depicts a very simplified version of what it could be. We have a ``PowerSupply`` class that does a fictive power up sequence with
a finite state machine. Notice how this file can be built with the ``ENABLE_HIL_TESTING`` define, allowing the application to delay its startup until Scrutiny 
takes over.

.. literalinclude:: _static/code-examples/hil_testing1.cpp
    :language: c++
    :encoding: utf-8

Python script
#############

An example of a Python script that tests the device could go as follow.

.. literalinclude:: _static/code-examples/hil_testing1.py
    :language: python
    :encoding: utf-8

-----

End-Of-Line configuration
-------------------------------

EOL configuration is another intersting use case for the Scrutiny Python SDK. Let's consider a product that requires a configuration step after manufacturing.

This configuration could be writing parameters and assembly information (model, serial number, etc) in a Non-Volatile Memory or burning a fuse in the processor. 
In most application, the :abbr:`NVM (Non-Volatile Memory)` is connected to the processor, making it accessible to the firmware or a advanced JTAG.

In this example, we will show how we can add a hook in the firmware to let a remote user take control of a :abbr:`EEPROM (Electrically Erasable Programmable Read-Only Memory)` 
(a type of :abbr:`NVM (Non-Volatile Memory)`) through the SDK. We will abstract the EEPROM driver under a class that have a ``write()`` and a ``read()`` method.


C++ Application
###############

.. literalinclude:: _static/code-examples/eol_config1.cpp
    :language: c++
    :encoding: utf-8


Python script
#############

.. literalinclude:: _static/code-examples/eol_config1.py
    :language: python
    :encoding: utf-8

We can even make something a little more advance and encapsulate everything related to the EEPROM interraction into a ``EEPROMConfigurator`` class.
Using the value of ``m_buffer``, which is a pointer, we can leverage :meth:`ScrutinyClient.read_memory()<scrutiny.sdk.client.ScrutinyClient.read_memory>`
to dump the content of the EEPROM.


.. literalinclude:: _static/code-examples/eol_config2.py
    :language: python
    :encoding: utf-8
