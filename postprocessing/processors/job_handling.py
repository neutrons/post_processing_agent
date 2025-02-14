"""
    Handling of job execution.

    @copyright: 2014 Oak Ridge National Laboratory
"""
import logging
import subprocess
import os
import re
import time
import psutil

CONVERSION_FACTOR_BYTES_TO_MB = 1.0 / (1024 * 1024)


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
    # Get process memory usage limit
    mem_limit_mb = get_memory_limit_mb(configuration)
    # Get process time limit
    time_limit_sec = get_time_limit_sec(configuration)
    with open(out_log, "w") as logFile, open(out_err, "w") as errFile:
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
            start_time = time.time()
            proc_psutil = psutil.Process(proc.pid)

            # Monitor the elapsed time and the total memory usage of the subprocess and its children
            try:
                terminate = False
                while proc.poll() is None:  # process is still running
                    total_mem_usage_mb = (
                        get_total_memory_usage(proc_psutil)
                        * CONVERSION_FACTOR_BYTES_TO_MB
                    )
                    elapsed_time = time.time() - start_time
                    logging.debug(
                        f"Subprocess memory usage: {total_mem_usage_mb} MiB. Max limit: {mem_limit_mb} MiB."
                    )
                    logging.debug(
                        f"Elapsed time: {elapsed_time} s. Max time limit: {time_limit_sec} s."
                    )

                    if total_mem_usage_mb > mem_limit_mb:
                        err_message = f"Total memory usage exceeded limit ({total_mem_usage_mb / 1024:2f} GiB > {mem_limit_mb / 1024:2f} GiB). Terminating job."
                        terminate = True
                    elif elapsed_time > time_limit_sec:
                        err_message = f"Time limit exceeded ({elapsed_time:2f} s > {time_limit_sec:2f} s). Terminating job."
                        terminate = True

                    if terminate:
                        logging.warning(err_message)
                        # Terminate process and its child processes
                        terminate_or_kill_process_tree(proc.pid)
                        # Add message in the run reduction error log file
                        errFile.write(err_message)
                        break

                    time.sleep(configuration.mem_check_interval_sec)

                proc.wait()

            except psutil.NoSuchProcess:
                logging.warning("The process has already terminated.")

            except Exception as e:
                logging.error(f"An error occurred: {e}")

            finally:
                proc.communicate()


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
        with open(out_err, "r") as fp:
            for line in fp.readlines():
                if len(line.replace("-", "").strip()) > 0:
                    last_line = line.strip()
                result = re.search("Error: (.+)$", line)
                if result is not None:
                    error_line = result.group(1)
        if error_line is None:
            error_line = last_line
        for item in configuration.exceptions:
            if re.search(item, error_line):
                success = True
                data["information"] = error_line
                logging.error("Reduction error ignored: %s", error_line)

        if not success:
            data["error"] = f"REDUCTION: {error_line}"
            logging.error(f"REDUCTION: {error_line}")

    return success, data


def get_memory_limit_mb(configuration):
    """
    Get the memory limit in Megabytes based on a percentage of the available system memory
    @param Configuration configuration: configuration
    @return float: memory limit in MB
    """
    mem_total = psutil.virtual_memory().total
    mem_fraction = configuration.system_mem_limit_perc / 100.0
    return mem_total * mem_fraction * CONVERSION_FACTOR_BYTES_TO_MB


def get_time_limit_sec(configuration):
    """
    Get the task time limit in seconds
    @param Configuration configuration: configuration
    @return float: time in seconds
    """
    return configuration.task_time_limit_minutes * 60.0


def get_total_memory_usage(proc):
    """
    Get the total memory usage in bytes of process ``proc`` and its children
    @param Popen proc: process
    @return float: memory usage in bytes
    """
    # Start with the memory usage of the parent process
    total_memory = proc.memory_info().rss
    # Iterate through all child processes and add their memory usage
    for child in proc.children(recursive=True):
        total_memory += child.memory_info().rss
    return total_memory


def terminate_or_kill_process_tree(pid, timeout=3):
    """Terminate or, if unsuccessful, kill process and its children
    @param int pid: process ID
    @param int timeout: timeout in seconds
    """

    def on_terminate(proc):
        warn_msg = ""
        if proc.pid != pid:
            warn_msg += "child "
        warn_msg += f"process {proc} terminated with exit code {proc.returncode}"
        logging.warning(warn_msg)

    parent = psutil.Process(pid)
    procs = parent.children(recursive=True)
    procs.append(parent)
    # Send SIGTERM
    for p in procs:
        p.terminate()
    gone, alive = psutil.wait_procs(procs, timeout=timeout, callback=on_terminate)
    if alive:
        # Send SIGKILL
        for p in alive:
            logging.warning(f"process {p} survived SIGTERM; trying SIGKILL")
            p.kill()
        gone, alive = psutil.wait_procs(alive, timeout=timeout, callback=on_terminate)
        if alive:
            # Give up
            for p in alive:
                logging.warning(f"process {p} survived SIGKILL; giving up")
