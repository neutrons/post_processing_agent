from ar_report import *

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
    duration = 42.0

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
        entry.create_dataset("duration", (1,), data=[duration])

    yield {
        "filepath": Path(nexus_file.name),
        "start_time": start_time,
        "end_time": end_time,
        "duration": duration,
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


########################################### unit tests of GenericFile


def test_GenericFile():
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
            pytest.approx(genericfile.filesizeMiB(), float(len(CONTENTS)) / 1024.0 / 1024.0)
            assert genericfile.filesizehuman() == f"{len(CONTENTS)}B"  # bytes

            # creation time is within 0.1s of when the test was started
            delta = genericfile.timeCreation - NOW
            assert abs(delta.total_seconds()) < 0.1
            # only up through the minutes are in GenericFile's representation
            assert genericfile.iso8601() == genericfile.timeCreation.isoformat()[:16]
        finally:
            # remove the temporary file
            os.unlink(handle.name)


def test_GenericFile_empty():
    # create a file with empty contents
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as handle:
        handle.close()

        try:
            assert not GenericFile(handle.name)
        finally:
            # remove the temporary file
            os.unlink(handle.name)


########################################### unit tests of ReductionLogFile


def test_ReductionLogFile():
    # double check that the file didn't get moved
    assert INPUT_LOGFILE.exists(), str(INPUT_LOGFILE) + " does not exist"
    # parse the file
    reduction_log_file = ReductionLogFile(INPUT_LOGFILE, SHORT_NAME)
    assert reduction_log_file

    # taken from staring at the logs
    assert reduction_log_file.mantidVersion == "6.7.0"
    assert reduction_log_file.longestDuration == pytest.approx(2 * 60 + 3.72), "longestDuration"
    assert reduction_log_file.longestAlgorithm == "SNSPowderReduction"
    assert reduction_log_file.host == "autoreducer3.sns.gov"
    assert reduction_log_file.started == "2023-08-16T13:36Z"

    # LoadEventNexus + Load + LoadDiffCal + LoadNexusProcessed + Load + Load + Load + LoadNexusProcessed + LoadNexusProcessed
    duration = 4.62 + 0.74 + 0.42 + 2.99 + 23.42 + 1.07 + 7.41 + 5.08 + 3.83
    assert reduction_log_file.loadDurationTotal == pytest.approx(duration), "loadDurationTotal"
    assert reduction_log_file.loadEventNexusDuration == pytest.approx(4.62 + 0.74), "loadEventNexusDuration"


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
    assert reduction_log_file.longestAlgorithm == longestAlgorithm, "longestAlgorithm"  # empty

    assert float(reduction_log_file.longestDuration) == pytest.approx(0.0), "longestDuration"
    assert float(reduction_log_file.loadDurationTotal) == pytest.approx(0.0), "loadDurationTotal"
    assert float(reduction_log_file.loadEventNexusDuration) == pytest.approx(0.0), "loadEventNexusDuration"


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
    assert eventfile.duration == nexus_file["duration"]


########################################### unit tests of ARStatus


def test_ARstatus_reduxTime_no_valid_logfiles():
    """Test reduxTime when no logfiles have valid start/finish times"""
    # Create a mock ARstatus object with logfiles that don't have valid times

    # Create temporary directory structure
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create shared/autoreduce directory
        shared_dir = os.path.join(temp_dir, "shared", "autoreduce")
        os.makedirs(shared_dir)

        # Create reduction_log directory
        log_dir = os.path.join(shared_dir, "reduction_log")
        os.makedirs(log_dir)

        # Create a mock event file
        event_file = type(
            "MockEventFile",
            (),
            {
                "shortname": "TEST_123",
                "isThisRun": lambda self, name: name.startswith("TEST_123"),
            },
        )()

        # Create log file with no valid algorithm times
        log_file_path = os.path.join(log_dir, "TEST_123.log")
        with open(log_file_path, "w") as f:
            f.write("This is Mantid version 6.7.0\n")
            f.write("Some log content without algorithm timing info\n")

        # Create ARstatus instance
        ar_status = ARstatus(shared_dir, event_file)

        # Test reduxTime - should return 0.0 when no valid logfiles
        assert ar_status.reduxTime == 0.0


def test_ARstatus_reduxTime_with_valid_logfiles():
    """Test reduxTime when logfiles have valid start/finish times"""

    # Create temporary directory structure
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create shared/autoreduce directory
        shared_dir = os.path.join(temp_dir, "shared", "autoreduce")
        os.makedirs(shared_dir)

        # Create reduction_log directory
        log_dir = os.path.join(shared_dir, "reduction_log")
        os.makedirs(log_dir)

        # Create a mock event file
        event_file = type(
            "MockEventFile",
            (),
            {
                "shortname": "TEST_123",
                "isThisRun": lambda self, name: name.startswith("TEST_123"),
            },
        )()

        # Create log file with valid algorithm timing info
        log_file_path = os.path.join(log_dir, "TEST_123.log")
        with open(log_file_path, "w") as f:
            f.write("This is Mantid version 6.7.0\n")
            f.write("running on autoreducer3.sns.gov starting 2023-08-16T13:36Z\n")
            f.write("LoadEventNexus-[Information] Execution Date: 2023-08-16 13:36:10.123456\n")
            f.write("LoadEventNexus-[Notice] LoadEventNexus successful, Duration 4.62 seconds\n")
            f.write("SNSPowderReduction-[Information] Execution Date: 2023-08-16 13:36:15.789012\n")
            f.write("SNSPowderReduction-[Notice] SNSPowderReduction successful, Duration 2 minutes 3.72 seconds\n")

        # Create ARstatus instance
        ar_status = ARstatus(shared_dir, event_file)

        # Test reduxTime - should calculate duration between first start and last finish
        redux_time = ar_status.reduxTime
        assert redux_time > 0.0
        # Should be approximately 2 minutes 9.34 seconds (difference between start times + last duration)
        expected_time = 5.665556 + (2 * 60 + 3.72)  # time diff + duration of last algorithm
        assert abs(redux_time - expected_time) < 1.0  # Allow 1 second tolerance


def test_ARstatus_properties():
    """Test various properties of ARstatus class"""
    # Create temporary directory structure
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create shared/autoreduce directory
        shared_dir = os.path.join(temp_dir, "shared", "autoreduce")
        os.makedirs(shared_dir)

        # Create reduction_log directory
        log_dir = os.path.join(shared_dir, "reduction_log")
        os.makedirs(log_dir)

        # Create some reduced files
        reduced_file1 = os.path.join(shared_dir, "TEST_123_reduced.nxs")
        reduced_file2 = os.path.join(shared_dir, "TEST_123_peaks.integrate")
        with open(reduced_file1, "w") as f:
            f.write("reduced data")
        with open(reduced_file2, "w") as f:
            f.write("peaks data")

        # Create a mock event file
        event_file = type(
            "MockEventFile",
            (),
            {
                "shortname": "TEST_123",
                "isThisRun": lambda self, name: name.startswith("TEST_123"),
            },
        )()

        # Create log file
        log_file_path = os.path.join(log_dir, "TEST_123.log")
        with open(log_file_path, "w") as f:
            f.write("This is Mantid version 6.7.0\n")
            f.write("running on autoreducer3.sns.gov starting 2023-08-16T13:36Z\n")
            f.write("LoadEventNexus-[Notice] LoadEventNexus successful, Duration 4.62 seconds\n")

        # Create ARstatus instance
        ar_status = ARstatus(shared_dir, event_file)

        # Test properties
        assert ar_status.host == "autoreducer3.sns.gov"
        assert ar_status.mantidVersion == "6.7.0"
        assert ar_status.logstarted == "2023-08-16T13:36Z"
        assert len(ar_status.reduxfiles) == 2
        assert ar_status.loadDurationTotal > 0.0
        assert ar_status.loadEventNexusDuration >= 0.0
