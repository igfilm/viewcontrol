viewcontrol.playback
====================

The playback package controls the playback of all media. At the moment in containes only one module.

Process/Thread MpvProcess
-------------------------

The processmpv module starts the mpv-player with the python-mpv package in its own thread. Commands are passed via Queues. New files can be appended to the player playlist at any time by passing a (String, float or None) tuple. Also the commands "pause", "resume" and "next" are supported.

.. note::
    python-mpv will raise an error if no element is left in the players playlist and next is called.

The class can be started as threading.Thread or multiprocessing.Process. This is done by implementing two dummy (ProcessMpv, ThreadMpv) classes which pass the arguments to the CommandProcess class and starts it in their run function. Since the communication is only done via Queues and Events which are similar at threading/queue and multiprocessing.

.. autoclass:: viewcontrol.playback.processmpv.ProcessMpv
    :members:
    :show-inheritance:

.. autoclass:: viewcontrol.playback.processmpv.ThreadMpv
    :members:
    :show-inheritance:

.. autoclass:: viewcontrol.playback.processmpv.MpvProcess
    :members:
    :show-inheritance:
