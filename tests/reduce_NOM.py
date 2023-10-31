from __future__ import absolute_import, division, print_function
import numpy as np

# sys.path.append("/opt/mantidnightly/bin")
from mantid.simpleapi import *  # noqa: E402

######################################################################
########## user defined parameters t
resamplex = -6000
vanradius = 0.58
# wavelengthMin = 0.1
# wavelengthMax = 2.9
##### information for what runs to associate
calFileDefault = (
    "/SNS/NOM/shared/CALIBRATION/2019_1_1B_CAL/NOM_calibrate_d131573_2019_08_18.h5"
)
# calFileDefault = '/SNS/NOM/shared/CALIBRATION/2019_1_1B_CAL/NOM_d131573_2019_09_05_shifter.h5'
charFile = "/SNS/NOM/shared/CALIBRATION/2019_1_1B_CAL/NOM_char_2018_05_29-rietveld.txt"
expiniFileDefault = "/SNS/NOM/IPTS-22783/shared/autoNOM/exp.ini"
# 0 means use the runs specified in the exp.ini
# -1 means turn off the correction
# specify files to be summed as a tuple or list
sampleBackRun = 0
vanRun = 0
vanBackRun = 0
##### information for PDF generation
# ranges for Q to be used in merging data for PDF - nan means us the data range
Qmin = [np.nan, np.nan, 2.0, np.nan, np.nan, np.nan]
Qmax = [10.0, 10.0, np.nan, 16.0, np.nan, 1.7]
deltaQ = 0.02
qmax_overall = 50.0
qmin_fourier = 0.3  # setting this to zero uses all the data
qmax_fourier = 40.0
fitting_order = 2  # order of polynomial to fit which divides the S(Q)
qmin_fitting = 20.0  # should be after peaks die off
########## end of user defined parameters
######################################################################

raise RuntimeError("Below is trimmed for testing")
