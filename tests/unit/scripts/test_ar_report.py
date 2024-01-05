from scripts.ar_report import *

import datetime
import h5py
import os
from pathlib import Path
import pytest
import shutil
import tempfile


# data directory is inside of tests/
DATA_DIREC = Path(__file__).parent.parent.parent / "data"
INPUT_LOGFILE = DATA_DIREC / "PG3_56301.nxs.h5.log"

# this should resolve to PG3_56301, but we are making it dynamic so things stay consistent
SHORT_NAME = os.path.split(INPUT_LOGFILE)[-1].split(".")[0]
# for comparing contents in junk reduction logs
ZERO_STR = "0.0"


@pytest.fixture(scope="function")
def nexus_file():
    start_time = "starting-time"
    end_time = "starting-time"

    sns_dir = tempfile.mkdtemp(prefix="SNS")
    instrument_dir = tempfile.mkdtemp(dir=sns_dir)
    proposal_dir = tempfile.mkdtemp(prefix="IPTS-", dir=instrument_dir)
    nexus_dir = tempfile.mkdtemp(prefix="nexus", dir=proposal_dir)
    nexus_file = tempfile.NamedTemporaryFile(suffix=".nxs.h5", dir=nexus_dir)

    with h5py.File(nexus_file.name, "w") as handle:
        entry = handle.create_group("entry")

        entry.create_dataset(
            "start_time",
            data=[
                start_time,
            ],
        )
        entry.create_dataset(
            "end_time",
            data=[
                end_time,
            ],
        )

    yield {
        "filepath": Path(nexus_file.name),
        "start_time": start_time,
        "end_time": end_time,
    }


@pytest.fixture(scope="function")
def output_dir():
    output_dir = tempfile.mkdtemp()
    yield output_dir
    shutil.rmtree(output_dir)


########################################### unit tests of utility functions


def test_getPropDir(nexus_file):
    prop_dir_correct = str(nexus_file["filepath"]).split("/")
    prop_dir_correct = os.path.join("/", *prop_dir_correct[:5])

    prop_dir_test = getPropDir(str(nexus_file["filepath"]))

    assert prop_dir_test == prop_dir_correct


@pytest.mark.skip("not yet implemented")
def test_getRuns():
    pass


@pytest.mark.skip("not yet implemented")
def test_getOutFilename():
    pass


<<<<<<< HEAD
########################################### unit tests of GenericFile


def test_GenericFile():
=======
def test_generic_file():
>>>>>>> 6015614 (Add unit test for GenericFile)
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


<<<<<<< HEAD
def test_GenericFile_empty():
=======
def test_generic_file_empty():
>>>>>>> 6015614 (Add unit test for GenericFile)
    # create a file with empty contents
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as handle:
        handle.close()

        try:
            assert not GenericFile(handle.name)
        finally:
            # remove the temporary file
            os.unlink(handle.name)


<<<<<<< HEAD
########################################### unit tests of ReductionLogFile
=======
logfile_path = "tests/unit/scripts/PG3_56301.nxs.log"
>>>>>>> 6015614 (Add unit test for GenericFile)


def test_ReductionLogFile():
    # double check that the file didn't get moved
    assert INPUT_LOGFILE.exists(), str(INPUT_LOGFILE) + " does not exist"
    # parse the file
    reduction_log_file = ReductionLogFile(INPUT_LOGFILE, SHORT_NAME)
    assert reduction_log_file

    # taken from staring at the logs
    assert reduction_log_file.mantidVersion == "6.7.0"
    assert reduction_log_file.longestDuration == pytest.approx(
        2 * 60 + 3.72
    ), "longestDuration"
    assert reduction_log_file.longestAlgorithm == "SNSPowderReduction"
    assert reduction_log_file.host == "autoreducer3.sns.gov"
    assert reduction_log_file.started == "2023-08-16T13:36Z"

    # LoadEventNexus + Load + LoadDiffCal + LoadNexusProcessed + Load + Load + Load + LoadNexusProcessed + LoadNexusProcessed
    duration = 4.62 + 0.74 + 0.42 + 2.99 + 23.42 + 1.07 + 7.41 + 5.08 + 3.83
    assert reduction_log_file.loadDurationTotal == pytest.approx(
        duration
    ), "loadDurationTotal"
    assert reduction_log_file.loadEventNexusDuration == pytest.approx(
        4.62 + 0.74
    ), "loadEventNexusDuration"


def check_bad_ReductionLogFile_values(
    reduction_log_file,
    mantidVersion="UNKNOWN",
    host="UNKNOWN",
    started="UNKNOWN",
    longestAlgorithm="UNKNOWN",
):
    # fields are still the initial crappy values
    assert reduction_log_file.mantidVersion == mantidVersion, "mantidVersion"
    assert reduction_log_file.host == host, "host"
    assert reduction_log_file.started == started, "started"
    assert (
        reduction_log_file.longestAlgorithm == longestAlgorithm
    ), "longestAlgorithm"  # empty

    assert float(reduction_log_file.longestDuration) == pytest.approx(
        0.0
    ), "longestDuration"
    assert float(reduction_log_file.loadDurationTotal) == pytest.approx(
        0.0
    ), "loadDurationTotal"
    assert float(reduction_log_file.loadEventNexusDuration) == pytest.approx(
        0.0
    ), "loadEventNexusDuration"


def test_ReductionLogFile_partial_contents():
    # read in the first 8 lines from a "good" file
    assert INPUT_LOGFILE.exists(), str(INPUT_LOGFILE) + " does not exist"
    with open(INPUT_LOGFILE) as handle:
        data = handle.readlines()
        data = data[:8]
        data = "".join(data)

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as handle:
        # write out those lines to the test logfile
        handle.write(data)
        handle.close()

        try:
            reduction_log_file = ReductionLogFile(handle.name, SHORT_NAME)

            # things that are in the file

            check_bad_ReductionLogFile_values(
                reduction_log_file,
                mantidVersion="6.7.0",
                host="autoreducer3.sns.gov",
                started="2023-08-16T13:36Z",
            )
        finally:
            # remove the temporary file
            os.unlink(handle.name)


def test_ReductionLogFile_empty_file():
    reduction_log_file = ReductionLogFile("non-existant-file.log", SHORT_NAME)
    assert not reduction_log_file  # it is invalid
    check_bad_ReductionLogFile_values(reduction_log_file)


def test_ReductionLogFile_junk_contents():
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as handle:
        handle.write("this is total junk\n")
        handle.close()

        try:
            reduction_log_file = ReductionLogFile(handle.name, SHORT_NAME)
            check_bad_ReductionLogFile_values(reduction_log_file)
        finally:
            # remove the temporary file
            os.unlink(handle.name)


########################################### unit tests of EventFile


def test_EventFile(nexus_file):
    # calculate what the prefix should be - normally <instr>_<runnum>
    prefix = str(nexus_file["filepath"].name).replace(".nxs.h5", "")

    eventfile = EventFile(nexus_file["filepath"].parent, nexus_file["filepath"].name)
    assert eventfile
    assert eventfile.shortname == nexus_file["filepath"].name
    assert str(eventfile) == prefix
    assert eventfile.isThisRun(str(nexus_file["filepath"].name))
    assert eventfile.timeStart == nexus_file["start_time"]
    assert eventfile.timeStop == nexus_file["end_time"]


########################################### unit tests of ARStatus


@pytest.mark.skip("not yet implemented")
def test_ARstatus(nexus_file):
    pass
