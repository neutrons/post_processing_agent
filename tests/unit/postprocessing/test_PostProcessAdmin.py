from __future__ import print_function

import shutil

from postprocessing.PostProcessAdmin import PostProcessAdmin

# third-party imports
import os
import pytest
import tempfile
from tests.conftest import getDevConfiguration


def createEmptyFile(filename):
    with open(filename, "w"):
        pass


def test_bad_constructor():
    # require that it fails if nothing is provided
    with pytest.raises(TypeError):
        _ = PostProcessAdmin()


def test_good_constructor(mocker):
    instrument = "EQSANS"

    # setup mock configuration
    outdir = tempfile.mkdtemp()
    configuration = getDevConfiguration(outdir)
    os.mkdir(configuration.dev_instrument_shared)
    reduction_script = os.path.join(
        configuration.dev_instrument_shared, "reduce_%s.py" % instrument
    )
    createEmptyFile(reduction_script)
    summary_script = os.path.join(
        configuration.dev_instrument_shared, "sumRun_%s.py" % instrument
    )
    createEmptyFile(summary_script)

    # create empty datafile because the processor checks the file exists
    pretend_datafile = tempfile.mkstemp()[1]  # the name of the file
    assert os.path.exists(pretend_datafile)

    # data examples are taken from PostProcessing.py
    data = {
        "information": "mac83808.sns.gov",
        "run_number": "30892",
        "instrument": instrument,
        "ipts": "IPTS-10674",
        "facility": "SNS",
        "data_file": pretend_datafile,
    }  # "/Volumes/RAID/SNS/EQSANS/IPTS-10674/0/30892/NeXus/EQSANS_30892_event.nxs"}
    postProc = PostProcessAdmin(data, configuration)
    assert postProc

    # mock the send method so it doesn't try to actually send messages to activemq
    postProc.send = mocker.MagicMock()

    # run reduction
    postProc.reduce()
    # verify reduction log directory - this should only be a single subdirectory
    outdir_contents = [os.path.join(outdir, item) for item in os.listdir(outdir)]
    outdir_contents.sort()
    expected_contents = [
        os.path.join(outdir, "reduction_log"),
        configuration.dev_instrument_shared,
    ]
    expected_contents.sort()
    assert len(outdir_contents) == len(expected_contents)
    assert outdir_contents == expected_contents

    # cleanup
    os.unlink(pretend_datafile)
    shutil.rmtree(outdir)

    # create_reduction_script() delegates to other functions


if __name__ == "__main__":
    pytest.main([__file__])
