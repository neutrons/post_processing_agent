"""
`   Processor for Intersect cataloging

    @copyright: 2023 Oak Ridge National Laboratory
"""

import copy
import logging
import json
import os
import requests
from .base_processor import BaseProcessor


class IntersectProcessor(BaseProcessor):
    """
    Define post-processing task
    """

    ## Input queue
    _message_queue = "/queue/INTERSECT.RAW.DATA_READY"
    COMPLETE_QUEUE = "/queue/INTERSECT.RAW.COMPLETE"
    ERROR_QUEUE = "/queue/INTERSECT.RAW.ERROR"

    def _prepare_send_data(self):
        to_send = copy.deepcopy(self.data)
        to_send["type"] = "raw"
        return to_send

    def send_to_intersect(self):
        res = {}
        try:
            data_to_send = self._prepare_send_data()
            response = requests.post(self.configuration.intersect_ingest_url, json=data_to_send, timeout=3)
            if response.status_code == 200:
                success = True
            else:
                success = False
                res["error"] = f"SENDING TO Intersect: {response.text}"
        except Exception as e:
            success = False
            res["error"] = f"SENDING TO Intersect: {e}"

        return success, res

    def __call__(self):
        """
        Execute the job
        """
        success, status_data = self.send_to_intersect()
        self.data.update(status_data)
        if success:
            self.send(self.COMPLETE_QUEUE, json.dumps(self.data))
        else:
            self.send(self.ERROR_QUEUE, json.dumps(self.data))


class IntersectReducedProcessor(IntersectProcessor):
    """
    Defines post-processing task for reduced data
    """

    ## Input queue
    _message_queue = "/queue/INTERSECT.REDUCED.DATA_READY"
    COMPLETE_QUEUE = "/queue/INTERSECT.REDUCED.COMPLETE"
    ERROR_QUEUE = "/queue/INTERSECT.REDUCED.ERROR"

    def _read_reduced_data(self, filepath):
        if not os.path.exists(filepath):
            logging.info("Could not find %s so will not send to Intersect", filepath)
            return None

        with open(filepath) as f:
            contents = json.load(f)
            if "input_files" not in contents or "output_files" not in contents:
                logging.info(
                    "%s does not appear to be a JSON reduction file so will not send to Intersect",
                    filepath,
                )
                return None

        return contents

    def _prepare_send_data(self):
        to_send = copy.deepcopy(self.data)
        to_send["type"] = "reduced"
        raw_file_name = os.path.basename(self.data["data_file"])
        reduction_file_name = raw_file_name.replace(".nxs.h5", ".json")
        reduction_file_path = os.path.join(self.output_dir, reduction_file_name)
        reduced_data_info = self._read_reduced_data(reduction_file_path)
        if not reduced_data_info:
            raise Exception("Cannot read reduced data info")
        to_send["reduced_data_info"] = reduced_data_info
        return to_send
