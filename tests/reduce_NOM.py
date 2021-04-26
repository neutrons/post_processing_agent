from __future__ import (absolute_import, division, print_function)
from glob import glob
import numpy as np
import os
import stat
import sys
import json
# sys.path.append("/opt/mantidnightly/bin")
from mantid.simpleapi import *  # noqa: E402
import mantid  # noqa: E402

######################################################################
########## user defined parameters t
resamplex = -6000
vanradius = 0.58
#wavelengthMin = 0.1
#wavelengthMax = 2.9
##### information for what runs to associate
calFileDefault = '/SNS/NOM/shared/CALIBRATION/2019_1_1B_CAL/NOM_calibrate_d131573_2019_08_18.h5'
#calFileDefault = '/SNS/NOM/shared/CALIBRATION/2019_1_1B_CAL/NOM_d131573_2019_09_05_shifter.h5'
charFile = '/SNS/NOM/shared/CALIBRATION/2019_1_1B_CAL/NOM_char_2018_05_29-rietveld.txt'
expiniFileDefault = "/SNS/NOM/IPTS-22783/shared/autoNOM/exp.ini"
# 0 means use the runs specified in the exp.ini
# -1 means turn off the correction
# specify files to be summed as a tuple or list
sampleBackRun = 0
vanRun = 0
vanBackRun = 0
##### information for PDF generation
# ranges for Q to be used in merging data for PDF - nan means us the data range
Qmin = [np.nan, np.nan, 2., np.nan, np.nan, np.nan]
Qmax = [10., 10., np.nan, 16., np.nan, 1.7]
deltaQ = .02
qmax_overall = 50.
qmin_fourier = .3  # setting this to zero uses all the data
qmax_fourier = 40.
fitting_order = 2   # order of polynomial to fit which divides the S(Q)
qmin_fitting = 20.  # should be after peaks die off
########## end of user defined parameters
######################################################################

print('Command Line Args: {}'.format(sys.argv[1:]))

eventFileAbs = sys.argv[1]
outputDir = sys.argv[2]
maxChunkSize = 8.
if len(sys.argv) > 3:
    maxChunkSize = float(sys.argv[3])

eventFile = os.path.split(eventFileAbs)[-1]
eventFile = eventFile.replace('/lustre', '')
nexusDir = eventFileAbs.replace(eventFile, '')
cacheDir = "/tmp"   # local disk to (hopefully) reduce issues
runNumber = eventFile.split('_')[1].split('.')[0]
configService = mantid.config
dataSearchPath = configService.getDataSearchDirs()
dataSearchPath.append(nexusDir)
configService.setDataSearchDirs(";".join(dataSearchPath))

# uncomment next line to delete cache files
#CleanFileCache(CacheDir=cacheDir, AgeInDays=0)

proposalDir = '/' + '/'.join(nexusDir.split('/')[1:4])
# look for calibration in the proposal directory
calFile = calFileDefault
calFileOptions = glob(os.path.join(proposalDir, 'NOM_calibrate*.h5'))
if len(calFileOptions) > 0:
    sorted(calFileOptions, key=lambda fname: os.path.getctime(fname))
    calFile = calFileOptions[-1]
del calFileOptions

# look for exp.ini in the proposal directory
expiniFilename = os.path.join(proposalDir, 'shared', 'autoNOM', 'exp.ini')
if not os.path.exists(expiniFilename):
    expiniFilename = expiniFileDefault
# change permission to 664
try:
    permission = stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH
    os.chmod(expiniFilename, permission)
except:
    pass
print("Using {}".format(expiniFilename))

# determine information for caching
wksp = LoadEventNexus(Filename=eventFileAbs, MetaDataOnly=True)
PDLoadCharacterizations(Filename=charFile,
                        ExpIniFilename=expiniFilename,
                        OutputWorkspace="characterizations")
PDDetermineCharacterizations(InputWorkspace=wksp,
                             Characterizations="characterizations",
                             BackRun=sampleBackRun,
                             NormRun=vanRun,
                             NormBackRun=vanBackRun)
charPM = mantid.PropertyManagerDataService.retrieve('__pd_reduction_properties')


def clearmem(keepname=None):
    # clear out memory
    def isSpecialName(name):
        return name in ['characterizations', 'PG3_cal', 'PG3_mask']
    names = [name for name in mtd.getObjectNames()
             if not isSpecialName(name)]
    for name in names:
        if keepname is not None and name == keepname:
            continue
        DeleteWorkspace(name)


def toJson(json_config, filename):
    for key in json_config.keys():
        value = json_config[key]
        if type(value).__module__ == 'numpy':
            if type(value[0]) == np.int32 or type(value[0]) == np.int64:
                value = [int(val) for val in value]
            else:
                value = list(value)
        json_config[key] = value

    print('Writing configuration to {}'.format(filename))
    with open(filename, 'w') as handle:
        json.dump(json_config, handle, indent=2)

json_config = {'Instrument': 'NOM',
               'Title': wksp.getTitle(),
               'Sample': {'Runs': str(runNumber),
                          'Background': {'Runs': charPM['container'].valueAsStr,
                                         'Background': {'Runs': charPM['empty_environment'].valueAsStr,
                                                        'Background': {'Runs': charPM['empty_instrument'].valueAsStr}},
                                         },
                          'Material': 'Si O2',  # TODO
                          'PackingFraction': 0.5,
                          'Geometry': {'Radius': 0.15,  # TODO
                                       'Height': 1.8},  # TODO
                          'AbsorptionCorrection': {'Type': 'Carpenter'},
                          'MultipleScatteringCorrection': {'Type': 'Carpenter'},
                          'InelasticCorrection': {'Type': 'Placzek',
                                                  'Order': '1st',
                                                  'Self': True,
                                                  'Interference': False,
                                                  'FitSpectrumWith': 'GaussConvCubicSpline',
                                                  'LambdaBinningForFit': [0.16, 0.04, 2.8],
                                                  'LambdaBinningForCalc': [0.16, 0.0001, 2.9]
                                                  },
                          },
               'Vanadium': {'Runs': charPM['vanadium'].valueAsStr,
                            'Background': {'Runs': charPM['vanadium_background'].valueAsStr},
                            'Material': 'V',
                            'MassDensity': 6.11,  # isn't this already in mantid?
                            'PackingFraction': 1.,
                            'Geometry': {'Radius': 0.2925,
                                         'Height': 1.8},
                            'AbsorptionCorrection': {'Type': 'Carpenter'},
                            'MultipleScatteringCorrection': {'Type': 'Carpenter'},
                            'InelasticCorrection': {'Type': 'Placzek',
                                                    'Order': '1st',
                                                    'Self': True,
                                                    'Interference': False,
                                                    'FitSpectrumWith': 'GaussConvCubicSpline',
                                                    'LambdaBinningForFit': [0.16, 0.04, 2.8],
                                                    'LambdaBinningForCalc': [0.1, 0.0001, 3.0]}
                            },
               'Calibration': {'Filename': calFile},
               'HighQLinearFitRange': .6,
               'Merging': {
                   'QBinning': [0.0, 0.02, 40.0],
                   'Characterizations': {'Filename': charFile},
                   'SumBanks': [3]},
               'CacheDir': cacheDir,
               'OutputDir': outputDir
               }

toJson(json_config, os.path.join(outputDir, 'NOM_%s.json' % str(runNumber)))
DeleteWorkspace(str(wksp))
DeleteWorkspace("characterizations")

# get back the runs to use so they can be explicit in the generated python script
sampleBackRun = charPM['container'].value[0]
vanRun = charPM['vanadium'].value[0]
vanBackRun = charPM['vanadium_background'].value[0]


# guess the default name of the sample output workspace from SNSPowderReduction
wksp_name = "NOM_"+runNumber

# just automatically focus all data into a single spectrum
CreateGroupingWorkspace(InstrumentName='NOMAD', OutputWorkspace='NOM_group', GroupDetectorsBy='All')

# process the run for total scattering
SNSPowderReduction(Filename=eventFile,
                   MaxChunkSize=maxChunkSize, PreserveEvents=True,
                   PushDataPositive='None',
                   CalibrationFile=calFile,
                   CharacterizationRunsFile=charFile,
                   BackgroundNumber=str(sampleBackRun),
                   VanadiumNumber=str(vanRun),
                   VanadiumBackgroundNumber=str(vanBackRun),
                   ExpIniFilename=expiniFilename,
                   RemovePromptPulseWidth=50,
                   ResampleX=resamplex,
                   BinInDspace=True,
                   FilterBadPulses=25.,
                   SaveAs="gsas fullprof topas",
                   CacheDir=cacheDir,
                   OutputDirectory=outputDir,
                   StripVanadiumPeaks=True,
                   VanadiumRadius=vanradius,
                   NormalizeByCurrent=True, FinalDataUnits="dSpacing")
SQ = wksp_name+'_SofQ'
RenameWorkspace(InputWorkspace=wksp_name, OutputWorkspace=SQ)
clearmem(keepname=SQ)

# process the run for Rietveld - must be done second, will be fast because of caching
SNSPowderReduction(Filename=eventFile,
                   MaxChunkSize=maxChunkSize, PreserveEvents=True,
                   PushDataPositive='AddMinimum',
                   CalibrationFile=calFile,
                   CharacterizationRunsFile=charFile,
                   BackgroundNumber=str(sampleBackRun),
                   VanadiumNumber=str(vanRun),
                   VanadiumBackgroundNumber=str(vanBackRun),
                   ExpIniFilename=expiniFilename,
                   RemovePromptPulseWidth=50,
                   ResampleX=resamplex,
                   BinInDspace=True,
                   FilterBadPulses=25.,
                   SaveAs="gsas fullprof topas",
                   CacheDir=cacheDir,
                   OutputDirectory=outputDir,
                   StripVanadiumPeaks=True,
                   VanadiumRadius=vanradius,
                   NormalizeByCurrent=True, FinalDataUnits="dSpacing")

# save the processing script
GeneratePythonScript(InputWorkspace=wksp_name,
                     Filename=os.path.join(outputDir, wksp_name+'.py'))

ConvertUnits(InputWorkspace=wksp_name,
             OutputWorkspace=wksp_name, Target="dSpacing")

# create second workspace for ad-hoc PDF
Gr = wksp_name+'_Gofr'
ConvertUnits(InputWorkspace=SQ,
             OutputWorkspace=SQ, Target="MomentumTransfer")

# bin everything to the same place
binning = (max(mtd[SQ].readX(0)[0], qmin_fourier), deltaQ, qmax_overall)
print('binning in Q to {}'.format(binning))
Rebin(InputWorkspace=SQ, OutputWorkspace=SQ,
      Params=binning)

# Fit a polynomial to high-Q and divide by it
QfitRange = (qmin_fitting, qmax_overall)
if QfitRange[0] > QfitRange[1]:
    raise RuntimeError('Q-range is not possible: {} to {}'.format(QfitRange[0], QfitRange[1]))
if fitting_order == 2:
    Fit(InputWorkspace=SQ,
        Function='name=Quadratic,A0=1,A1=1,A2=0',
        StartX=QfitRange[0], EndX=QfitRange[1], Output='fittable').OutputParameters.column(1)[0]
    fitParams = mtd['fittable_Parameters']
    a0, a1, a2 = fitParams.cell(0, 1), fitParams.cell(1, 1), fitParams.cell(2, 1)
elif fitting_order == 1:
    Fit(InputWorkspace=SQ,
        Function='name=LinearBackground,A0=1,A1=0',
        StartX=QfitRange[0], EndX=QfitRange[1], Output='fittable').OutputParameters.column(1)[0]
    fitParams = mtd['fittable_Parameters']
    a0, a1, a2 = fitParams.cell(0, 1), fitParams.cell(1, 1), 0.
elif fitting_order == 0:
    Fit(InputWorkspace=SQ,
        Function='name=FlatBackground,A0=1',
        StartX=QfitRange[0], EndX=QfitRange[1], Output='fittable').OutputParameters.column(1)[0]
    fitParams = mtd['fittable_Parameters']
    a0, a1, a2 = fitParams.cell(0, 1), 0., 0.
else:
    raise RuntimeError('Do not know how to fit order={} polynomial'.format(order))
print('dividing by {} + {} * Q + {} * Q^2'.format(a0, a1, a2))
x = mtd[SQ].readX(0)
y = .5*(x[1:] + x[:-1])  # at this point it is actually x
y = a0 + a1 * y + a2 * y * y
CreateWorkspace(OutputWorkspace='fitted', DataX=x, DataY=y, UnitX='MomentumTransfer')
Divide(LHSWorkspace=SQ, RHSWorkspace='fitted', OutputWorkspace=SQ)
SaveNexusProcessed(InputWorkspace=SQ,
                   Filename=os.path.join(outputDir, 'NOM_'+runNumber+'_SQ.nxs'))

PDFFourierTransform(InputWorkspace=SQ, OutputWorkspace='Gr',
                    QMax=qmax_fourier,
                    #InputSofQType='S(Q)-1',
                    DeltaR=.02,
                    RMax=50.)
SavePDFGui(InputWorkspace='Gr',
           Filename=os.path.join(outputDir, 'NOM_'+runNumber+'.gr'))

# convert the data to Q[S(Q)-1]
print('converting to F(Q)')
ConvertToMatrixWorkspace(InputWorkspace=SQ, OutputWorkspace=SQ)
PDConvertReciprocalSpace(InputWorkspace=SQ, OutputWorkspace=SQ,
                         From='S(Q)', To='F(Q)')

# save a picture of the normalized ritveld data
banklabels = ['bank 1 - 15 deg',
              'bank 2 - 31 deg',
              'bank 3 - 67 deg',
              'bank 4 - 122 deg',
              'bank 5 - 154 deg',
              'bank 6 - 7 deg']
spectratoshow = [2, 3, 4, 5]

saveplot1d_args = dict(InputWorkspace=wksp_name,
                       SpectraList=spectratoshow,
                       SpectraNames=banklabels)

post_image = True
if post_image:
    html = ''
    div = SavePlot1D(OutputType='plotly', XLabel='d-spacing', **saveplot1d_args)
    html += '<div>{}</div>'.format(div)

    div = SavePlot1D(InputWorkspace=SQ, OutputType='plotly',
                     YLabel='Q[S(Q)-1]', XLabel='Q')
    html += '<div>{}</div>'.format(div)

    div = SavePlot1D(InputWorkspace='Gr', OutputType='plotly',
                     YLabel='G(r)', XLabel='r')
    html += '<div>{}</div>'.format(div)

    from finddata.publish_plot import publish_plot
    request = publish_plot('NOM', runNumber, files={'file': html})
    print("post returned %d" % request.status_code)
    print("resulting document:")
    print(request.text)
else:
    filename = os.path.join(outputDir, wksp_name + '.html')
    SavePlot1D(OutputFilename=filename, OutputType='plotly-full',
               **saveplot1d_args)
    print('saved', filename)

# remove cache files older than 14 days
CleanFileCache(CacheDir=cacheDir, AgeInDays=7)
