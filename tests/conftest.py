# 3rd-party imports
import pytest

# standard imports
from collections import namedtuple
import logging
import os
import subprocess
import sys
import tempfile

this_module_path = sys.modules[__name__].__file__


@pytest.fixture(scope="module")
def data_server():
    r"""Object containing info and functionality for data files"""

    class _DataServe:
        _directory = os.path.join(os.path.dirname(this_module_path), "data")

        @property
        def directory(self):
            r"""Directory where to find the data files"""
            return self._directory

        def path_to(self, basename):
            r"""Absolute path to a data file"""
            file_path = os.path.join(self._directory, basename)
            if not os.path.isfile(file_path):
                raise IOError(
                    "File {basename} not found in data directory {self._directory}"
                )
            return file_path

    return _DataServe()


@pytest.fixture(scope="function")
def test_logger():
    r"""
    Instantiate a Logger that writes messages to a temporary file
    @returns namedtuple('TestLogger', ['logger', 'log_file']) where 'logger' is a Logger object
    and 'log_file' is the absolute path to the file recording the log messages
    """
    logger = logging.getLogger("test")
    logger.setLevel(logging.DEBUG)
    _, log_file = tempfile.mkstemp()
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)
    TestLogger = namedtuple("TestLogger", ["logger", "log_file"])
    yield TestLogger(logger, log_file)
    # clean up time
    for handler in logger.handlers:
        handler.close()
        logger.removeHandler(handler)
    os.remove(log_file)


def docker_identify_container():
    """This returns the container-id associated with the name that starts with "integration-post_processing_agent".
    The function was added to be more resilient to slight variations in what docker names the images.
    """
    # this will throw an exception if the command returns non-zero
    container_id = subprocess.check_output(
        args=r'docker ps -qaf "name=^integration-post_processing_agent"',
        stderr=subprocess.STDOUT,
        shell=True,
    )
    # remove trailing whitespace
    container_id = container_id.strip()
    # verify it is non-empty
    if container_id:
        return container_id.decode()
    else:
        return "integration_post_processing_agent_1"  # default name on github


def docker_exec_and_cat(filename):
    """`cat` a file in a docker container"""
    # get the name of the docker container that does the work
    container_id = docker_identify_container()
    print("communicating with docker container id", container_id)
    # this will throw an exception if the command returns non-zero
    filecontents = subprocess.check_output(
        args="docker exec {} cat {}".format(container_id, filename),
        stderr=subprocess.STDOUT,
        shell=True,
    )
    return filecontents.decode()


def getDevConfigurationFile():
    srcdir = os.path.dirname(os.path.realpath(__file__))  # directory this file is in
    # go up 1 level to get out of tests directory
    srcdir = os.path.split(srcdir)[0]

    return os.path.join(srcdir, "configuration/post_process_consumer.conf.development")


def getDevConfiguration(dev_output_dir=""):
    """
    Create a Configuration object with a now developer directory
    @param dev_output_dir: Location of the output directory
    """
    from postprocessing.Configuration import Configuration

    # load the developer configuration file
    config = Configuration(getDevConfigurationFile())
    if dev_output_dir:
        config.dev_output_dir = dev_output_dir
        config.dev_instrument_shared = os.path.join(dev_output_dir, "shared")
    return config
