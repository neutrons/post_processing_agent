#!/bin/env python
import os
import re
import subprocess
import sys

# reg expression to parse mantid python on analysis cluster
mantidRegExp = re.compile(r"/opt/.antid.*/bin")

# variable to specify mantid version
MANDID_VERSION = "MANTID_VERSION"
# mapping from mantid version to mantid library location on analysis cluster
mantid_version_dict = {"nightly": "/opt/mantidnightly/bin", "stable": "/opt/Mantid/bin"}

# variable to specify conda environment name
CONDA_NAME = "CONDA_ENV"
# where the conda wrapper lives
NSD_CONDA_WRAP = "/usr/bin/nsd-conda-wrap.sh"


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

    def parse_var_value(string, var_name):
        var_string = string.split(var_name)[1].strip()
        if var_string.startswith("="):
            # split = and get first variable after =
            var_string = (
                var_string.split("=")[1]
                .strip()
                .split()[0]
                .replace('"', "")
                .replace("'", "")
            )
            return var_string

        return None

    line = line.strip()
    if line.startswith("sys.path"):
        # backward compatible: sys.path.append or sys.path.insert
        mantidversion = mantidRegExp.findall(line)
        if len(mantidversion) == 1:
            print("Mantid version: {}".format(mantidversion))
            return mantidversion[0], None

    elif line.startswith(MANDID_VERSION):
        # specify mantid version as: 50, 60, nightly, stable
        mantid_version = parse_var_value(line, MANDID_VERSION)

        if mantid_version is None:
            # not in MANTID_VERSION = ... mode
            return None, None
        elif mantid_version in mantid_version_dict:
            # label: nightly, stable
            return mantid_version_dict[mantid_version], None
        else:
            # version number
            return "/opt/mantid{}/bin".format(mantid_version), None

    elif line.startswith(CONDA_NAME):
        # CONDA name
        conda_name = parse_var_value(line, CONDA_NAME)

        if conda_name is None:
            # not in CONDA = ... mode
            return None, None

        return None, conda_name

    return None, None


def main():
    if len(sys.argv) < 4:
        print(
            "Usage: {} <reduction_script> <nexusfile> <outputdirectory>".format(
                sys.argv[0]
            )
        )
        sys.exit(1)

    # parse argument 1: reduction script
    reduction_script = sys.argv[1]

    # generate subprocess command to reduce data
    reduction_commands = generate_subprocess_command(
        reduction_script, sys.argv[2:], True
    )

    # call
    print(" ".join(reduction_commands))
    return_code = subprocess.call(reduction_commands)
    sys.exit(return_code)


def generate_subprocess_command(
    reduce_script, reduction_params, verify_mantid_path=True
):
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

    with open(reduce_script, "r") as script_file:
        for line in script_file:
            # check mantid path with regular expression r'/opt/.antid.*/bin'
            mantid_path, conda_env_name = get_mantid_loc(line)
            if mantid_path is not None:
                mantid_paths.append(mantid_path)
            elif conda_env_name is not None:
                conda_env_names.append(conda_env_name)

    # Convert new mantid script path
    if len(mantid_paths) + len(conda_env_names) > 1:
        raise RuntimeError(
            "Reduction script {} specifies multiple mantid python paths ({}) "
            "and conda environments ({})".format(
                reduce_script, mantid_paths, conda_env_names
            )
        )
    elif len(conda_env_names) == 1:
        # conda environment
        conda_env_name = conda_env_names[0]
        print("Using {} conda environment".format(conda_env_name))
        cmd = [NSD_CONDA_WRAP, conda_env_name, "--classic"]
    elif len(mantid_paths) == 1:
        # user specified mantid python
        mantidpython = os.path.join(mantid_paths[0], "mantidpython")
        if not os.path.exists(mantidpython) and verify_mantid_path:
            raise RuntimeError("Failed to find launcher: '%s'" % mantidpython)
        cmd = [mantidpython, "--classic"]
    else:
        # no mantid path is specified: use standard python3
        print(
            "Failed to determine mantid version from script: '{}'\n"
            "Defaulting to system python".format(reduce_script)
        )
        cmd = ["python3"]

    # construct sub process command
    cmd.append(reduce_script)
    cmd.extend(reduction_params)

    return cmd


if __name__ == "__main__":
    main()
