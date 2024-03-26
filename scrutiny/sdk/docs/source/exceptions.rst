.. _page_exceptions:

Exceptions
==========

All exceptions thrown by the Scrutiny Python :abbr:`SDK (Software Development Kit)` inherits the common :class:`ScrutinySDKException<scrutiny.sdk.ScrutinySDKException>`.

The inheritance hierarchy goes as follows.

.. image:: _static/exception_hierarchy.png
    :scale: 80 %
    :alt: Exception hierarchy
    :align: center

-----

.. autoclass:: scrutiny.sdk.exceptions.ScrutinySDKException
    :exclude-members: __init__, __new__

-----

.. autoclass:: scrutiny.sdk.exceptions.ConnectionError
    :exclude-members: __init__, __new__

-----

.. autoclass:: scrutiny.sdk.exceptions.InvalidValueError
    :exclude-members: __init__, __new__

-----

.. autoclass:: scrutiny.sdk.exceptions.OperationFailure
    :exclude-members: __init__, __new__

-----

.. autoclass:: scrutiny.sdk.exceptions.TimeoutException
    :exclude-members: __init__, __new__

-----

.. autoclass:: scrutiny.sdk.exceptions.NameNotFoundError
    :exclude-members: __init__, __new__

-----

.. autoclass:: scrutiny.sdk.exceptions.ApiError
    :exclude-members: __init__, __new__

-----

.. autoclass:: scrutiny.sdk.exceptions.BadResponseError
    :exclude-members: __init__, __new__

-----

.. autoclass:: scrutiny.sdk.exceptions.ErrorResponseException
    :exclude-members: __init__, __new__