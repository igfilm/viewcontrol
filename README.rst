viewcontrol
===========

Lightweight program for playback of various image media formats with seamless transitions and control via Ethernet connected devices and DMX.

This software is currently being developed to create a fully automatic cinema-like playback, running on a single board computer and controlling devices connected via Ethernet.

Quick Start
-----------

Install
^^^^^^^

.. code-block:: bash

    $ git clone https://github.com/igfilm/viewcontrol.git && cd viewcontrol
    $ python3 -m venv .venv && source .venv/bin/activate  # optional
    $ pip install -r requirements.txt`

Run
^^^

.. code-block:: bash

    $ source .venv/bin/activate  # optional
    $ python3 -m viewcontrol <project folder> <options>


Supported Devices
-----------------

* Atlona OME-SW32 (Telnet)
* Denon DN500-BD (TCP/IP)

Planned
^^^^^^^
* Behringer X32 (OSC)
