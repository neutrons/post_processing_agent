# pylint: disable=line-too-long, too-many-statements, too-few-public-methods, too-many-instance-attributes, invalid-name
"""
    Post-processing, ActiveMQ, and logging configuration

    The original code for this class was take from https://github.com/mantidproject/autoreduce

    @copyright: 2014 Oak Ridge National Laboratory
"""
import sys
import os
import json
import logging


class Configuration(object):
    """
    Read and process configuration file and provide an easy way to create a configured Client object
    """

    def __init__(self, config_file):
        if os.access(config_file, os.R_OK) is False:
            raise RuntimeError(
                "Configuration file doesn't exist or is not readable: %s" % config_file
            )
        cfg = open(config_file, "r")
        json_encoded = cfg.read()
        config = json.loads(json_encoded)

        # Keep a record of which config file we are using
        self.config_file = config_file
        # ActiveMQ user creds
        self.amq_user = config["amq_user"]
        self.amq_pwd = config["amq_pwd"]
        # ActiveMQ broker information
        self.failover_uri = config["failover_uri"]
        self.queues = config["amq_queues"]
        self.sw_dir = config["sw_dir"] if "sw_dir" in config else "/opt/postprocessing"
        self.postprocess_error = config["postprocess_error"]
        # Reduction AMQ queues
        self.reduction_data_ready = (
            config["reduction_data_ready"]
            if "reduction_data_ready" in config
            else "REDUCTION.DATA_READY"
        )
        self.reduction_started = config["reduction_started"]
        self.reduction_complete = config["reduction_complete"]
        self.reduction_error = config["reduction_error"]
        self.reduction_disabled = config["reduction_disabled"]
        self.heartbeat_ping = (
            config["heartbeat_ping"]
            if "heartbeat_ping" in config
            else "/topic/SNS.COMMON.STATUS.PING"
        )
        # Reduction script writer
        self.create_reduction_script = (
            config["create_reduction_script"]
            if "create_reduction_script" in config
            else "REDUCTION.CREATE_SCRIPT"
        )
        self.service_status = (
            config["service_status"]
            if "service_status" in config
            else "/topic/SNS.${instrument}.STATUS.POSTPROCESS"
        )

        self.heart_beat = config["heart_beat"]
        self.log_file = (
            config["log_file"] if "log_file" in config else "post_processing.log"
        )
        self.start_script = (
            config["start_script"] if "start_script" in config else "python"
        )
        self.task_script = (
            config["task_script"] if "task_script" in config else "PostProcessAdmin.py"
        )
        self.python_dir = (
            config["python_dir"]
            if "python_dir" in config
            else os.path.join(self.sw_dir, "postprocessing")
        )
        self.mantid_path = (
            config["mantid_path"] if "mantid_path" in config else "/opt/Mantid/bin"
        )
        self.dev_output_dir = (
            config["dev_output_dir"] if "dev_output_dir" in config else ""
        )
        self.python_executable = (
            config["python_exec"] if "python_exec" in config else "python"
        )

        self.max_procs = config["max_procs"] if "max_procs" in config else 5

        self.comm_only = (
            config["communication_only"] == 1
            if "communication_only" in config
            else False
        )

        self.task_script_queue_arg = (
            config["task_script_queue_arg"]
            if "task_script_queue_arg" in config
            else None
        )
        self.task_script_data_arg = (
            config["task_script_data_arg"] if "task_script_data_arg" in config else None
        )

        self.exceptions = (
            config["exceptions"]
            if "exceptions" in config
            else ["Error in logging framework"]
        )

        self.jobs_per_instrument = (
            config["jobs_per_instrument"] if "jobs_per_instrument" in config else 2
        )

        # plot publishing
        self.publish_url = config.get("publish_url_template", "")
        self.publisher_username = config.get("publisher_username", "")
        self.publisher_password = config.get("publisher_password", "")

        self.calvera_ingest_url = config.get("calvera_ingest_url", "")

        sys.path.insert(0, self.sw_dir)
        # Configure processor plugins
        self.processors = config["processors"] if "processors" in config else []
        if isinstance(self.processors, list):
            for p in self.processors:
                toks = p.split(".")
                if len(toks) == 2:
                    # for instance, emulate `from oncat_processor import ONCatProcessor`
                    # TODO replace with importlib.import_module()
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
                        self.queues.append(processor_class.get_input_queue_name())
                    except:  # noqa: E722
                        logging.error(
                            "Configuration: Error loading processor: %s", sys.exc_value
                        )
                else:
                    logging.error(
                        "Configuration: Processors can only be specified in the format module.Processor_class"
                    )

    def log_configuration(self, logger=logging):
        """
        Log the current configuration
        """
        logger.info("Using %s", self.config_file)
        if self.comm_only:
            logger.info(
                "  - Running in COMMUNICATION ONLY mode: no post-processing will be performed"
            )
        logger.info("  - LOCAL execution")
        logger.info("  - Max number of processes: %s", self.max_procs)
        logger.info("  - Input queues: %s", self.queues)
        logger.info("  - Installation dir: %s", self.sw_dir)
        logger.info("  - Start script: %s", self.start_script)
        logger.info("  - Task script: %s", self.task_script)
        logger.info("  - Error exceptions: %s", str(self.exceptions))


# Set the log level for the Stomp client
stomp_logger = logging.getLogger("stompest.sync.client")
stomp_logger.setLevel(logging.ERROR)


class StreamToLogger(object):
    r"""File-like stream object that redirects writes to a Logger instance."""

    def __init__(self, logger, log_level=logging.INFO):
        r"""
        @brief duck-typing for a file-stream object that redirects to a Logger instance
        @param Logger logger: instance of python standard Logger
        @param int log_level: one of DEBUG, INFO, WARNING, ERROR, CRITICAL
        """
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ""

    def write(self, buf):
        """
        Write a message to stdout so we can see it when running interactively
        """
        sys.stdout.write(buf)
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())


def initialize_logging(log_file, level=logging.INFO, preemptive_cleanup=False):
    r"""
    @brief Set the default log level and the file where to append log messages

    @details: also pipe sys.stderr to the STDERR channel of the root logger

    @param str log_file: absolute path to the file logging the messages
    @param int level: one of DEBUG, INFO, WARNING, ERROR, CRITICAL
    @param bool preemptive_cleanup: remove all existing handlers of the root looger before initializing
    """
    # logging.basicConfig does nothing if the root logger already has handlers
    if preemptive_cleanup:
        for handler in logging.root.handlers:
            handler.close()
            logging.root.removeHandler(handler)

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s/%(process)d %(message)s",
        filename=log_file,
        filemode="a",
    )
    stderr_logger = logging.getLogger("STDERR")
    sl = StreamToLogger(stderr_logger, logging.ERROR)
    sys.stderr = sl


# Default locations for configurationss
CONFIG_FILE = "/etc/autoreduce/post_processing.conf"
CONFIG_FILE_ALTERNATE = (
    "/sw/fermi/autoreduce/postprocessing/configuration/post_processing.conf"
)


def read_configuration(
    config_file=None, defaults=[CONFIG_FILE, CONFIG_FILE_ALTERNATE], log_file=""
):
    r"""
    Returns a new configuration object for a given configuration file, and initializes the basic configuration
    of all log messages.

    @details: also initialize the logging (see `initialize_logging`)

    @param str config_file: absolute path to custom configuration file to process
    @param list defaults: configuration files to be used when no custom configuration is provided
    @param log_file: Specify optional override for logfile. This is used for testing.

    @returns Configuration: data structure representing the configuration file just read
    """

    if config_file is None:
        for config_default in defaults:
            if os.access(config_default, os.R_OK):
                config_file = config_default
                break
        else:
            raise RuntimeError(
                "Default configuration file(s) do not exist, or unreadable: %s"
                % str(defaults)
            )

    configuration = Configuration(config_file)
    if log_file:
        configuration.log_file = str(log_file)
    initialize_logging(configuration.log_file)

    return configuration
