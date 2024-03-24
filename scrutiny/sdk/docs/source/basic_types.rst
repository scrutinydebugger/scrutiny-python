Basic Types
===========


.. py:class:: scrutiny.core.basic_types.EmbeddedDataType

    (Enum) Represent a data type in the C++ firmware. Values are 
    
    - sintX (X: 8, 16, 32, 64)
    - uintX (X: 8, 16, 32, 64)
    - floatX (X: 32, 64)
    - boolean

    .. automethod:: scrutiny.sdk.EmbeddedDataType.get_size_bit
    .. automethod:: scrutiny.sdk.EmbeddedDataType.get_size_byte


-----

.. autoclass:: scrutiny.core.basic_types.Endianness
    :exclude-members: __init__, __new__
    :members:
    :member-order: bysource
