Device
======


.. py:class:: scrutiny.sdk.EmbeddedDataType (Enum)

    Represent a data type in the C++ firmware. Values are 
        - sintX (X: 8, 16, 32, 64)
        - uintX (X: 8, 16, 32, 64)
        - floatX (X: 32, 64)
        - boolean

    .. automethod:: scrutiny.sdk.EmbeddedDataType.get_size_bit
    .. automethod:: scrutiny.sdk.EmbeddedDataType.get_size_byte


