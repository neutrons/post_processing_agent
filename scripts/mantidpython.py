#!/bin/env python
import os
import re
import subprocess
import sys

mantidRegExp=re.compile(r'/opt/.antid.*/bin')
def getMantidLoc(line):
    line = line.strip()
    if not line.startswith("sys.path"):
        return None
    mantidversion = mantidRegExp.findall(line)
    if len(mantidversion)==1:
        return mantidversion[0]
    else:
        return None

# testing for the extraction function
"""
print getMantidLoc("from mantid.simpleapi import ") # should be None
print getMantidLoc('sys.path.append(os.path.join("/opt/Mantid/bin"))') # HYS
print getMantidLoc("sys.path.insert(0,'/opt/Mantid/bin')") # REFL
print getMantidLoc('sys.path.append("/opt/mantidnightly/bin")') # NOM
"""

reductionScript=file(sys.argv[1], 'r')

mantidpath=None
for line in reductionScript:
    mantidpath=getMantidLoc(line)
    if mantidpath is not None:
        break
if mantidpath is None:
    print "Failed to determine mantid version from script: '%s'" \
        % sys.argv[1]
    print "Defaulting to system python"
    mantidpython='python'
else:
    mantidpython=os.path.join(mantidpath, "mantidpython")
    if not os.path.exists(mantidpython):
        raise RuntimeError("Failed to find launcher: '%s'" % mantidpython)

cmd=sys.argv[1:]
cmd.insert(0,mantidpython)
if mantidpath is not None:
    cmd.insert(1,"--classic")
subprocess.call(cmd)
