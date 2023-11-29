from __future__ import print_function

import shutil

from postprocessing.Configuration import Configuration
from postprocessing.PostProcessAdmin import PostProcessAdmin

# third-party imports
import os
import pytest
import tempfile


def getDevConfiguration(dev_output_dir=""):
    """
    Create a Configuration object with a now developer directory
    @param dev_output_dir: Location of the output directory
    """
    srcdir = os.path.dirname(os.path.realpath(__file__))  # directory this file is in
    # go up 3 levels
    for i in range(3):
        srcdir = os.path.split(srcdir)[0]
    # load the developer configuration file
    config = Configuration(
        os.path.join(srcdir, "configuration/post_process_consumer.conf.development")
    )
    if dev_output_dir:
        config.dev_output_dir = dev_output_dir
    return config


def test_bad_constructor():
    # require that it fails if nothing is provided
    with pytest.raises(TypeError):
        _ = PostProcessAdmin()


def test_good_constructor(mocker):
    # setup mock configuration
    outdir = tempfile.mkdtemp()
    configuration = getDevConfiguration(outdir)

    # create empty datafile because the processor checks the file exists
    pretend_datafile = tempfile.mkstemp()[1]  # the name of the file
    assert os.path.exists(pretend_datafile)

    # data examples are taken from PostProcessing.py
    data = {
        "information": "mac83808.sns.gov",
        "run_number": "30892",
        "instrument": "EQSANS",
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
    assert outdir_contents == [os.path.join(outdir, "reduction_log")]

    # cleanup
    os.unlink(pretend_datafile)
    shutil.rmtree(outdir)

    # create_reduction_script() delegates to other functions


if __name__ == "__main__":
    pytest.main([__file__])
