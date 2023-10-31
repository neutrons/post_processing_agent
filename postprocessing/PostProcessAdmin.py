#!/usr/bin/env python
"""
Post-processing tasks

The original code for this class was take from https://github.com/mantidproject/autoreduce

Example input dictionaries:

{"information": "mac83808.sns.gov", "run_number": "30892", "instrument": "EQSANS", "ipts": "IPTS-10674",
 "facility": "SNS", "data_file": "/Volumes/RAID/SNS/EQSANS/IPTS-10674/0/30892/NeXus/EQSANS_30892_event.nxs"}

{"information": "autoreducer1.sns.gov", "run_number": "85738", "instrument": "CNCS", "ipts": "IPTS-10546",
 "facility": "SNS", "data_file": "/SNS/CNCS/IPTS-10546/0/85738/NeXus/CNCS_85738_event.nxs"}

@copyright: 2014 Oak Ridge National Laboratory
"""
import logging, json, socket, os, sys, subprocess
import processors.job_handling as job_handling
from stompest.config import StompConfig
from stompest.sync import Stomp


class PostProcessAdmin:
    def __init__(self, data, conf):
        logging.debug("json data: %s [%s]" % (str(data), type(data)))
        if not isinstance(data, dict):
            raise ValueError("PostProcessAdmin expects a data dictionary")
        data["information"] = socket.gethostname()
        self.data = data
        self.conf = conf

        # List of error messages to be handled as information
        self.exceptions = self.conf.exceptions

        stompConfig = StompConfig(
            self.conf.failover_uri, self.conf.amq_user, self.conf.amq_pwd
        )
        self.client = Stomp(stompConfig)

        self.data_file = None
        self.facility = None
        self.instrument = None
        self.proposal = None
        self.run_number = None

    def _process_data(self, data):
        """
        Retrieve run information from the data dictionary
        provided with an incoming message.
        @param data: data dictionary
        """
        if data.has_key("data_file"):
            self.data_file = str(data["data_file"])
            if os.access(self.data_file, os.R_OK) is False:
                raise ValueError(
                    "Data file does not exist or is not readable: %s" % self.data_file
                )
        else:
            raise ValueError("data_file is missing: %s" % self.data_file)

        if data.has_key("facility"):
            self.facility = str(data["facility"]).upper()
        else:
            raise ValueError("Facility is missing")

        if data.has_key("instrument"):
            self.instrument = str(data["instrument"]).upper()
        else:
            raise ValueError("Instrument is missing")

        if data.has_key("ipts"):
            self.proposal = str(data["ipts"]).upper()
        else:
            raise ValueError("IPTS is missing")

        if data.has_key("run_number"):
            self.run_number = str(data["run_number"])
        else:
            raise ValueError("Run number is missing")

    def reduce(self):
        """
        Reduction process using job submission.
        """
        self._process_data(self.data)
        try:
            self.send("/queue/" + self.conf.reduction_started, json.dumps(self.data))
            instrument_shared_dir = os.path.join(
                "/", self.facility, self.instrument, "shared", "autoreduce"
            )
            proposal_shared_dir = os.path.join(
                "/",
                self.facility,
                self.instrument,
                self.proposal,
                "shared",
                "autoreduce",
            )
            log_dir = os.path.join(proposal_shared_dir, "reduction_log")
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            # Allow for an alternate output directory, if defined
            if len(self.conf.dev_output_dir.strip()) > 0:
                proposal_shared_dir = self.conf.dev_output_dir
            logging.info("Using output directory: %s" % proposal_shared_dir)

            # Look for run summary script
            summary_script = os.path.join(
                instrument_shared_dir, "sumRun_%s.py" % self.instrument
            )
            if os.path.exists(summary_script) is True:
                summary_output = os.path.join(
                    proposal_shared_dir,
                    "%s_%s_runsummary.csv" % (self.instrument, self.proposal),
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
                logging.debug("Run summary subprocess started: " + cmd)
                subprocess.call(cmd, shell=True)
                logging.debug("Run summary subprocess completed, see " + summary_output)

            # Look for auto-reduction script
            reduce_script_path = os.path.join(
                instrument_shared_dir, "reduce_%s.py" % self.instrument
            )
            if os.path.exists(reduce_script_path) is False:
                self.send(
                    "/queue/" + self.conf.reduction_disabled, json.dumps(self.data)
                )
                return

            # Run the reduction
            out_log = os.path.join(log_dir, os.path.basename(self.data_file) + ".log")
            out_err = os.path.join(log_dir, os.path.basename(self.data_file) + ".err")
            job_handling.local_submission(
                self.conf,
                reduce_script_path,
                self.data_file,
                proposal_shared_dir,
                out_log,
                out_err,
            )

            # Determine error condition
            success, status_data = job_handling.determine_success_local(
                self.conf, out_err
            )
            self.data.update(status_data)
            if success:
                if os.path.isfile(out_err):
                    os.remove(out_err)
                self.send(
                    "/queue/" + self.conf.reduction_complete, json.dumps(self.data)
                )
            else:
                self.send("/queue/" + self.conf.reduction_error, json.dumps(self.data))
        except:  # noqa: E722
            logging.error("reduce: %s" % sys.exc_value)
            self.data["error"] = "Reduction: %s " % sys.exc_value
            self.send("/queue/" + self.conf.reduction_error, json.dumps(self.data))

    def create_reduction_script(self):
        """
        Create a new reduction script from a template
        """
        try:
            import reduction_script_writer

            writer = reduction_script_writer.ScriptWriter(self.data["instrument"])
            writer.process_request(
                self.data, configuration=self.conf, send_function=self.send
            )
        except:  # noqa: E722
            logging.error("create_reduction_script: %s" % sys.exc_value)

    def send(self, destination, data):
        """
        Send an AMQ message
        @param destination: AMQ queue to send to
        @param data: payload of the message
        """
        logging.info("%s: %s" % (destination, data))
        self.client.connect()
        self.client.send(destination, data)
        self.client.disconnect()


if __name__ == "__main__":
    import argparse
    from Configuration import read_configuration

    parser = argparse.ArgumentParser(description="Post-processing agent")
    parser.add_argument(
        "-q", metavar="queue", help="ActiveMQ queue name", dest="queue", required=True
    )
    parser.add_argument(
        "-c", metavar="config", help="Configuration file", dest="config"
    )
    parser.add_argument("-d", metavar="data", help="JSON data", dest="data")
    parser.add_argument(
        "-f", metavar="data_file", help="Nexus data file", dest="data_file"
    )
    namespace = parser.parse_args()

    try:
        # Refresh configuration is we need to use an alternate configuration
        if namespace.config is not None:
            configuration = read_configuration(namespace.config)
        else:
            configuration = read_configuration()

        # If we have no data dictionary, try to create one
        if namespace.data is None:
            if namespace.data_file is not None:
                data = {"facility": "SNS", "data_file": namespace.data_file}
                file_name = os.path.basename(namespace.data_file)
                toks = file_name.split("_")
                if len(toks) > 1:
                    data["instrument"] = toks[0].upper()
                    try:
                        data["run_number"] = str(int(toks[1]))
                    except:  # noqa: E722
                        logging.error("Could not determine run number")
                    ipts_toks = namespace.data_file.upper().split(toks[0].upper())
                    if len(ipts_toks) > 1:
                        sep_toks = ipts_toks[1].split("/")
                        if len(sep_toks) > 1:
                            data["ipts"] = sep_toks[1]
            else:
                logging.error("PostProcessAdmin: Expected a JSON object or a file path")
        else:
            data = json.loads(namespace.data)

        # Process the data
        try:
            pp = PostProcessAdmin(data, configuration)
            if isinstance(
                configuration.reduction_data_ready, list
            ) and namespace.queue in [
                "/queue/%s" % q for q in configuration.reduction_data_ready
            ]:
                pp.reduce()
            elif namespace.queue == "/queue/%s" % configuration.reduction_data_ready:
                pp.reduce()
            elif namespace.queue == "/queue/%s" % configuration.create_reduction_script:
                pp.create_reduction_script()

            # Check for registered processors
            if isinstance(configuration.processors, list):
                for p in configuration.processors:
                    toks = p.split(".")
                    if len(toks) == 2:
                        processor_module = __import__(
                            "postprocessing.processors.%s" % toks[0],
                            globals(),
                            locals(),
                            [
                                toks[1],
                            ],
                            -1,
                        )
                        try:
                            processor_class = eval("processor_module.%s" % toks[1])
                            if (
                                namespace.queue
                                == processor_class.get_input_queue_name()
                            ):
                                # Instantiate and call the processor
                                proc = processor_class(
                                    data, configuration, send_function=pp.send
                                )
                                proc()
                        except:  # noqa: E722
                            logging.error(
                                "PostProcessAdmin: Processor error: %s" % sys.exc_value
                            )
                    else:
                        logging.error(
                            "PostProcessAdmin: Processors can only be specified in the format module.Processor_class"
                        )

        except:  # noqa: E722
            # If we have a proper data dictionary, send it back with an error message
            if isinstance(data, dict):
                data["error"] = str(sys.exc_value)
                stomp = Stomp(
                    StompConfig(
                        configuration.failover_uri,
                        configuration.amq_user,
                        configuration.amq_pwd,
                    )
                )
                stomp.connect()
                stomp.send(configuration.postprocess_error, json.dumps(data))
                stomp.disconnect()
            raise
    except:  # noqa: E722
        logging.error("PostProcessAdmin: %s" % sys.exc_value)
