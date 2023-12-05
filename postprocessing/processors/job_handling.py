"""
    Handling of job execution.

    @copyright: 2014 Oak Ridge National Laboratory
"""
import logging
import subprocess
import os
import re


def local_submission(configuration, script, input_file, output_dir, out_log, out_err):
    """
    Run a script locally
    @param configuration: configuration object
    @param script: full path to the reduction script to run
    @param input_file: input file to pass along to the script
    @param output_dir: reduction output directory
    @param out_log: reduction log file
    @param out_err: reduction error file
    """
    cmd = "%s %s %s %s/" % (
        configuration.python_executable,
        script,
        input_file,
        output_dir,
    )
    logFile = open(out_log, "w")
    errFile = open(out_err, "w")
    if configuration.comm_only is False:
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=logFile,
            stderr=errFile,
            universal_newlines=True,
            cwd=output_dir,
        )
        proc.communicate()
    logFile.close()
    errFile.close()


def determine_success_local(configuration, out_err):
    """
    Determine whether we generated an error
    @param configuration: configuration object
    @param out_err: job error file
    """
    success = not os.path.isfile(out_err) or os.stat(out_err).st_size == 0
    data = {}
    if not success:
        # Go through each line and report the error message.
        # If we can't fine the actual error, report the last line
        last_line = None
        error_line = None
        # TODO in python3 this should be changed to a context manager
        fp = open(out_err, "r")
        for line in fp.readlines():
            if len(line.replace("-", "").strip()) > 0:
                last_line = line.strip()
            result = re.search("Error: (.+)$", line)
            if result is not None:
                error_line = result.group(1)
        fp.close()
        if error_line is None:
            error_line = last_line
        for item in configuration.exceptions:
            if re.search(item, error_line):
                success = True
                data["information"] = error_line
                logging.error("Reduction error ignored: %s", error_line)

        if not success:
            data["error"] = f"REDUCTION: {error_line}"

    return success, data
