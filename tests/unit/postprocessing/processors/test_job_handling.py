from postprocessing.processors.job_handling import (
    local_submission,
    determine_success_local,
)
from postprocessing.Configuration import Configuration

import os
import pytest
import sys
import tempfile


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
