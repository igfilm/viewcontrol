viewcontrol.remotecontrol
=========================


Fundamentals
------------

There are 3 different communication types how the client (this program) is communicating with the server (the devices):

- Request (Client->Server)
    - requesting value of a parameter
    - server will returning requested value
    - program flow:
        - send request string (maybe with argument e.g. for channel value)
        - interpret received answer
- Command (Client->Server)
    - requesting change of a parameter
    - server may return a confirmation or the updated value
    - program flow:
        - send command string with or without additional argument
        - interpret received answer if there is one
- Event/Answer (Server->Client)
    - server sends status chances to Client
    - program flow:
        - interpret received event string/object

Each device is its own thread in which all processing is done. Commands send und messages received are passed in Command Items send over queues. Available commands for each device are stored in Command Templates. See the appropriate sections for more information.


Command Items
-------------

For sending a ``CommandSendItem`` and receiving a ``CommandRecvItem`` are used which are passed over the Queue. The actual command properties are stored in ``CommandTemplate`` which are stored in the class attribute dict_command_template of each device. The device and command name are used to send the command to the appropriate device with the matching command.

.. autoclass:: viewcontrol.remotecontrol.commanditem.CommandSendItem
    :members:
    :show-inheritance:

.. autoclass:: viewcontrol.remotecontrol.commanditem.CommandRecvItem
    :members:
    :show-inheritance:


Command Templates
-----------------

The properties of every command are defined in CommandTemplates, which can be loaded from a YAML file and are stored in the CommandTemplateList (it is a dict).


Rules for YAML:

1) there must be an answer_analysis for all commands/requests expecting a response, even if its identical to the composition (can't be tested)
2) all attributes must be there
3) if there is an answer_analysis there must be a argument_mappings too, except when there a nor parser groups in answer_analysis
4) the formatter string must be valid and can be indexed (not tested)
5) the formatter string must have less or equal arguments than in the argument_mapping (this is for OSC the case)
6) the regex string must be valid and
7) must have less or equal capture groups that the argument mapping (this is for OSC the case, too)
8) mapping dict
    a) dict keys must be str and are displayed as label of options
    b) dict values can be of types list, dict and one of the strings 'int', 'float'
        - list: elements must have the same type, can be duplicates, but makes no sense
        - dict: keys must be string, values must have the same type and can be duplicates
        - str: are must be in list and are used for type casting of answers

.. important::
    in the current state of the package, CommandTemplates must be in the CommandTemplateList to be passable through queues. This is because only the command name is stored in the CommandItems.


.. autoclass:: viewcontrol.remotecontrol.commanditem.CommandTemplate
    :members:
    :show-inheritance:


.. autoclass:: viewcontrol.remotecontrol.commanditem.CommandTemplateList
    :members:
    :show-inheritance:

Devices
-------

For each device a new python module in the appropriate protocol package is created and the device class is derived from ThreadCommunication (protocol namespace). Optionally a Dictionary with CommandTemplates can be created in the data folder a which must have the same name as the file the device class is defined in.

Each Communication interface is started in its own thread, this way, the waiting for incoming massages can be blocking. Each Protocols/Devices thread class is derived from th Communication is derived from ``viewcontrol.remotecontrol.threadcommunicationbase``. Which also handles connection errors and writing into the log. All child Protocols/Devices just need to overwrite the ``listen()`` method with the Protocol/Device specific code for communication.

Since only one Device per Protocol is supported at the moment, bigger changes in the ThreadCommunication class are very likely.

.. autoclass:: viewcontrol.remotecontrol.threadcommunicationbase.ThreadCommunicationBase
    :members:
    :show-inheritance:

.. autoclass:: viewcontrol.remotecontrol.threadcommunicationbase.DeviceType
    :members:
    :show-inheritance:


Process/Thread CommandProcess
-----------------------------

The class can be started as ``threading.Thread`` or ``multiprocessing.Process``. This is done by implementing two dummy (``ProcessCmd``, ``ThreadCmd``) classes which pass the arguments to the ``CommandProcess`` class and starts it in their run function. Since the communication is only done via Queues and Events which are similar at threading/queue and multiprocessing.

.. autoclass:: viewcontrol.remotecontrol.processcmd.ProcessCmd
    :members:
    :show-inheritance:

.. autoclass:: viewcontrol.remotecontrol.processcmd.ThreadCmd
    :members:
    :show-inheritance:

.. autoclass:: viewcontrol.remotecontrol.processcmd.CommandProcess
    :members:
    :show-inheritance:


