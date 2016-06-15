"""
    The base processor defines a base class to be used to process jobs.
    An input AMQ queue is defined. The post-processing client will 
    automatically register with that queue upon starting.

    @copyright: 2014-2015 Oak Ridge National Laboratory
"""
import os
import logging
import json
import string
import job_handling

class BaseProcessor(object):
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

    def _get_script_path(self, job_name, job_info, run_options, common_properties):
        """
            Determine which script to run.
            @param job_name: a name for the job
            @param job_info: job description dictionary
            @param run_options: options for running the job
            @param common_properties: properties common to all jobs
        """
        # Check for script information, or Mantid algorithm
        script = ''
        if 'script' in job_info:
            script = job_info['script']
        elif 'algorithm' in job_info:
            # The following should be a standard script that runs the 
            # designated algorithm
            properties = common_properties
            properties['Filename'] = self.data_file
            properties.update(job_info['alg_properties'])

            script_template = os.path.join(self.configuration.sw_dir, 'scripts', 'run_mantid_algorithm.py_template')
            template_content = open(script_template).read()
            # Replace the dictionary entries
            template = string.Template(template_content)
            script_content = template.substitute({'algorithm': job_info['algorithm'],
                                          'algorithm_properties': properties})
            script = os.path.join(self.output_dir, "mantid_script_%s.py" % job_name)
            script_file = open(script, 'w')
            script_file.write(script_content)
            script_file.close()
        return script

    def _run_job(self, job_name,  job_info, run_options, common_properties, 
                 wait=True, dependencies=[]):
        """
            Run a local job and wait for its completion.
            @param job_name: a name for the job
            @param job_info: job description dictionary
            @param run_options: options for running the job
            @param common_properties: properties common to all jobs
            @param wait: if True, we will wait for the job to finish before returning
            @param dependencies: list of job dependencies
        """
        # Check for script information, or Mantid algorithm
        script = self._get_script_path(job_name, job_info, run_options, common_properties)

        # Check that the script exists
        if not os.path.isfile(script):
            self.process_error(self.configuration.reduction_error, 
                               "Script %s does not exist" % str(script))

        # Remove old log files
        out_log = os.path.join(self.log_dir, "%s.%s.log" % (os.path.basename(self.data_file), job_name))
        out_err = os.path.join(self.log_dir, "%s.%s.err" % (os.path.basename(self.data_file), job_name))
        if os.path.isfile(out_err):
            os.remove(out_err)
        if os.path.isfile(out_log):
            os.remove(out_log)

        if 'remote' in run_options and run_options['remote'] is True:
            node_request = None
            if "node_request" in job_info:
                node_request = job_info["node_request"]
            job_id = job_handling.remote_submission(self.configuration, script, self.data_file, 
                                                    self.output_dir, out_log, out_err, 
                                                    wait, dependencies, node_request=node_request)
        else:
            job_id = job_handling.local_submission(self.configuration, script, self.data_file, 
                                                   self.output_dir, out_log, out_err)

        return job_id, out_log, out_err

    def _process_data(self, data):
        """
            Retrieve run information from the data dictionary
            provided with an incoming message.
            @param data: data dictionary
        """
        if data.has_key('data_file'):
            self.data_file = str(data['data_file'])
            if os.access(self.data_file, os.R_OK) == False:
                raise ValueError("Data file does not exist or is not readable")
        else:
            raise ValueError("data_file is missing")

        if data.has_key('facility'):
            self.facility = str(data['facility']).upper()
        else: 
            raise ValueError("Facility is missing")

        if data.has_key('instrument'):
            self.instrument = str(data['instrument']).upper()
        else:
            raise ValueError("Instrument is missing")

        if data.has_key('ipts'):
            self.proposal = str(data['ipts']).upper()
        else:
            raise ValueError("IPTS is missing")

        if data.has_key('run_number'):
            self.run_number = str(data['run_number'])
        else:
            raise ValueError("Run number is missing")

        self.proposal_shared_dir = os.path.join('/', self.facility, self.instrument, self.proposal, 'shared', 'autoreduce')
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
        self.send('/queue/%s' % destination , json.dumps(self.data))
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
            print "NOT SEND TO AMQ", destination, message