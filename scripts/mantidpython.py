#!/usr/bin/env python3
import subprocess
import sys

# variable to specify conda environment name
CONDA_NAME = "CONDA_ENV"
# where the conda wrapper lives
NSD_CONDA_WRAP = "/usr/bin/nsd-conda-wrap.sh"


def get_conda_env(line):
    """Get conda environment name from a line in the reduction script

    CONDA_ENV='sasview'
    CONDA_ENV='imaging'

    Parameters
    ----------
    line: str
        one line in auto reduction file

    Returns
    -------
    str or None
        conda environment name (None if not found)

    """

    def parse_var_value(string, var_name):
        var_string = string.split(var_name)[1].strip()
        if var_string.startswith("="):
            # split = and get first variable after =
            var_string = var_string.split("=")[1].strip().split()[0].replace('"', "").replace("'", "")
            return var_string

        return None

    line = line.strip()
    if line.startswith(CONDA_NAME):
        # CONDA name
        conda_name = parse_var_value(line, CONDA_NAME)
        return conda_name

    return None


def main():
    if len(sys.argv) < 4:
        print("Usage: {} <reduction_script> <nexusfile> <outputdirectory>".format(sys.argv[0]))
        sys.exit(1)

    # parse argument 1: reduction script
    reduction_script = sys.argv[1]

    # generate subprocess command to reduce data
    reduction_commands = generate_subprocess_command(reduction_script, sys.argv[2:], True)

    # call
    print(" ".join(reduction_commands))
    return_code = subprocess.call(reduction_commands)
    sys.exit(return_code)


def generate_subprocess_command(reduce_script, reduction_params, verify_mantid_path=True):
    """Search reduction script for conda environment name
    and construct the command (in list) for subprocess

    Parameters
    ----------
    reduce_script
    reduction_params: ~list
        reduction script arguments after reduction script
    verify_mantid_path: bool
        unused parameter kept for backward compatibility

    Returns
    -------
    ~list
        auto reduction command for subprocess

    Raises
    ------
    RuntimeError
        If no CONDA_ENV is specified or multiple CONDA_ENVs are specified

    """
    # Go through auto reduction script to locate conda environment
    conda_env_names = list()

    with open(reduce_script, "r") as script_file:
        for line in script_file:
            # check for conda environment specification
            conda_env_name = get_conda_env(line)
            if conda_env_name is not None:
                conda_env_names.append(conda_env_name)

    # Enforce single conda environment requirement
    if len(conda_env_names) == 0:
        raise RuntimeError(
            f"Reduction script {reduce_script} does not specify a CONDA_ENV. "
            "A conda environment must be specified using 'CONDA_ENV=<environment_name>'."
        )
    elif len(conda_env_names) > 1:
        raise RuntimeError(
            f"Reduction script {reduce_script} specifies multiple conda environments: {conda_env_names}. "
            "Only one CONDA_ENV may be specified."
        )

    # Use the single conda environment
    conda_env_name = conda_env_names[0]
    print(f"Using {conda_env_name} conda environment")
    cmd = [NSD_CONDA_WRAP, conda_env_name, "--classic"]

    # construct sub process command
    cmd.append(reduce_script)
    cmd.extend(reduction_params)

    return cmd


if __name__ == "__main__":
    main()
