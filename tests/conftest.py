# 3rd-party imports
import pytest

# standard imports
from collections import namedtuple
import logging
import os
import sys
import tempfile

this_module_path = sys.modules[__name__].__file__


@pytest.fixture(scope='module')
def data_server():
    r"""Object containing info and functionality for data files"""

    class _DataServe(object):

        _directory = os.path.join(os.path.dirname(this_module_path), 'data')

        @property
        def directory(self):
            r"""Directory where to find the data files"""
            return self._directory

        def path_to(self, basename):
            r"""Absolute path to a data file"""
            file_path = os.path.join(self._directory, basename)
            if not os.path.isfile(file_path):
                raise IOError('File {basename} not found in data directory {self._directory}')
            return file_path

    return _DataServe()


@pytest.yield_fixture(scope='function')  # 'yield_fixture' deprecated in favor of 'yield' when using python 3.x
def test_logger():
    r"""
    Instantiate a Logger that writes messages to a temporary file
    @returns namedtuple('TestLogger', ['logger', 'log_file']) where 'logger' is a Logger object
    and 'log_file' is the absolute path to the file recording the log messages
    """
    logger = logging.getLogger('test')
    logger.setLevel(logging.DEBUG)
    _, log_file = tempfile.mkstemp()
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)
    TestLogger = namedtuple('TestLogger', ['logger', 'log_file'])
    yield TestLogger(logger, log_file)
    # clean up time
    for handler in logger.handlers:
        handler.close()
        logger.removeHandler(handler)
    os.remove(log_file)
