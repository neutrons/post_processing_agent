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
import importlib
import json


class TestConfiguration:
    def test_init(self, data_server):
        with pytest.raises(RuntimeError) as exception_info:
            Configuration("no_file")
        assert "Configuration file doesn't exist" in str(exception_info.value)
        conf = Configuration(data_server.path_to("post_processing.conf"))
        assert conf.sw_dir == "/opt/postprocessing"
        assert conf.log_file == "/tmp/postprocessing.log"
        assert "/queue/CATALOG.ONCAT.DATA_READY" in conf.queues
        assert sys.path[0] == "/opt/postprocessing"
        assert len(conf.processors) == 2

    def test_log_configuration(self, data_server, test_logger):
        conf = Configuration(data_server.path_to("post_processing.conf"))
        conf.log_configuration(logger=test_logger.logger)
        log_contents = open(test_logger.log_file).read()
        assert "LOCAL execution" in log_contents


def test_read_configuration(data_server, caplog):
    caplog.set_level(logging.INFO)
    with pytest.raises(RuntimeError) as exception_info:
        log_file = tempfile.mkstemp()[1]  # second argument is filename
        read_configuration(defaults=[], log_file=log_file)
    assert "Default configuration file(s) do not exist, or unreadable" in str(exception_info.value)
    backup = sys.stderr
    try:
        log_file = tempfile.mkstemp()[1]  # second argument is filename
        conf = read_configuration(config_file=data_server.path_to("post_processing.conf"), log_file=log_file)
        # read_configuration also initializes the logging
        logging.info("record info to file")
        sys.stderr.write("writing to sys.stderr records this in file")
        # test that the log file was created
        log_contents = open(conf.log_file, "r").read()  # noqa: F841
        # check the log messages that would have been written to the log file had pytest not captured them
        assert "record info to file" in caplog.records[0].message
        assert "writing to sys.stderr records this in file" in caplog.records[1].message
    except IOError:
        raise IOError("Log file not found: " + str(conf.log_file))
        # python3 version raise IOError("Log file not found") from e
    finally:
        sys.stderr = backup


@pytest.fixture
def config(data_server):
    return Configuration(data_server.path_to("post_processing.conf"))


@pytest.mark.parametrize("log_level_str", ["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"])
def test_log_level(log_level_str, config, tmp_path):
    """Test setting log level in the configuration file"""
    config.log_level = log_level_str
    expected_log_level = getattr(logging, log_level_str)
    # we need to reload logging so that the new config gets set correctly
    importlib.reload(logging)
    # create a copy of the config file
    tmp_conf_file = tmp_path / "post_processing.conf"
    tmp_conf_file.write_text(json.dumps(config, default=lambda o: o.__dict__))
    # read configuration file, which initializes logging
    read_configuration(config_file=tmp_conf_file.as_posix())
    assert logging.root.level == expected_log_level


class TestStreamToLogger:
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
        # we need to reload logging so that the new config gets set correctly
        importlib.reload(logging)
        initialize_logging(log_file)
        sys.stderr.write("What an error!")
        log_contents = open(log_file, "r").read()
        assert "What an error!" in log_contents
    finally:
        os.remove(log_file)
        sys.stderr = backup


if __name__ == "__main__":
    pytest.main([__file__])
