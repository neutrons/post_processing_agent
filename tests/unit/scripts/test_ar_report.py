from ar_report import GenericFile

import datetime
import h5py
import os
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


def test_generic_file():
    CONTENTS = "hello!"
    NOW = datetime.datetime.now()

    # create a file with non-empty contents
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as handle:
        handle.write(CONTENTS)
        handle.close()

        try:
            genericfile = GenericFile(handle.name)
            assert genericfile  # anything goes wrong and this is false
            assert len(genericfile.filename) > 0  # there was a file created
            assert genericfile.filename == handle.name

            # length is compatible with contents written
            assert genericfile.filesize == len(CONTENTS)
            pytest.approx(
                genericfile.filesizeMiB(), float(len(CONTENTS)) / 1024.0 / 1024.0
            )
            assert genericfile.filesizehuman() == f"{len(CONTENTS)}B"  # bytes

            # creation time is within 0.1s of when the test was started
            delta = genericfile.timeCreation - NOW
            assert abs(delta.total_seconds()) < 0.1
            # only up through the minutes are in GenericFile's representation
            assert genericfile.iso8601() == genericfile.timeCreation.isoformat()[:16]
        finally:
            # remove the temporary file
            os.unlink(handle.name)


def test_generic_file_empty():
    # create a file with empty contents
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as handle:
        handle.close()

        try:
            assert not GenericFile(handle.name)
        finally:
            # remove the temporary file
            os.unlink(handle.name)


logfile_path = "tests/unit/scripts/PG3_56301.nxs.log"


def test_ReductionLogFile():
    # reduction_log_file = ReductionLogFile(logfile_path, "PG3_56301")

    # assert reduction_log_file.mantidVersion ==
    # assert reduction_log_file.longestDuration ==
    # assert reduction_log_file.longestAlgorithm ==
    # assert reduction_log_file.loadDurationTotal ==
    # assert reduction_log_file.loadEventNexusDuration ==
    # assert reduction_log_file.started ==
    # assert reduction_log_file.host ==

    pass
