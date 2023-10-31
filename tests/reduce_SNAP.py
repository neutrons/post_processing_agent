#!/usr/bin/env python
from __future__ import absolute_import, division, print_function, unicode_literals

import sys, os

sys.path.append("/opt/mantidnightly/bin")
import mantid
from mantid.simpleapi import *

eventFileAbs = sys.argv[1]
outputDir = sys.argv[2] + "/"

eventFile = os.path.split(eventFileAbs)[-1]
nexusDir = eventFileAbs.replace(eventFile, "")
runNumber = eventFile.split("_")[1].split(".")[0]

configService = mantid.config
dataSearchPath = configService.getDataSearchDirs()
dataSearchPath.append(nexusDir)
configService.setDataSearchDirs(";".join(dataSearchPath))

raise RuntimeError("Below is trimmed for testing")
