"""
    Processor for ONCat cataloging

    @copyright: 2017 Oak Ridge National Laboratory
"""
import os
import logging
import json
import glob
from .base_processor import BaseProcessor
import pyoncat


class ONCatProcessor(BaseProcessor):
    """
    Define post-processing task
    """

    ## Input queue
    _message_queue = "/queue/CATALOG.ONCAT.DATA_READY"
    STARTED_QUEUE = "/queue/CATALOG.ONCAT.STARTED"
    COMPLETE_QUEUE = "/queue/CATALOG.ONCAT.COMPLETE"
    ERROR_QUEUE = "/queue/CATALOG.ONCAT.ERROR"

    def __call__(self):
        """
        Execute the job
        """

        self.send(self.STARTED_QUEUE, json.dumps(self.data))

        try:
            self.ingest(self.data["data_file"])
        except Exception as e:
            logging.error("Error ingesting data file: %s", e)
            self.data["error"] = f"ONCAT: {e}"
            self.send(self.ERROR_QUEUE, json.dumps(self.data))
        else:
            self.send(self.COMPLETE_QUEUE, json.dumps(self.data))

    def ingest(self, location):
        """Will catalog the given file and any other related files.

        pyoncat ingest makes a POST request to the ONCat server to register
        the file.
        """
        oncat = pyoncat.ONCat(
            self.configuration.oncat_url,
            api_token=self.configuration.oncat_api_token,
        )

        location = location.replace("//", "/")

        logging.info("Calling ONCat for %s", location)
        datafile = oncat.Datafile.ingest(location)

        for related_file in related_files(datafile):
            # With PyONCat 1.4.0 in Python 2, we need to convert from
            # unicode to str.  See: #210.
            logging.info("Calling ONCat for %s", related_file)
            oncat.Datafile.ingest(related_file)


def related_files(datafile):
    """Given a datafile, return a list of related files to also catalog.
    This is a simple heuristic based on the file's location and run number.
    """
    location = datafile.location
    facility = datafile.facility
    instrument = datafile.instrument
    experiment = datafile.experiment
    run_number = datafile.get("indexed.run_number")

    if not run_number:
        return []

    return [
        path
        for path in glob.glob(
            os.path.join(
                "/",
                facility,
                instrument,
                experiment,
                "images",
                "det_*",
                instrument + "_" + str(run_number) + "_det_*",
            )
        )
        if path != location
    ]
