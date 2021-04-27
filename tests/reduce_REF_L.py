"""
    Auto-reduction script for the Liquids Reflectometer
    For reference:
        Type 0: Normal sample data
        Type 1: Direct beams for scaling factors
        Type 2: Zero-attenuator direct beams
        Type 3: Data that we don't need to treat
"""
import sys
import os
import json
import warnings
warnings.simplefilter('ignore', RuntimeWarning)


if ("MANTIDPATH" in os.environ):
    del os.environ["MANTIDPATH"]
#sys.path.insert(0,"/opt/mantid50/bin")
#sys.path.insert(1,"/opt/mantid50/lib")
sys.path.insert(0,"/opt/mantidnightly/bin")
sys.path.insert(1,"/opt/mantidnightly/lib")

import mantid
from mantid.simpleapi import *

try:
    from sf_calculator import ScalingFactor
    DIRECT_BEAM_CALC_AVAILABLE = True
    logger.notice("sf_calculator available")
except:
    import scipy
    logger.notice("Scaling factor calculation upgrade not available: scipy=%s" % scipy.__version__)
    DIRECT_BEAM_CALC_AVAILABLE = False

event_file_path=sys.argv[1]
output_dir=sys.argv[2]

event_file = os.path.split(event_file_path)[-1]
# The legacy format is REF_L_xyz_event.nxs
# The new format is REF_L_xyz.nxs.h5
run_number = event_file.split('_')[2]
run_number = run_number.replace('.nxs.h5', '')

raise RuntimeError('Below is trimmed for testing')
