#!/bin/env python
import os
import subprocess
import sys

reductionScript=file(sys.argv[1], 'r')

mantidpath=None
for line in reductionScript:
    if line.startswith(r'sys.path.append("/opt/'):
        mantidpath=line.replace(r'sys.path.append(','') \
                    .replace(r')','')[1:-2].strip()
        break
if mantidpath is None:
    raise RuntimeError("Failed to determine mantid version from script: %s" \
                       % sys.argv[1])

mantidpython=os.path.join(mantidpath, "mantidpython")
if not os.path.exists(mantidpython):
    raise RuntimeError("Failed to find launcher: '%s'" % mantidpython)

cmd=sys.argv[1:]
cmd.insert(0,mantidpython)
subprocess.call(cmd)