#!/usr/bin/env python
from __future__ import (absolute_import, division, print_function, unicode_literals)

import sys,os
sys.path.append("/opt/mantidnightly/bin")
import mantid
from mantid.simpleapi import *

eventFileAbs=sys.argv[1]
outputDir=sys.argv[2]+'/'

eventFile = os.path.split(eventFileAbs)[-1]
nexusDir = eventFileAbs.replace(eventFile, '')
runNumber = eventFile.split('_')[1].split('.')[0]

configService = mantid.config
dataSearchPath = configService.getDataSearchDirs()
dataSearchPath.append(nexusDir)
configService.setDataSearchDirs(";".join(dataSearchPath))


######################################################################
# EDITABLE PARAMETERS
######################################################################
binning='0.7, -0.0015, 6.0'

extras = {} # to supply other properties for filenames

### Masking should be one of the following strings :
#masking = 'None'
masking = 'Horizontal'
#masking = 'Vertical'
#masking = 'Masking Workspace'
#masking = 'Custom - xml masking file'
#extras['MaskingFilename'] = '/SNS/SNAP/IPTS-26217/shared/Mask_vI.xml'

### Calibration  should be one of the following strings :
# 'Convert Units' or  'Calibration File'
calibration = 'Convert Units'
#calibration = 'Calibration File'
#calibration = 'DetCal File'
#extras['CalibrationFilename'] = '/SNS/SNAP/shared/Calibration/Mantid/SNAP_calibrate_d30628_2016_02_19.cal'
#extras['DetCalFilename'] = '/SNS/SNAP/IPTS-26217/shared/E76p2_W65p3.DetCal'

### Grouping  should be one of the following strings :
grouping = 'All'
#grouping = 'Column'
#grouping = 'Banks'
#grouping = 'Modules'
#grouping = '2_4 Grouping'

### normalization  should be one of the following strings :
#normalization = 'None'
#normalization = 'From Workspace'
#normalization = 'From Processed Nexus'
normalization = 'Extracted from Data'
#norm_file = 'nor_nexus.nxs'

### Modify the chunking when loading the events file
extras['MaxChunkSize'] = 0

######################################################################
# EDITABLE PARAMETERS END
# ====================================================================
# DO NOT EDIT BELOW THIS POINT
######################################################################

# reduce the data
SNAPReduce(RunNumbers=runNumber,
           Masking=masking,
           Calibration=calibration,
           Binning=binning,
           Normalization=normalization,
           GroupDetectorsBy=grouping,
           ProcessingMode='Production',
           SaveData=True,
           PeakClippingWindowSize=12, 
           SmoothingRange=5,
           OutputDirectory=outputDir,
           **extras)

# determine the name of the workspace to plot
wkspNames = mantid.AnalysisDataService.getObjectNames()
wkspNames = [item for item in wkspNames
             if 'SNAP_' + runNumber in item]
print('Workspace names (will use first):', wkspNames)
GeneratePythonScript(InputWorkspace=wkspNames[0],
                     Filename=os.path.join(outputDir, 'python', wkspNames[0] + '.py'))

# generate the plot
div = SavePlot1D(Inputworkspace=wkspNames[0],
                 OutputType='plotly',
                 XLabel='d-spacing (A)')

# post the image
try: # version on autoreduce
    from postprocessing.publish_plot import publish_plot
except ImportError: # version on instrument computers
    from finddata.publish_plot import publish_plot
request = publish_plot('SNAP', runNumber, files={'file':div})
print("post returned %d" % request.status_code)
print("resulting document:")
print(request.text)
