"""
    Processor for ONCat cataloging

    @copyright: 2017 Oak Ridge National Laboratory
"""
import os
import logging
import json
from .base_processor import BaseProcessor
from . import job_handling

class ONCatProcessor(BaseProcessor):
    """
        Define post-processing task
    """
    ## Input queue
    _message_queue = "/queue/CATALOG.ONCAT.DATA_READY"
    STARTED_QUEUE = '/queue/CATALOG.ONCAT.STARTED'
    COMPLETE_QUEUE = '/queue/CATALOG.ONCAT.COMPLETE'
    ERROR_QUEUE = '/queue/CATALOG.ONCAT.ERROR'
    SCRIPT_PATH = "/opt/postprocessing/scripts/oncat_ingest.py"

    def __init__(self, data, conf, send_function):
        """
            Initialize the processor
            @param data: data dictionary from the incoming message
            @param conf: configuration object
            @param send_function: function to call to send AMQ messages
        """
        super(ONCatProcessor, self).__init__(data, conf, send_function)

    def __call__(self):
        """
            Execute the job
        """
        if not os.path.isfile(self.SCRIPT_PATH):
            self.data['information'] = "ONCat script not found: %s" % self.SCRIPT_PATH
            self.send(self.ERROR_QUEUE, json.dumps(self.data))
            return

        self.send(self.STARTED_QUEUE, json.dumps(self.data))

        _, out_log, out_err = self._run_job("oncat", dict(script=self.SCRIPT_PATH), dict(), dict())
        success, status_data = job_handling.determine_success_local(self.configuration, out_err)
        self.data.update(status_data)
        if os.path.isfile(out_log):
            try:
                os.remove(out_log)
            except:
                logging.error("Error removing log file: %s", out_log)
        if success:
            if os.path.isfile(out_err):
                try:
                    os.remove(out_err)
                except:
                    logging.error("Error removing error log file: %s", out_err)
            self.send(self.COMPLETE_QUEUE, json.dumps(self.data))
        else:
            self.send(self.ERROR_QUEUE, json.dumps(self.data))
