#!/bin/env python
import os
import re
import subprocess
import sys
import tempfile

mantidRegExp = re.compile(r'/opt/.antid.*/bin')

MANDID_VERSION = 'MANTID_VERSION='
CONDA_NAME = 'CONDA_ENV='
NSD_CONDA_WRAP = '/SNS/users/wzz/Projects/AutoReduction/nsd-app-wrap/nsd-conda-wrap.sh'

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
    # parse argument 1: reduction script
    reductionScript = open(sys.argv[1], 'r')

    # generate subprocess command to reduce data
    reduction_commands = generate_subprocess_command(reductionScript, sys.argv[2:], True)

    # call
    file_out = tempfile.NamedTemporaryFile(delete=False)
    file_err = tempfile.NamedTemporaryFile(delete=False)
    out_name = file_out.name
    err_name = file_err.name
    return_code = subprocess.call(reduction_commands, stdout=file_out, stderr=file_err)
    file_out.close()
    file_err.close()

    # read
    fout = open(out_name, 'r')
    print(fout.readlines())
    fout.close()
    os.remove(out_name)

    ferr = open(err_name, 'r')
    print(ferr.readlines())
    ferr.close()
    os.remove(err_name)
    print('Return code: {}'.format(return_code))


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
    elif len(conda_env_names) == 1:
        # conda environment
        conda_env_name = conda_env_names[0]
        cmd = ['bash', '-i', NSD_CONDA_WRAP, conda_env_name]
    elif len(mantid_paths) == 1:
        # user specified mantid python
        mantidpython = os.path.join(mantid_paths[0], "mantidpython")
        if not os.path.exists(mantidpython) and verify_mantid_path:
            raise RuntimeError("Failed to find launcher: '%s'" % mantidpython)
        cmd = [mantidpython, "--classic"]
    else:
        # no mantid path is specified: use standard python3
        print("Failed to determine mantid version from script: '{}'\n"
              "Defaulting to system python".format(reduce_script))
        cmd = ['python3']

    # construct sub process command
    cmd.append(reduce_script)
    cmd.extend(reduction_params)

    return cmd


if __name__ == '__main__':
    main()
