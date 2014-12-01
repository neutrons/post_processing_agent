"""
"""
import os
import logging
import json

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
    
    def run_job(self, job_info, run_options, common_properties):
        """
            Run a job.
            @param job_info: job description dictionary
            @param run_options: options for running the job
            @param common_properties: properties common to all jobs

            job_info is a dictionary containing the following information:
            job_info = {
                        'algorithm': 'some mantid algorithm to run',
                        'script': 'script to run if no algorithm is provided',
                        'alg_properties': {},
                        'predecessors': [list of IDs]
                       }
        """
        # Check whether we need to run locally or remotely
        is_remote = False
        if 'remote' in run_options and run_options['remote'] is True:
            is_remote = True
            
        if is_remote:
            _run_remote_job(job_info, run_options, common_properties)
        else:
            _run_local_job(job_info, run_options, common_properties)
    
    def _run_local_job(self, job_info, run_options, common_properties):
        """
            Run a local job
            @param job_info: job description dictionary
            @param run_options: options for running the job
            @param common_properties: properties common to all jobs
        """
        # Check for script information, or Mantid algorithm
        algorithm = ''
        if 'script' in job_info:
            script = job_info['script']
        elif 'algorithm' in job_info:
            # The following should be a standard script that runs the 
            # designated algorithm
            script = 'run_mantid_algorithm.py'
            algorithm = job_info['algorithm']
        
        cmd = "python %s %s %s/" % (script, self.data_file, output_dir)
        logFile=open(out_log, "w")
        errFile=open(out_err, "w")
        if self.conf.comm_only is False:
            proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                                    stdout=logFile, stderr=errFile, universal_newlines = True)
            proc.communicate()
        logFile.close()
        errFile.close()
        
    def _run_remote_job(job_info, run_options, common_properties):
        """
            Run a remote job
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
        
    def process_error(self, destination, message):
        """
            Log and send error message
            
            @param destination: queue to send the error to
            @param message: error message
        """
        error_message = "%s: %s" % (type(self).__name__, message)
        logging.error(error_message)
        self.data["error"] = error_message
        
        if self.send_function is not None:
            self.send_function('/queue/%s' % destination , json.dumps(self.data))
