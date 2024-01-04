import h5py
import pytest
import shutil
import tempfile


@pytest.fixture(scope="function")
def nexus_file():
    sns_dir = tempfile.mkdtemp(prefix="SNS")
    instrument_dir = tempfile.mkdtemp(dir=sns_dir)
    proposal_dir = tempfile.mkdtemp(prefix="IPTS-", dir=instrument_dir)
    nexus_dir = tempfile.mkdtemp(dir=proposal_dir)

    nexus_file = tempfile.NamedTemporaryFile(suffix=".nxs.h5", dir=nexus_dir)

    with h5py.File(nexus_file.name, "w") as handle:
        entry = handle.create_group("entry")

        entry.create_dataset("start_time", data=["test", "test"])
        entry.create_dataset("end_time", data=["test", "test"])

    yield nexus_file

    shutil.rmtree(sns_dir)


@pytest.fixture(scope="function")
def output_dir():
    output_dir = tempfile.mkdtemp()
    yield output_dir
    shutil.rmtree(output_dir)


# def test_main_new(nexus_file, output_dir):
#    main(nexus_file.name, output_dir)
#    pass


def test_main_append():
    pass


def test_main_argError():
    pass


logfile_path = "tests/unit/scripts/PG3_56301.nxs.log"


def test_ReductionLogFile():
    pass
    # reduction_log_file = ReductionLogFile(logfile_path, "PG3_56301.nxs.log")

    # assert reduction_log_file.mantidVersion ==
    # assert reduction_log_file.longestDuration ==
    # assert reduction_log_file.longestAlgorithm ==
    # assert reduction_log_file.loadDurationTotal ==
    # assert reduction_log_file.loadEventNexusDuration ==
    # assert reduction_log_file.started ==
    # assert reduction_log_file.host ==
