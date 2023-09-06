"""
    Processor for NDIP cataloging

    @copyright: 2023 Oak Ridge National Laboratory
"""

import logging
import json
import requests


class NDIPProcessor:
    """
        Define post-processing task
    """
    ## Input queue
    _message_queue = "/queue/CATALOG.NDIP.DATA_READY"
    STARTED_QUEUE = '/queue/CATALOG.NDIP.STARTED'
    COMPLETE_QUEUE = '/queue/CATALOG.NDIP.COMPLETE'
    ERROR_QUEUE = '/queue/CATALOG.NDIP.ERROR'

    @classmethod
    def get_input_queue_name(cls):
        """
            Returns the name of the queue to use to start a job
        """
        return cls._message_queue

    def __init__(self, data, conf, send_function):
        """
            Initialize the processor
            @param data: data dictionary from the incoming message
            @param conf: configuration object
            @param send_function: function to call to send AMQ messages
        """
        self.data = data
        self.configuration = conf
        self._send_function = send_function

    def send_data(self):
        res = {}
        try:
            response = requests.post(self.configuration.ndip_ingest_url, json=self.data, timeout=3)
            if response.status_code == 200:
                success = True
            else:
                success = False
                res["error"] = "SENDING TO NDIP: %s" % response.text
        except Exception as e:
            success = False
            res["error"] = "SENDING TO NDIP: %s" % str(e)

        return success, res

    def send(self, destination, message):
        """
            Send an AMQ message

            @param destination: queue to send the error to
            @param message: message
        """
        if self._send_function is not None:
            logging.debug("Sending message: %s", message)
            self._send_function(destination, message)
        else:
            print("DID NOT SEND TO AMQ", destination, message)

    def __call__(self):
        """
            Execute the job
        """
        self.send(self.STARTED_QUEUE, json.dumps(self.data))
        success, status_data = self.send_data()
        self.data.update(status_data)
        if success:
            self.send(self.COMPLETE_QUEUE, json.dumps(self.data))
        else:
            self.send(self.ERROR_QUEUE, json.dumps(self.data))


class NDIPreducedProcessor(NDIPProcessor):
    """
        Defines post-processing task for reduced data
    """
    ## Input queue
    _message_queue = "/queue/REDUCTION_CATALOG.NDIP.DATA_READY"
    STARTED_QUEUE = '/queue/REDUCTION_CATALOG.NDIP.STARTED'
    COMPLETE_QUEUE = '/queue/REDUCTION_CATALOG.NDIP.COMPLETE'
    ERROR_QUEUE = '/queue/REDUCTION_CATALOG.NDIP.ERROR'
