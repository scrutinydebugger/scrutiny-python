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

.. literalinclude:: _static/code-examples/hil_testing/hil_testing_1_time_hpp.cpp
    :language: c++
    :encoding: utf-8

.. literalinclude:: _static/code-examples/hil_testing/hil_testing_2_hardware_hpp.cpp
    :language: c++
    :encoding: utf-8

.. literalinclude:: _static/code-examples/hil_testing/hil_testing_3_power_supply_hpp.cpp
    :language: c++
    :encoding: utf-8

.. literalinclude:: _static/code-examples/hil_testing/hil_testing_4_power_supply_cpp.cpp
    :language: c++
    :encoding: utf-8

.. literalinclude:: _static/code-examples/hil_testing/hil_testing_5_application_hpp.cpp
    :language: c++
    :encoding: utf-8

.. literalinclude:: _static/code-examples/hil_testing/hil_testing_6_main_cpp.cpp
    :language: c++
    :encoding: utf-8

Python script
#############

An example of a Python script that tests the device could go as follow.

.. literalinclude:: _static/code-examples/hil_testing/hil_testing_1_powerup_check.py
    :language: python
    :encoding: utf-8

-----

End-Of-Line configuration
-------------------------

EOL configuration is another intersting use case for the Scrutiny Python SDK. Let's consider a product that requires a configuration step after manufacturing.

This configuration could be writing parameters and assembly information (model, serial number, etc) in a Non-Volatile Memory or burning a fuse in the processor. 
In most application, the :abbr:`NVM (Non-Volatile Memory)` is connected to the processor, making it accessible to the firmware or a advanced JTAG.

In this example, we will show how we can add a hook in the firmware to let a remote user take control of a :abbr:`EEPROM (Electrically Erasable Programmable Read-Only Memory)` 
(a type of :abbr:`NVM (Non-Volatile Memory)`) through the SDK. We will abstract the EEPROM driver under a class that have a ``write()`` and a ``read()`` method.


C++ Application
###############

.. literalinclude:: _static/code-examples/eol_config/eol_config_1_eeprom_driver_hpp.cpp
    :language: c++
    :encoding: utf-8

.. literalinclude:: _static/code-examples/eol_config/eol_config_2_eeprom_configurator_hpp.cpp
    :language: c++
    :encoding: utf-8

.. literalinclude:: _static/code-examples/eol_config/eol_config_3_eeprom_configurator_cpp.cpp
    :language: c++
    :encoding: utf-8

.. literalinclude:: _static/code-examples/eol_config/eol_config_4_main_cpp.cpp
    :language: c++
    :encoding: utf-8



Python script
#############

.. literalinclude:: _static/code-examples/eol_config/eol_config_assembly_header.py
    :language: python
    :encoding: utf-8

We can even make something a little more advanced and encapsulate everything related to the EEPROM interaction into a ``EEPROMConfigurator`` class.
Using the value of ``m_buffer``, which is a pointer, we can leverage :meth:`ScrutinyClient.read_memory()<scrutiny.sdk.client.ScrutinyClient.read_memory>`
to dump the content of the EEPROM.

.. literalinclude:: _static/code-examples/eol_config/eol_config_dump_eeprom.py
    :language: python
    :encoding: utf-8

-----

Control algorithm tuning
------------------------

The following example is a bit more creative and shows how powerful Scrutiny can be when developping embedded firmware. 

It illustrates a scenario where a PI controller operates within a 10KHz control loop, demonstrating how the controller's 
response could be characterized automatically. 
For the sake of simplicity, this example does not include validation of the controller's operational conditions 
(i.e., there are no error conditions or feedback range checks).

- The controller in question is a PI controller with a saturated output.
- The parameters can be declared as ``const`` or ``volatile`` based on a compilation option
   
  - When declared as ``const`` the compiler can optimize for speed, which would be a typical production configuration.
  - When declared as ``volatile``, the compiler will not perform any optimization, ensuring that the scrutiny input will be recognized.

- The configuration of the scrutiny-embedded library is not shown in this example, as the focus is primarily on the SDK.


C++ Application
###############

.. literalinclude:: _static/code-examples/calibration/calibration_1_pi_controller_sat_hpp.cpp
    :language: c++
    :encoding: utf-8

.. literalinclude:: _static/code-examples/calibration/calibration_2_main_cpp.cpp
    :language: c++
    :encoding: utf-8


The following python script accepts gains value (kp, ki) from the command line and initiates a characterization process.
This process involves incrementally adjusting the control reference from 0 to 0.1, then 0 to 0.2, 0 to 0.3, and so on.  
At each step, the built-in data logger records the controller’s response to the input step. 
The script then saves this data to a CSV file using the Scrutiny SDK.

Python script
#############

.. literalinclude:: _static/code-examples/calibration/calibration_1_pi_graph.py
    :language: python
    :encoding: utf-8
