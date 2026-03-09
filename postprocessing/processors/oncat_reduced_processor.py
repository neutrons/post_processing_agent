"""
Processor for ONCat cataloging

@copyright: 2017 Oak Ridge National Laboratory
"""

import os
import logging
import json
from .base_processor import BaseProcessor
import pyoncat


class ONCatProcessor(BaseProcessor):
    """
    Define post-processing task
    """

    ## Input queue
    _message_queue = "/queue/REDUCTION_CATALOG.DATA_READY"
    STARTED_QUEUE = "/queue/REDUCTION_CATALOG.STARTED"
    COMPLETE_QUEUE = "/queue/REDUCTION_CATALOG.COMPLETE"
    ERROR_QUEUE = "/queue/CATALOG.ERROR"

    def __call__(self):
        """
        Execute the job
        """
        self.send(self.STARTED_QUEUE, json.dumps(self.data))

        raw_file_name = os.path.split(self.data_file)[-1]
        reduction_file_name = raw_file_name.replace(".nxs.h5", ".json")
        reduction_file_path = os.path.join(self.output_dir, reduction_file_name)

        try:
            self.ingest(reduction_file_path)
        except Exception as e:
            logging.error("Error ingesting data file: %s", e)
            self.data["error"] = f"ONCAT: {e}"
            self.send(self.ERROR_QUEUE, json.dumps(self.data))
        else:
            self.send(self.COMPLETE_QUEUE, json.dumps(self.data))

    def ingest(self, location):
        """Will catalog the given reduction json file.

        pyoncat ingest makes a POST request to the ONCat server
        to register the file.

        The reduction file must be a valid JSON file with
        "input_files" and "output_files" keys.
        """
        if not os.path.exists(location):
            logging.info("Could not find %s so will not call ONCat", location)
            return

        with open(location) as f:
            contents = json.load(f)
            if "input_files" not in contents or "output_files" not in contents:
                logging.info(
                    "%s does not appear to be a JSON reduction file so will not call ONCat",
                    location,
                )
                return

        oncat = pyoncat.ONCat(
            self.configuration.oncat_url,
            api_token=self.configuration.oncat_api_token,
        )

        logging.info("Calling ONCat for %s", location)
        oncat.Reduction.ingest(location)
