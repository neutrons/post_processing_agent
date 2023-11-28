from postprocessing.processors.job_handling import determine_success_local

from postprocessing.Configuration import Configuration
import tempfile

import pytest


@pytest.mark.parametrize("", [])
def test_local_submission(
    mocker, configuration, script, input_file, output_dir, out_log, out_err
):
    pass


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
