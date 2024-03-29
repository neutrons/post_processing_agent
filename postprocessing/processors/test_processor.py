"""
    Test Processor

    @copyright: 2014 Oak Ridge National Laboratory
"""
from .base_processor import BaseProcessor
import json


class TestProcessor(BaseProcessor):
    # tell pytest this class does not contain tests
    __test__ = False

    ## Input queue
    _message_queue = "/queue/REDUCTION.TESTPROCESSOR.DATA_READY"

    def __call__(self):
        """
        Just send back acknowledgment messages
        """
        self.send(
            "/queue/" + self.configuration.reduction_started, json.dumps(self.data)
        )
        self.send(
            "/queue/" + self.configuration.reduction_complete, json.dumps(self.data)
        )
