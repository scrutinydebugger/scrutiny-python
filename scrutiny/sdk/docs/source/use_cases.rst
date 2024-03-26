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
Additional :abbr:`GPIO (General Purpose Input/Output)` may be use to get a feedback, or even an analog input.

The following piece of C++ depicts a very simplified version of what it could be. We have a ``do_powerup`` function that blocks until completion or timeout.
The structure of that function depicts a Finite State Machine (FSM); a construct quite useful to do automation.

.. literalinclude:: _static/code-examples/hil_testing1.cpp
    :language: c++
    :encoding: utf-8
