#!/usr/bin/env python

# imports section
import sys, os, glob, filecmp, datetime, shutil

try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser
sys.path.insert(0, "/opt/mantidnightly/bin")
sys.path.insert(0, "/opt/mantidnightly/lib")
sys.path.append("/SNS/CNCS/shared/autoreduce")
import copy_script

from ARLibrary import *  # note that ARLibrary would set mantidpath as well

from mantid.simpleapi import *
import numpy as np
import scipy.optimize as opt
import scipy.interpolate as interp

import mantid

mantid.kernel.config.setFacility("SNS")
# parameters section
# this part changes with web input
MaskBTPParameters = []
MaskBTPParameters.append({"Pixel": "121-128"})
MaskBTPParameters.append({"Pixel": "1-8"})
MaskBTPParameters.append({"Bank": "36-50"})

# MaskBTPParameters.append({'Pixel': '1-43,95-128'})
# MaskBTPParameters.append({'Pixel': '1-7,122-128'})
# MaskBTPParameters.append({'Bank': '36-50'})#8T magnet
raw_vanadium = "/SNS/CNCS/IPTS-26786/nexus/CNCS_386574.nxs.h5"
processed_vanadium = "van_386574.nxs"
VanadiumIntegrationRange = [
    49501.0,
    50501.0,
]  # integration range for Vanadium in TOF at 1.0 meV
grouping = "8x2"  # allowed values 1x1, 2x1, 4x1, 8x1, 8x2 powder
Emin = "-0.95"
Emax = "0.95"
Estep = "0.005"
E_pars_in_mev = False
TIB_min = ""
TIB_max = ""
doTIB = True
T0 = ""
Motor_names = "omega"
Temperature_names = (
    "SampleTemp,sampletemp,SensorB,SensorA,temp5,temp8,sensor0normal,SensorC,Temp4"
)
create_elastic_nxspe = False  # +-0.1Ei, 5 steps
create_MDnxs = False
a = "8.355"
b = "8.355"
c = "9.076"
alpha = "90.0"
beta = "90.0"
gamma = "120.0"
uVector = "-1.46299,-1.46299,8.50124"
vVector = "3.91295,3.91295,3.17848"
sub_directory = "/tmp"
auto_tzero_flag = False

# parameters not on the webpage
# below remains unchanged
NormalizedVanadiumEqualToOne = True
configfile = "config.ini"


def change_permissions(filename, permission):
    try:
        os.chmod(filename, permission)
    except OSError:
        pass


# Reduction section
def check_newer_script(instrument, folder):
    """
    Checks if reduce_instrument.py is in a certain folder.
    It searches for all reduce_instrument*.py, takes the newest one and compares the content with
    /SNS/instrument/shared/autoreduce/reduce_instrument.py. If there is no such file in the folder,
    or the content has changed, it will copy reduce_instrument.py to reduce_instrument_date_and_time.py
    in folder.
    """
    master_filename = (
        "/SNS/" + instrument + "/shared/autoreduce/reduce_" + instrument + ".py"
    )
    # master_filename='/SNS/users/3y9/Desktop/reduce_CNCS.py'
    search_pattern = os.path.join(folder, "reduce_" + instrument + "*.py")
    result = glob.glob(search_pattern)
    newer_file_exists = True
    if result:
        # there are reduce_... files, get the newest
        newest_filename = max(result, key=os.path.getctime)
        # check content. If the same, then there is no newer file
        newer_file_exists = not filecmp.cmp(master_filename, newest_filename)
    if newer_file_exists:
        new_filename = os.path.join(
            folder,
            "reduce_"
            + instrument
            + "_"
            + datetime.datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
            + ".py",
        )
        shutil.copy2(master_filename, new_filename)
    return newer_file_exists


def preprocessVanadium(Raw, Processed, Parameters):
    if os.path.isfile(Processed):
        LoadNexus(Filename=Processed, OutputWorkspace="__VAN")
        dictvan = {"UseProcessedDetVan": "1", "DetectorVanadiumInputWorkspace": "__VAN"}
    else:
        LoadEventNexus(Filename=Raw, OutputWorkspace="__VAN", Precount=0)
        CropWorkspace(InputWorkspace="__VAN", OutputWorkspace="__VAN", XMax=2e5)
        for d in Parameters:
            MaskBTP(Workspace="__VAN", **d)
        dictvan = {
            "SaveProcessedDetVan": "1",
            "DetectorVanadiumInputWorkspace": "__VAN",
            "SaveProcDetVanFilename": Processed,
            "UseBoundsForDetVan": "1",
            "DetVanIntRangeHigh": VanadiumIntegrationRange[1],
            "DetVanIntRangeLow": VanadiumIntegrationRange[0],
            "DetVanIntRangeUnits": "TOF",
        }
    return dictvan


def preprocessData(filename):
    dictdata = {}
    __IWS = LoadEventNexus(filename)
    __IWS = CropWorkspace(InputWorkspace=__IWS, XMax=2e5)
    # this bit is for the ESS detector prototype
    # xmin,xmax=__IWS.readX(0)
    # __tmp=Rebin(InputWorkspace=__IWS,Params=str(xmin)+',1,'+str(xmax),PreserveEvents=False)
    # __tmp=ConvertToPointData(InputWorkspace=__tmp)
    # x=__tmp.readX(0)
    # y=__tmp.extractY()[-1024:,:]    # the last 1024 pixels but all bins
    # try:
    #    import h5py
    #    output_filename='/SNS/CNCS/IPTS-17219/shared/ESSdata/dat'+str(__IWS.getRunNumber())+'.h5'
    #    with h5py.File(output_filename,'w') as hf:
    #        hf.create_dataset('xarray',data=x,compression="gzip", compression_opts=9)
    #        hf.create_dataset('yarray',data=y,compression="gzip", compression_opts=9)
    # except:
    #    pass
    Ei = __IWS.getRun()["EnergyRequest"].firstValue()
    t0 = preprocesst0(Ei, __IWS)
    tibmin, tibmax = preprocessTIB(Ei, __IWS)
    ETransfer = preprocessEnergyTransfer(Ei)
    dictdata["SampleInputWorkspace"] = "__IWS"
    dictdata["SampleInputMonitorWorkspace"] = "__IWS"
    dictdata["UseIncidentEnergyGuess"] = "1"
    dictdata["IncidentEnergyGuess"] = Ei
    dictdata["TimeZeroGuess"] = t0
    dictdata["EnergyTransferRange"] = ETransfer
    dictdata["TimeIndepBackgroundSub"] = doTIB
    dictdata["TibTofRangeStart"] = tibmin
    dictdata["TibTofRangeEnd"] = tibmax
    dictdata["IncidentBeamNormalisation"] = "ByCurrent"
    return dictdata


def gaussian(x, mu, sig, scale, background):
    return background + scale * np.exp(
        -np.power(x - mu, 2.0) / (2 * np.power(sig, 2.0))
    )


def fittingt0(Eguess, ws):
    ws_clone = CloneWorkspace(ws)
    vertical_number_of_pixels = 10
    MaskBTP(
        Workspace="ws_clone",
        Pixel="1-{0},{1}-128".format(
            int(64.0 - vertical_number_of_pixels / 2.0),
            int(64.0 + vertical_number_of_pixels / 2.0),
        ),
    )
    MaskBTP(Workspace="ws_clone", Bank="34-39")
    instr = ws_clone.getInstrument()
    source = instr.getSource()
    sample = instr.getSample()
    L1 = sample.getDistance(source)
    vi = 437.4 * np.sqrt(Eguess)

    L2_list = []
    bank_indices = range(1, 51)
    for idx, chosen_bank in enumerate(bank_indices):
        bank = instr.getComponentByName("bank" + str(chosen_bank))[0]
        L2_list.append(bank.getDistance(sample))

    L2_ave = np.mean(L2_list)
    D = L1 + L2_ave
    t_elastic_no_offset = D / vi * 1e6

    # get into time space
    microseconds_to_bin = "5"
    TOF_ws = Rebin(InputWorkspace=ws_clone, Params=microseconds_to_bin)
    s = SumSpectra(InputWorkspace=TOF_ws)
    DeleteWorkspace(TOF_ws)
    TOF = s.readX(0)
    TOF = (TOF[:-1] + TOF[1:]) * 0.5
    I = s.readY(0)  # noqa: E741 this is a horrible variable name

    for i, val in enumerate(TOF):
        if val > t_elastic_no_offset:
            break

    I_sliced = I[
        i
        - int(250 / int(microseconds_to_bin)) : i
        + int(250 / int(microseconds_to_bin))
    ]
    TOF_sliced = TOF[
        i
        - int(250 / int(microseconds_to_bin)) : i
        + int(250 / int(microseconds_to_bin))
    ]
    if 0:
        try:
            initial_guess = (TOF_sliced[np.argmax(I_sliced)], 35.0, np.max(I_sliced), 0)
            popt, pcov = opt.curve_fit(gaussian, TOF_sliced, I_sliced, p0=initial_guess)
            elastic_position_fitted = popt[0]
            T0_fitted = elastic_position_fitted - t_elastic_no_offset
        except:  # noqa: E722
            initial_guess = (t_elastic_no_offset, 35.0, np.max(I), 0)
            popt, pcov = opt.curve_fit(gaussian, TOF, I, p0=initial_guess)
            elastic_position_fitted = popt[0]
            T0_fitted = elastic_position_fitted - t_elastic_no_offset
    else:
        T0_fitted = TOF_sliced[np.argmax(I_sliced)] - t_elastic_no_offset
    return T0_fitted


def tzero_interp(ei=12, mode=1):
    """
    ei in meV
    chopper modes: HF = 1, AI = 3, HR = 0
    return a t-zero in microseconds
    """

    run_cycle = "2019A"

    if mode == 1:  # HF
        HF_m3_tzero = np.load(
            "/SNS/CNCS/shared/BL5-scripts/{0}-m3-tzero-{1}.npy".format("HF", run_cycle)
        )
        HF_ei_tzero = np.load(
            "/SNS/CNCS/shared/BL5-scripts/{0}-ei-tzero-{1}.npy".format("HF", run_cycle)
        )
        HF_interp = interp.interp1d(HF_ei_tzero[::-1], HF_m3_tzero[::-1])
        try:
            return float(HF_interp(ei))
        except:  # noqa: E722
            return float(T0)
    elif mode == 3:  # AI
        AI_m3_tzero = np.load(
            "/SNS/CNCS/shared/BL5-scripts/{0}-m3-tzero-{1}.npy".format("AI", run_cycle)
        )
        AI_ei_tzero = np.load(
            "/SNS/CNCS/shared/BL5-scripts/{0}-ei-tzero-{1}.npy".format("AI", run_cycle)
        )
        AI_interp = interp.interp1d(AI_ei_tzero[::-1], AI_m3_tzero[::-1])
        try:
            return float(AI_interp(ei))
        except:  # noqa: E722
            return float(T0)
    elif mode == 0:  # HR
        HR_m3_tzero = np.load(
            "/SNS/CNCS/shared/BL5-scripts/{0}-m3-tzero-{1}.npy".format("HR", run_cycle)
        )
        HR_ei_tzero = np.load(
            "/SNS/CNCS/shared/BL5-scripts/{0}-ei-tzero-{1}.npy".format("HR", run_cycle)
        )
        HR_interp = interp.interp1d(HR_ei_tzero[::-1], HR_m3_tzero[::-1])
        try:
            return float(HR_interp(ei))
        except:  # noqa: E722
            return float(T0)
    else:  # unknown
        return 0


def preprocesst0(Eguess, ws):
    if auto_tzero_flag:
        t0 = fittingt0(Eguess, ws)
    else:
        try:
            # t0=float(T0)
            mode = ws.run()["DoubleDiskMode"].timeAverageValue()
            _Ei, _FMP, _FMI, t0 = GetEi(ws)
            t0 = tzero_interp(_Ei, mode)
        except ValueError:
            mode = ws.run()["DoubleDiskMode"].timeAverageValue()
            _Ei, _FMP, _FMI, t0 = GetEi(ws)
            if mode != 1:
                t0 -= 5.91
    AddSampleLog(
        Workspace=ws, LogName="CalculatedT0", LogText=str(t0), LogType="Number"
    )
    return t0


def preprocessTIB(EGuess, ws):
    try:
        tibmin = float(TIB_min)
        tibmax = float(TIB_max)
    except ValueError:
        if EGuess < 50:
            tibmin, tibmax = SuggestTibCNCS(EGuess)
        else:
            tibmin = 5000
            tibmax = 15000
        if abs(EGuess - 12) < 0.1:
            tibmin, tibmax = [21900.0, 22580.0]
    AddSampleLogMultiple(ws, "TIBmin,TIBmax", str(tibmin) + "," + str(tibmax))
    return (tibmin, tibmax)


def preprocessEnergyTransfer(EGuess):
    try:
        emin = float(Emin)
        emax = float(Emax)
        estep = float(Estep)
        if E_pars_in_mev:
            return [emin, estep, emax]
        else:
            return [emin * EGuess, estep * EGuess, emax * EGuess]
    except ValueError:
        return [-0.5 * EGuess, 0.01 * EGuess, 0.95 * EGuess]


def preprocessGrouping(ws, outdir):
    if grouping in ["2x1", "4x1", "8x1", "8x2"]:
        dictgrouping = {
            "GroupingFile": "/SNS/CNCS/shared/autoreduce/CNCS_" + grouping + ".xml"
        }
    elif grouping == "powder":
        GroupingFilename = outdir + "powdergroupfile.xml"
        ParFilename = outdir + "powdergroupfile.par"
        GenerateGroupingPowder(
            InputWorkspace=ws, AngleStep=0.5, GroupingFilename=GroupingFilename
        )
        dictgrouping = {"GroupingFile": GroupingFilename}
        change_permissions(GroupingFilename, 0o664)
        change_permissions(ParFilename, 0o664)
    else:
        dictgrouping = {"GroupingFile": ""}
    return dictgrouping


def get_colorscale_minimum(arr):
    x = arr[np.isfinite(arr)]
    x = x[x > 0]
    xc = x[np.argsort(x)][int(len(x) * 0.02)]  # ignore the bottom 2%
    return xc


if __name__ == "__main__":
    # check number of arguments
    if len(sys.argv) != 3:
        print("autoreduction code requires a filename and an output directory")
        sys.exit()
    if not (os.path.isfile(sys.argv[1])):
        print("data file ", sys.argv[1], " not found")
        sys.exit()

    config["default.facility"] = "SNS"
    nexus_file = sys.argv[1]
    output_directory = sys.argv[2]

    ar_changed = check_newer_script("CNCS", output_directory)
    # create the autoreduction plotting setup script
    copy_script.copy_gui_script("CNCS", output_directory)
    # DownloadInstrument(ForceUpdate=True)

    cfgfile_path = os.path.join(output_directory, configfile)
    if not os.path.isfile(cfgfile_path):
        sub_directory = ""
        cfg = ConfigParser.ConfigParser()
        cfg.add_section("Reduction config")
        cfg.set("Reduction config", "subdirectory", sub_directory)
        with open(cfgfile_path, "w") as f:
            cfg.write(f)
        change_permissions(cfgfile_path, 0o664)
    else:
        if ar_changed:
            cfg = ConfigParser.ConfigParser()
            cfg.add_section("Reduction config")
            cfg.set("Reduction config", "subdirectory", sub_directory)
            with open(cfgfile_path, "w") as f:
                cfg.write(f)
            change_permissions(cfgfile_path, 0o664)
        else:
            cfg = ConfigParser.ConfigParser()
            cfg.read(cfgfile_path)
            sub_directory = cfg.get("Reduction config", "subdirectory")
    sub_directory = sub_directory.strip()

    DGSdict = preprocessVanadium(
        raw_vanadium, output_directory + processed_vanadium, MaskBTPParameters
    )
    datadict = preprocessData(nexus_file)
    groupdict = preprocessGrouping("__IWS", output_directory)
    DGSdict.update(datadict)
    DGSdict.update(groupdict)
    DGSdict["OutputWorkspace"] = "reduce"

    DgsReduction(**DGSdict)

    if "SaveProcessedDetVan" in DGSdict.keys() and NormalizedVanadiumEqualToOne:
        filename = DGSdict["SaveProcDetVanFilename"]
        change_permissions(filename, 0o664)
        LoadNexus(Filename=filename, OutputWorkspace="__VAN")
        datay = mtd["__VAN"].extractY()
        meanval = float(datay[datay > 0].mean())
        CreateSingleValuedWorkspace(OutputWorkspace="__meanval", DataValue=meanval)
        Divide(
            LHSWorkspace="__VAN", RHSWorkspace="__meanval", OutputWorkspace="__VAN"
        )  # Divide the vanadium by the mean
        Multiply(
            LHSWorkspace="reduce", RHSWorkspace="__meanval", OutputWorkspace="reduce"
        )  # multiple by the mean of vanadium Normalized data = Data / (Van/meanvan) = Data *meanvan/Van
        SaveNexus(InputWorkspace="__VAN", Filename=filename)
        change_permissions(filename, 0o664)

    if create_elastic_nxspe:
        DGSdict["OutputWorkspace"] = "reduce_elastic"
        EGuess = DGSdict["IncidentEnergyGuess"]
        DGSdict["EnergyTransferRange"] = [-0.1 * EGuess, 0.04 * EGuess, 0.1 * EGuess]
        DgsReduction(**DGSdict)

    elog = ExperimentLog()
    elog.setLogList("EnergyRequest,CalculatedT0,TIBmin,TIBmax")
    elog.setSimpleLogList("EnergyRequest,CalculatedT0,TIBmin,TIBmax")
    elog.setSERotOptions(Motor_names)
    elog.setSETempOptions(Temperature_names)
    elog.setFilename(output_directory + "experiment_log.csv")

    run_number = mtd["reduce"].getRun()["run_number"].value
    s1, temp = elog.save_line("reduce")
    roundedvalue = "_%.1f_%.1f" % (s1, temp)
    valuestringwithoutdot = str(roundedvalue).replace(".", "p")
    if groupdict["GroupingFile"] == output_directory + "powdergroupfile.xml":
        roundedvalue = "_powder_%.1f" % temp
        valuestringwithoutdot = str(roundedvalue).replace(".", "p")
        nxspe_filename = os.path.join(
            output_directory,
            "inelastic",
            sub_directory,
            "CNCS_" + run_number + valuestringwithoutdot + ".nxspe",
        )
        SaveNXSPE(
            Filename=nxspe_filename,
            InputWorkspace="reduce",
            Psi="0",
            KiOverKfScaling="1",
            ParFile=output_directory + "powdergroupfile.par",
        )
        change_permissions(nxspe_filename, 0o664)
        if create_elastic_nxspe:
            nxspe_filename = os.path.join(
                output_directory,
                "elastic",
                sub_directory,
                "CNCS_" + run_number + valuestringwithoutdot + "_elastic.nxspe",
            )
            SaveNXSPE(
                Filename=nxspe_filename,
                InputWorkspace="reduce_elastic",
                Psi="0",
                KiOverKfScaling="1",
                ParFile=output_directory + "powdergroupfile.par",
            )
            change_permissions(nxspe_filename, 0o664)
    else:
        nxspe_filename = os.path.join(
            output_directory,
            "inelastic",
            sub_directory,
            "CNCS_" + run_number + valuestringwithoutdot + ".nxspe",
        )
        SaveNXSPE(
            Filename=nxspe_filename,
            InputWorkspace="reduce",
            Psi=str(s1),
            KiOverKfScaling="1",
        )
        change_permissions(nxspe_filename, 0o664)
        if create_elastic_nxspe:
            nxspe_filename = os.path.join(
                output_directory,
                "elastic",
                sub_directory,
                "CNCS_" + run_number + valuestringwithoutdot + "_elastic.nxspe",
            )
            SaveNXSPE(
                Filename=nxspe_filename,
                InputWorkspace="reduce_elastic",
                Psi=str(s1),
                KiOverKfScaling="1",
            )
            change_permissions(nxspe_filename, 0o664)

    if create_MDnxs:
        try:
            SetUB(
                "reduce",
                a=a,
                b=b,
                c=c,
                alpha=alpha,
                beta=beta,
                gamma=gamma,
                u=uVector,
                v=vVector,
            )
            SetGoniometer("reduce", Axis0=str(s1) + ",0,1,0,1")
            ConvertToMD(
                InputWorkspace="reduce",
                QDimensions="Q3D",
                dEAnalysisMode="Direct",
                Q3DFrames="HKL",
                QConversionScales="HKL",
                OutputWorkspace="md",
            )
            filename = os.path.join(
                output_directory,
                "MD",
                sub_directory,
                "CNCS_" + run_number + valuestringwithoutdot + "_MD.nxs",
            )
            SaveMD(Filename=filename, InputWorkspace="md")
            change_permissions(filename, 0o664)
        except:  # noqa: E722
            mantid.kernel.logger.information("Problems converting to MD")
