"""
    The base processor defines a base class to be used to process jobs.
    An input AMQ queue is defined. The post-processing client will
    automatically register with that queue upon starting.

    @copyright: 2014-2015 Oak Ridge National Laboratory
"""

import os
import logging
import json
from . import job_handling


class BaseProcessor:
    """
    Base class for job processor
    """

    data = {}
    configuration = None
    send_function = None
    data_file = None
    facility = None
    instrument = None
    proposal = None
    run_number = None

    ## Input queue
    _message_queue = "/queue/DUMMY"

    def __init__(self, data, conf, send_function):
        """
        Initialize the processor

        @param data: data dictionary from the incoming message
        @param conf: configuration object
        @param send_function: function to call to send an AMQ message
        """
        self.data = data
        self.configuration = conf
        self._process_data(data)
        self._send_function = send_function

    @classmethod
    def get_input_queue_name(cls):
        """
        Returns the name of the queue to use to start a job
        """
        return cls._message_queue

    def _run_job(self, job_name, job_info):
        """
        Run a local job.
        @param job_name: a name for the job
        @param job_info: job description dictionary
        """
        # Check for script information
        script = job_info["script"]

        # Check that the script exists
        if not os.path.isfile(script):
            self.process_error(
                self.configuration.reduction_error,
                f"Script {script} does not exist",
            )

        # Remove old log files
        out_log = os.path.join(
            self.log_dir, f"{os.path.basename(self.data_file)}.{job_name}.log"
        )
        out_err = os.path.join(
            self.log_dir, f"{os.path.basename(self.data_file)}.{job_name}.err"
        )
        if os.path.isfile(out_err):
            os.remove(out_err)
        if os.path.isfile(out_log):
            os.remove(out_log)

        job_handling.local_submission(
            self.configuration,
            script,
            self.data_file,
            self.output_dir,
            out_log,
            out_err,
        )

        return out_log, out_err

    def _process_data(self, data):
        """
        Retrieve run information from the data dictionary
        provided with an incoming message.
        @param data: data dictionary
        """
        if "data_file" in data:
            self.data_file = str(data["data_file"])
            try:
                open(self.data_file)
            except PermissionError as e:
                raise ValueError(
                    f"Data file permission denied: {self.data_file}"
                ) from e
            except FileNotFoundError as e:
                raise ValueError(f"Data file not found: {self.data_file}") from e
            except OSError as e:
                raise ValueError(
                    f"Data file open error for file {self.data_file}"
                ) from e
        else:
            raise ValueError(f"data_file is missing: {self.data_file}")

        if "facility" in data:
            self.facility = str(data["facility"]).upper()
        else:
            raise ValueError("Facility is missing")

        if "instrument" in data:
            self.instrument = str(data["instrument"]).upper()
        else:
            raise ValueError("Instrument is missing")

        if "ipts" in data:
            self.proposal = str(data["ipts"]).upper()
        else:
            raise ValueError("IPTS is missing")

        if "run_number" in data:
            self.run_number = str(data["run_number"])
        else:
            raise ValueError("Run number is missing")

        self.proposal_shared_dir = os.path.join(
            "/", self.facility, self.instrument, self.proposal, "shared", "autoreduce"
        )
        self.output_dir = self.proposal_shared_dir
        self.log_dir = self.output_dir

    def process_error(self, destination, message):
        """
        Log and send error message

        @param destination: queue to send the error to
        @param message: error message
        """
        error_message = "%s: %s" % (type(self).__name__, message)
        logging.error(error_message)
        self.data["error"] = error_message
        self.send(f"/queue/{destination}", json.dumps(self.data).encode())
        # Reset the error and information
        if "information" in self.data:
            del self.data["information"]
        if "error" in self.data:
            del self.data["error"]

    def send(self, destination, message):
        """
        Send an AMQ message

        @param destination: queue to send the error to
        @param message: error message
        """
        if self._send_function is not None:
            self._send_function(destination, message)
        else:
            print("NOT SEND TO AMQ", destination, message)
