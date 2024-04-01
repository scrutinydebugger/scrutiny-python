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
