"""
"""
import os
import logging
import json
import subprocess

class BaseProcessor(object):
    """
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
        """
        self.data = data
        self.configuration = conf
        self._process_data(data)
        self._send_function = send_function
    
    @classmethod
    def get_input_queue_name(cls):
        return cls._message_queue

    def _run_local_job(self, job_info, run_options, common_properties):
        """
            Run a local job and wait for its completion.
            
            @param job_info: job description dictionary
            @param run_options: options for running the job
            @param common_properties: properties common to all jobs
        """
        # Check for script information, or Mantid algorithm
        algorithm = ''
        script = ''
        if 'script' in job_info:
            script = job_info['script']
        elif 'algorithm' in job_info:
            # The following should be a standard script that runs the 
            # designated algorithm
            script = 'run_mantid_algorithm.py'
            algorithm = job_info['algorithm']
        
        # Check that the script exists
        if not os.path.isfile(script):
            self.process_error(self.configuration.reduction_error, 
                               "Script %s does not exist" % str(script))
        cmd = "python %s %s %s/" % (script, self.data_file, self.output_dir)
        
        out_log = os.path.join(self.log_dir, os.path.basename(self.data_file) + ".log")
        out_err = os.path.join(self.log_dir, os.path.basename(self.data_file) + ".err")
        logFile=open(out_log, "a")
        errFile=open(out_err, "a")
        if self.configuration.comm_only is False:
            proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                                    stdout=logFile, stderr=errFile, universal_newlines = True)
            proc.communicate()
        logFile.close()
        errFile.close()
        errFile = open(out_err, 'r')
        if len(errFile.read())>0:
            self.process_error(self.configuration.reduction_error, 
                               "Errors found")
        
    def _run_remote_jobs(self, job_info, run_options, common_properties):
        """
            Run a set of jobs with dependencies.
            
            @param job_info: job description dictionary
            @param run_options: options for running the job
            @param common_properties: properties common to all jobs
        """
        print "Not yet implemented"
        
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
        # Reset the error
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