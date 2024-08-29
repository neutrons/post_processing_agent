from postprocessing.processors.job_handling import (
    local_submission,
    determine_success_local,
    terminate_or_kill_process_tree,
)
from postprocessing.Configuration import Configuration

import logging
import os
import psutil
import pytest
import subprocess
import sys
import tempfile
import time


@pytest.mark.parametrize(
    "script, output_expected, error_expected",
    [
        (b"print('test')", b"test\n", b""),
        (b"raise Exception('forceError')", b"", b"Exception: forceError"),
    ],
)
def test_local_submission(mocker, script, output_expected, error_expected):
    mock_configuration = mocker.Mock(spec=Configuration)
    mock_configuration.python_executable = sys.executable
    mock_configuration.comm_only = False
    mock_configuration.system_mem_limit_perc = 60.0
    mock_configuration.mem_check_limit_sec = 0.5

    tempFile_script = tempfile.NamedTemporaryFile()
    tempFile_input = tempfile.NamedTemporaryFile()
    tempFile_output = tempfile.NamedTemporaryFile()
    tempFile_error = tempfile.NamedTemporaryFile()

    tempFile_script.write(script)

    tempFile_script.seek(0)
    tempFile_input.seek(0)
    tempFile_output.seek(0)
    tempFile_error.seek(0)

    local_submission(
        mock_configuration,
        tempFile_script.name,
        tempFile_input.name,
        os.path.dirname(tempFile_output.name),
        tempFile_output.name,
        tempFile_error.name,
    )

    assert output_expected == tempFile_output.read()
    assert error_expected in tempFile_error.read()


@pytest.mark.parametrize(
    "configuration, out_err, success_expected, data_expected",
    [
        ([], b"", True, {}),
        ([], b"regex not found", False, {"error": "REDUCTION: regex not found"}),
        ([], b"Error: regex found", False, {"error": "REDUCTION: regex found"}),
        (
            ["exception"],
            b"Error: regex found, exception handled",
            True,
            {"information": "regex found, exception handled"},
        ),
    ],
)
def test_determine_success_local(
    mocker, configuration, out_err, success_expected, data_expected
):
    configuration_mock = mocker.Mock(spec=Configuration)
    configuration_mock.exceptions = configuration

    with tempfile.NamedTemporaryFile() as error_file:
        error_file.write(out_err)
        error_file.seek(0)

        success, data = determine_success_local(configuration_mock, error_file.name)
        assert success == success_expected
        assert data == data_expected


def test_memory_limit(mocker, tmp_path, caplog):
    """Test monitoring memory usage and terminating a job that exceeds the usage limit"""
    mock_configuration = mocker.Mock(spec=Configuration)
    mock_configuration.python_executable = sys.executable
    mock_configuration.comm_only = False
    mock_configuration.exceptions = []
    # set too small memory limit of 1 MiB
    mock_configuration.system_mem_limit_perc = 100.0 * (
        1024 * 1024 / psutil.virtual_memory().total
    )
    mock_configuration.mem_check_interval_sec = 0.05

    # Modify log level to capture memory usage debug log
    caplog.set_level(logging.DEBUG)

    # Script that will consume a lot of memory
    script = """import numpy as np
import time
while True:
    _ = np.random.rand(100000, 1000)
    time.sleep(1)
    """
    tmp_file_script = tmp_path / "script.py"
    tmp_file_script.write_text(script)
    tmp_file_input = tmp_path / "in"
    tmp_file_output = tmp_path / "out"
    tmp_file_error = tmp_path / "err"

    local_submission(
        mock_configuration,
        tmp_file_script,
        tmp_file_input,
        tmp_file_output.parent,
        tmp_file_output,
        tmp_file_error,
    )
    assert "Subprocess memory usage" in caplog.text
    assert "Total memory usage exceeded limit" in caplog.text

    # Verify that a message was added in the reduction error log
    success, status_data = determine_success_local(mock_configuration, tmp_file_error)
    assert not success
    assert "error" in status_data
    assert "Total memory usage exceeded limit" in status_data["error"]


def test_terminate_or_kill_process_tree(tmp_path):
    """Test function terminate_or_kill_process tree for process with child process"""
    script = """
import subprocess
import time

subprocess.run(["python", "-c", "import time; time.sleep(10); print('Child Process')"])
time.sleep(30)  # Keep parent process alive
"""

    parent_script_file = tmp_path / "script.py"
    parent_script_file.write_text(script)

    # Start the parent process that starts a child process
    proc = subprocess.Popen(["python", parent_script_file.as_posix()])
    time.sleep(2)
    parent_psutil = psutil.Process(proc.pid)

    # Store list of started processes
    procs_psutil = parent_psutil.children(recursive=True)
    procs_psutil.append(parent_psutil)

    # Try to terminate the processes
    terminate_or_kill_process_tree(proc.pid)

    # Verify processes were terminated
    for p in procs_psutil:
        try:
            assert p.status() == psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            pass
