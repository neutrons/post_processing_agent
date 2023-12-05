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
    STARTED_QUEUE = "/queue/CATALOG.ONCAT.STARTED"
    COMPLETE_QUEUE = "/queue/CATALOG.ONCAT.COMPLETE"
    ERROR_QUEUE = "/queue/CATALOG.ONCAT.ERROR"
    SCRIPT_PATH = "/opt/postprocessing/scripts/oncat_ingest.py"

    def __call__(self):
        """
        Execute the job
        """
        if not os.path.isfile(self.SCRIPT_PATH):
            self.data["information"] = f"ONCat script not found: {self.SCRIPT_PATH}"
            self.send(self.ERROR_QUEUE, json.dumps(self.data))
            return

        self.send(self.STARTED_QUEUE, json.dumps(self.data))

        out_log, out_err = self._run_job("oncat", dict(script=self.SCRIPT_PATH))
        success, status_data = job_handling.determine_success_local(
            self.configuration, out_err
        )
        self.data.update(status_data)
        if os.path.isfile(out_log):
            try:
                os.remove(out_log)
            except:  # noqa: E722
                logging.error("Error removing log file: %s", out_log)
        if success:
            if os.path.isfile(out_err):
                try:
                    os.remove(out_err)
                except:  # noqa: E722
                    logging.error("Error removing error log file: %s", out_err)
            self.send(self.COMPLETE_QUEUE, json.dumps(self.data))
        else:
            self.send(self.ERROR_QUEUE, json.dumps(self.data))
