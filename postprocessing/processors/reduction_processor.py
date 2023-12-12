from .base_processor import BaseProcessor
from . import job_handling

import json
import logging
import os
import subprocess
import sys


class ReductionProcessor(BaseProcessor):
    _message_queue = "/queue/REDUCTION.DATA_READY"

    STARTED_QUEUE = "/queue/REDUCTION.STARTED"
    COMPLETED_QUEUE = "/queue/REDUCTION.COMPLETE"
    ERROR_QUEUE = "/queue/REDUCTION.ERROR"
    DISABLED_QUEUE = "/queue/REDUCTION.DISABLED"

    def __init__(self, data, conf, send_function):
        """
        Initialize the processor
        @param data: data dictionary from the incoming message
        @param conf: configuration object
        @param send_function: function to call to send AMQ messages
        """
        super(ReductionProcessor, self).__init__(data, conf, send_function)

    def __call__(self):
        """
        Reduction process using job submission.
        """

        try:
            self.send(ReductionProcessor.STARTED_QUEUE, json.dumps(self.data))
            # get instrument shared directory
            instrument_shared_dir = os.path.join(
                "/", self.facility, self.instrument, "shared", "autoreduce"
            )
            if len(self.configuration.dev_instrument_shared) > 0:
                instrument_shared_dir = self.configuration.dev_instrument_shared

            # get the proposal shared directory
            proposal_shared_dir = os.path.join(
                "/",
                self.facility,
                self.instrument,
                self.proposal,
                "shared",
                "autoreduce",
            )
            # Allow for an alternate output directory, if defined
            if len(self.configuration.dev_output_dir) > 0:
                proposal_shared_dir = self.configuration.dev_output_dir
            logging.info(f"Using output directory: {proposal_shared_dir}")

            # Set logging directory
            log_dir = os.path.join(proposal_shared_dir, "reduction_log")
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            # Look for run summary script
            summary_script = os.path.join(
                instrument_shared_dir, f"sumRun_{self.instrument}.py"
            )
            if os.path.exists(summary_script) is True:
                summary_output = os.path.join(
                    proposal_shared_dir,
                    f"{self.instrument}_{self.proposal}_runsummary.csv",
                )
                cmd = (
                    "python "
                    + summary_script
                    + " "
                    + self.instrument
                    + " "
                    + self.data_file
                    + " "
                    + summary_output
                )
                logging.debug(f"Run summary subprocess started: {cmd}")
                subprocess.call(cmd, shell=True)
                logging.debug(f"Run summary subprocess completed, see {summary_output}")

            # Look for auto-reduction script
            reduce_script_path = os.path.join(
                instrument_shared_dir, f"reduce_{self.instrument}.py"
            )
            if os.path.exists(reduce_script_path) is False:
                self.send(ReductionProcessor.DISABLED_QUEUE, json.dumps(self.data))
                return

            # Run the reduction
            out_log = os.path.join(log_dir, f"{os.path.basename(self.data_file)}.log")
            out_err = os.path.join(log_dir, f"{os.path.basename(self.data_file)}.err")
            job_handling.local_submission(
                self.configuration,
                reduce_script_path,
                self.data_file,
                proposal_shared_dir,
                out_log,
                out_err,
            )

            # Determine error condition
            success, status_data = job_handling.determine_success_local(
                self.configuration, out_err
            )

            self.data.update(status_data)
            if success:
                if os.path.isfile(out_err):
                    os.remove(out_err)
                self.send(ReductionProcessor.COMPLETED_QUEUE, json.dumps(self.data))
            else:
                self.send(ReductionProcessor.ERROR_QUEUE, json.dumps(self.data))
        except:  # noqa: E722
            logging.error(f"reduce: {sys.exc_info()[1]}")
            self.data["error"] = f"Reduction: {sys.exc_info()[1]} "
            self.send(ReductionProcessor.ERROR_QUEUE, json.dumps(self.data))
