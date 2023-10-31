from __future__ import print_function

# package imports
from postprocessing.Configuration import (
    Configuration,
    initialize_logging,
    read_configuration,
    StreamToLogger,
)

# third-party imports
import pytest

# standard imports
import logging
import os
import sys
import tempfile


class TestConfiguration(object):
    def test_init(self, data_server):
        with pytest.raises(RuntimeError) as exception_info:
            Configuration("no_file")
        assert "Configuration file doesn't exist" in str(exception_info.value)
        conf = Configuration(data_server.path_to("post_processing.conf"))
        assert conf.sw_dir == "/opt/postprocessing"
        assert conf.log_file == "/tmp/postprocessing.log"
        assert "/queue/CATALOG.ONCAT.DATA_READY" in conf.queues
        assert sys.path[0] == "/opt/postprocessing"

    def test_log_configuration(self, data_server, test_logger):
        conf = Configuration(data_server.path_to("post_processing.conf"))
        conf.log_configuration(logger=test_logger.logger)
        log_contents = open(test_logger.log_file).read()
        assert "LOCAL execution" in log_contents


def test_read_configuration(data_server):
    with pytest.raises(RuntimeError) as exception_info:
        read_configuration(defaults=[])
    assert "Default configuration file(s) do not exist, or unreadable" in str(
        exception_info.value
    )
    backup = sys.stderr
    try:
        conf = read_configuration(
            config_file=data_server.path_to("post_processing.conf")
        )
        # read_configuration also initializes the logging
        logging.info("record info to file")
        sys.stderr.write("writing to sys.stderr records this in file")
        log_contents = open(conf.log_file, "r").read()
        assert "record info to file" in log_contents
        assert "writing to sys.stderr records this in file" in log_contents
    finally:
        sys.stderr = backup


class TestStreamToLogger(object):
    def test_write(self, test_logger):
        sl = StreamToLogger(test_logger.logger)
        sl.write("Hello\nWorld")
        with open(test_logger.log_file, "r") as file_handle:
            contents = file_handle.read().splitlines()
            assert contents == ["Hello", "World"]


def test_initialize_logging():
    backup = sys.stderr
    _, log_file = tempfile.mkstemp()
    try:
        # we need preemptive_cleanup because previous tests have already created handlers for logging.root
        initialize_logging(log_file, preemptive_cleanup=True)
        sys.stderr.write("What an error!")
        log_contents = open(log_file, "r").read()
        assert "What an error!" in log_contents
    finally:
        os.remove(log_file)
        sys.stderr = backup


if __name__ == "__main__":
    pytest.main([__file__])
