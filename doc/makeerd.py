from eralchemy import render_er

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from viewcontrol.show import Base

path_dir = os.path.dirname(os.path.realpath(__file__))
path_file = os.path.join(path_dir, 'erd.png')
print("saved diagram under: '{}'".format(path_file))
render_er(Base, path_file)

#other possible output formats
#filename = os.path.join(path_dir, 'erd.er')
#render_er(Base, path_file)
#filename = os.path.join(path_dir, 'erd.dot')
#render_er(Base, path_file)