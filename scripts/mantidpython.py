#!/bin/env python
import os
import re
import subprocess
import sys


mantidRegExp = re.compile(r'/opt/.antid.*/bin')

MANDID_VERSION = 'MANTID_VERSION='
CONDA_NAME = 'CONDA_ENV='

mantid_version_dict = {'nightly': "/opt/mantidnightly/bin",
                       'stable': "/opt/Mantid/bin"}


def get_mantid_loc(line):
    """Get Mantid bin or mantid python location

    MANTID_VERSION='nightly'  # returns "/opt/mantidnightly/bin"
    MANTID_VERSION='60'       # returns "/opt/mantid60/bin"
    MANTID_VERSION='stable'   # returns "/opt/Mantid/bin"

    CONDA_ENV='sasview'
    CONDA_ENV='imaging'

    Parameters
    ----------
    line: str
        one line in auto reduction file

    Returns
    -------
    ~tuple
        mantid python location (None for not found), conda env name (None for not found)

    """
    line = line.strip()
    if line.startswith("sys.path"):
        # backward compatible: sys.path.append or sys.path.insert
        mantidversion = mantidRegExp.findall(line)
        print('Mantid version: {}'.format(mantidversion))
        if len(mantidversion) == 1:
            return mantidversion[0], None

    elif line.startswith(MANDID_VERSION):
        #  specify mantid version as: 50, 60, nightly, stable
        mantid_version = line.split(MANDID_VERSION)[1].split()[0].replace('"', '').replace("'", '')
        if mantid_version in mantid_version_dict:
            # label: nightly, stable
            return mantid_version_dict[mantid_version], None
        else:
            # version number
            return '/opt/mantid{}/bin'.format(mantid_version), None

    elif line.startswith(CONDA_NAME):
        # CONDA name
        conda_name = line.split(CONDA_NAME)[1].split()[0].replace("'", '').replace('"', '')
        return None, conda_name

    return None, None


def main():

    reductionScript = open(sys.argv[1], 'r')

    mantidpath=None
    for line in reductionScript:
        mantidpath = get_mantid_loc(line)
        if mantidpath is not None:
            break
    if mantidpath is None:
        print("Failed to determine mantid version from script: '%s'" % sys.argv[1])
        print("Defaulting to system python")
        mantidpython='python3'
    else:
        mantidpython = os.path.join(mantidpath, "mantidpython")
        if not os.path.exists(mantidpython):
            raise RuntimeError("Failed to find launcher: '%s'" % mantidpython)
    reductionScript.close()

    cmd=sys.argv[1:]
    cmd.insert(0,mantidpython)
    if mantidpath is not None:
        cmd.insert(1,"--classic")
    print('Command: {}'.format(cmd))
    subprocess.call(cmd)


def generate_subprocess_command(reduce_script, reduction_params, verify_mantid_path=True):
    """Search reduction script for specific
    - mantid python version or
    - conda environment name
    and construct the command (in list) for subprocess

    Parameters
    ----------
    reduce_script
    reduction_params: ~list
        reduction script arguments after reduction script
    verify_mantid_path: bool


    Returns
    -------
    ~list
        auto reduction command for subprocess

    """
    # Go through auto reduction script to locate (mantid) python path
    # use list to check whether there are multiple mantid python path or conda environment
    # are specified, which is not permitted
    mantid_paths = list()
    conda_env_names = list()

    script_file = open(reduce_script, 'r')
    for line in script_file:
        # check mantid path with regular expression r'/opt/.antid.*/bin'
        mantid_path, conda_env_name = get_mantid_loc(line)
        if mantid_path is not None:
            mantid_paths.append(mantid_path)
        elif conda_env_name is not None:
            conda_env_names.append(conda_env_name)
    script_file.close()

    # Convert new mantid script path
    if len(mantid_paths) + len(conda_env_names) > 1:
        raise RuntimeError('Reduction script {} specifies multiple mantid python paths ({}) '
                           'and conda environments ({})'.format(reduce_script, mantid_paths, conda_env_names))
    elif len(mantid_paths) == 1:
        # user specified mantid python
        mantidpython = os.path.join(mantid_paths[0], "mantidpython")
        if not os.path.exists(mantidpython) and verify_mantid_path:
            raise RuntimeError("Failed to find launcher: '%s'" % mantidpython)
    elif len(conda_env_names) == 1:
        # conda environment
        mantidpython = 'python'
        conda_env_name = conda_env_names[0]
    else:
        # no mantid path is specified: use standard python3
        print("Failed to determine mantid version from script: '{}'\n"
              "Defaulting to system python".format(reduce_script))
        mantidpython = 'python3'

    # construct sub process command
    cmd = [reduce_script]
    cmd.extend(reduction_params)
    cmd.insert(0, mantidpython)
    if len(mantid_paths) == 1:
        cmd.insert(1, "--classic")

    return cmd
