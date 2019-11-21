# viewcontrol
Lightweight program for playback of various image media formats with seamless transitions and control via Ethernet connected devices and DMX.

## Quick Start
### Install
 1) `$ git clone https://github.com/igfilm/viewcontrol.git && cd viewcontrol`
 2) `$ python3 -m venv .venv && source .venv/bin/activate`, optional
 3) `$ pip install -r requirements.txt`

### Run
1) `$ source .venv/bin/activate`, optional
2) `$ python3 -m viewcontrol <project folder> <options>`

A working show can be produced by running `$ python3 test/test_show.py`. The test folder 'testing' is not deleted.

## Show Entity Relationship Diagram
![Show ERD](https://github.com/igfilm/viewcontrol/blob/master/doc/erd.png "Show ERD")

## Suported Devices

* Atlona OME-SW32 (Telnet)
* Denon DN500-BD (TCP/IP)

*Planned*
* Behringer X32 (OSC)