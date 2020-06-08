viewcontrol.remotecontrol
=========================

Commnication Thread
-------------------

Each Communication interface is started in its own thread, this way, the waiting for incomming massages can be blocking. Each Protocols/Devices thread class is derived from th Communication is derived from ``viewcontrol.remotecontrol.threadcommunicationbase``. Which also handles connection errors and writing into the log. All child Protocols/Devices just need to overwrite the ``listen()`` mehtod with the Protocol/Device specific code for communication.

For each device a new python module in the appropriate protocol package is created and the device class is derived from ThreadCommunication. Optionally a Dictionary with CommandTemplates can be created in the data folder a.

.. automodule:: viewcontrol.remotecontrol.threadcommunicationbase
    :members:
    :show-inheritance:


Command Item
------------

Communication Types:

- Request (Client->Server)
    - requesting value of a parameter
    - server will returning requested value
    - program flow:
        - send request string (maybe with argument e.g. for channel value)
        - interpret recived answer
- Command (Client->Server)
    - requesting chnage of a prameter
    - server may return a confirmation or the updated value
    - program flow:
        - send command string with or without additional argument
        - interprete recived answer if ther is one
- Event/Answer (Server->Client)
    - server sends status chanches to Client
    - program flow:
        - interprete recived event string/object


.. automodule:: viewcontrol.remotecontrol.commanditembase
    :members:
    :show-inheritance:


Process/Thread
--------------

.. automodule:: viewcontrol.remotecontrol.processcmd
    :members:
    :show-inheritance:


Protocols (Subpackages)
-----------------------

Supported devices are listed at TODO

TCP/IP
^^^^^^

.. autoclass:: viewcontrol.remotecontrol.tcpip.threadcommunication.ThreadCommunicationBase
    :members:
    :show-inheritance:

Telnet
^^^^^^

.. autoclass:: viewcontrol.remotecontrol.telnet.threadcommunication.ThreadCommunicationBase
    :members:
    :show-inheritance:

Open Sound Protocol
^^^^^^^^^^^^^^^^^^^

..  .. automodule:: viewcontrol.remotecontrol.opensoundprotocol.threadcommunication
    :members:
    :show-inheritance:

