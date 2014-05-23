"""
    Post-processing, ActiveMQ, and logging configuration
    
    The original code for this class was take from https://github.com/mantidproject/autoreduce

    @copyright: 2014 Oak Ridge National Laboratory
"""
import logging, json, sys, os

## Default configuration file location
CONFIG_FILE = '/etc/autoreduce/post_process_consumer.conf'

class StreamToLogger(object):
    """
        File-like stream object that redirects writes to a logger instance.
    """
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''
 
    def write(self, buf):
        # Write the message to stdout so we can see it when running interactively
        sys.stdout.write(buf)
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())


class Configuration(object):
    """
        Read and process configuration file and provide an easy way to create a configured Client object
    """
    def __init__(self, config_file):
        if os.access(config_file, os.R_OK) == False:
            raise RuntimeError, "Configuration file doesn't exist or is not readable: %s" % sys.exc_value
        print "Using %s" % config_file
        cfg = open(config_file, 'r')
        json_encoded = cfg.read()
        config = json.loads(json_encoded)
        self.amq_user = config['amq_user']
        self.amq_pwd = config['amq_pwd']
        self.brokers = config['brokers']
        self.uri = config['uri']
        self.queues = config['amq_queues']
        self.sw_dir = config['sw_dir'] if 'sw_dir' in config else '/opt/postprocessing'
        self.postprocess_error = config['postprocess_error']
        # Catalog AMQ queues
        self.catalog_data_ready = config['catalog_data_ready'] if 'catalog_data_ready' in config else 'CATALOG.DATA_READY'
        self.catalog_started = config['catalog_started']
        self.catalog_complete = config['catalog_complete']
        self.catalog_error = config['catalog_error']
        # Reduction AMQ queues
        self.reduction_data_ready = config['reduction_data_ready'] if 'reduction_data_ready' in config else 'REDUCTION.DATA_READY'
        self.reduction_started = config['reduction_started']
        self.reduction_complete = config['reduction_complete']
        self.reduction_error = config['reduction_error']
        self.reduction_disabled = config['reduction_disabled']
        # Reduction catalog AMQ queues
        self.reduction_catalog_data_ready = config['reduction_catalog_data_ready'] if 'reduction_catalog_data_ready' in config else 'REDUCTION_CATALOG.DATA_READY'
        self.reduction_catalog_started = config['reduction_catalog_started']
        self.reduction_catalog_complete = config['reduction_catalog_complete']
        self.reduction_catalog_error = config['reduction_catalog_error']
        
        self.heart_beat = config['heart_beat']
        self.log_file = config['log_file'] if 'log_file' in config else 'post_processing.log'
        self.start_script = config['start_script'] if 'start_script' in config else 'startJob.sh'
        self.task_script = config['task_script'] if 'task_script' in config else 'PostProcessAdmin.py'
        self.python_dir = config['python_dir'] if 'python_dir' in config else os.path.join(self.sw_dir, 'postprocessing')
        self.script_dir = config['script_dir'] if 'script_dir' in config else os.path.join(self.sw_dir, 'scripts')
        self.mantid_path = config['mantid_path'] if 'mantid_path' in config else '/opt/Mantid/bin'
        self.dev_output_dir = config['dev_output_dir'] if 'dev_output_dir' in config else None
        
        self.max_nodes = config['max_nodes'] if 'max_nodes' in config else 32
        self.max_memory = config['max_memory'] if 'max_memory' in config else 8.0
        self.max_procs = config['max_procs'] if 'max_procs' in config else 5
        self.web_monitor_url = config['webmon_url_template'] if 'webmon_url_template' in config else "https://monitor.sns.gov/files/$instrument/$run_number/submit_reduced/"
        
        sys.path.insert(0, self.sw_dir)

# Set the log level for the Stomp client
stomp_logger = logging.getLogger('stompest.sync.client')
stomp_logger.setLevel(logging.ERROR)

def read_configuration(config_file):
    """
        Returns a new configuration object for a given
        configuration file
        @param config_file: configuration file to process
    """
    return Configuration(config_file)

## Configuration object
configuration = read_configuration(CONFIG_FILE)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(process)d/%(threadName)s: %(message)s",
    filename=configuration.log_file,
    filemode='a'
)

#stdout_logger = logging.getLogger('STDOUT')
#sl = StreamToLogger(stdout_logger, logging.INFO)
#sys.stdout = sl

stderr_logger = logging.getLogger('STDERR')
sl = StreamToLogger(stderr_logger, logging.ERROR)
sys.stderr = sl
