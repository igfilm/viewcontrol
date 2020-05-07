#!/usr/bin/env python
from __future__ import unicode_literals

# # Execute with
# # $ python viewcontrol/__main__.py (2.6+)
# # $ python -m viewcontrol          (2.7+)
from __future__ import unicode_literals
import sys

if __package__ is None and not hasattr(sys, "frozen"):
    # direct call of __main__.py
    import os.path

    path = os.path.realpath(os.path.abspath(__file__))
    print(path)
    sys.path.insert(0, os.path.dirname(os.path.dirname(path)))

from viewcontrol.viewcontrol import ViewControl

if __name__ == "__main__":
    ViewControl(sys.argv).main()
