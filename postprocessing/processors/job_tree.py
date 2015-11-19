"""
    Job tree processor. A series of jobs are defined in 
    /SNS/[instrument]/shared/autoreduce/reduce_[instrument].config.
    
    When a message is sent to the appropriate AMQ queue, those jobs
    will be ordered according to their dependencies and executed.
    
    @copyright: 2014 Oak Ridge National Laboratory
"""
from base_processor import BaseProcessor
import os
import json
import socket

class JobTreeProcessor(BaseProcessor):
    """
        Process used to execute a list of inter-dependent jobs.
    """
    ## Input queue
    _message_queue = "/queue/REDUCTION.JOBTREE.DATA_READY"
    
    def __init__(self, data, conf, send_function):
        """
            Initialize the processor
            
            @param data: data dictionary from the incoming message
            @param conf: configuration object
             @param send_function: function to call to send an AMQ message
        """
        super(JobTreeProcessor, self).__init__(data, conf, send_function)
        self.log_dir = os.path.join(self.proposal_shared_dir, "reduction_log")
        if not os.path.exists(self.log_dir):
                os.makedirs(self.log_dir)
    
    def __call__(self):
        """
            Determines what jobs we need to submit
            
            config['jobs'] = {'some ID': {
                                          'algorithm': 'some mantid algorithm to run',
                                          'script': 'script to run if no algorithm is provided',
                                          'alg_properties': {},
                                          'predecessors': [list of IDs]
                                          }
                             }
        """
        self.send('/queue/'+self.configuration.reduction_started, json.dumps(self.data))
        
        instrument_shared_dir = os.path.join('/', self.facility, self.instrument, 'shared', 'autoreduce')

        # Find the reduce_*.config file
        config_file = os.path.join(instrument_shared_dir, 'reduce_%s.config' % self.instrument.upper())
        if not os.path.isfile(config_file):
            self.process_error(self.configuration.reduction_error, "%s does not exist" % config_file)
            return
        
        # Process the config file
        content = open(config_file, 'r').read()
        config = json.loads(content)
        # Check for completeness
        for key in ['jobs', 'run_options', 'common_properties']:
            if key not in config.keys():
                self.process_error(self.configuration.reduction_error, "No '%s' key in configuration" % key)
                return
        # Order up the jobs
        job_submission = []
        jobs_sorted = False
        while(jobs_sorted is False):
            for name, job in config['jobs'].iteritems():
                if name in job_submission:
                    continue
                # If we don't have a predecessor, just add the job to the submission list
                if 'predecessors' not in job.keys():
                    job_submission.append(name)
                else:
                    # Loop through predecessors
                    can_submit = True
                    for pred in job['predecessors']:
                        if pred in config['jobs']:
                            can_submit = can_submit and pred in job_submission
                        else:
                            self.process_error(self.configuration.reduction_error, 
                                               "Predecessor '%s' does not exist" % pred)
                    if can_submit:
                        job_submission.append(name)
            
            jobs_sorted = len(job_submission) >= len(config['jobs'].keys())
            
        # Run the jobs in order
        self.run_jobs(job_submission, config['jobs'], config['run_options'], config['common_properties'])
        
        return job_submission
        
    def run_jobs(self, job_order, job_info, run_options, common_properties):
        """
            Run a list of jobs
            
            job_info is a dictionary containing the following information:
            job_info = {
                        'algorithm': 'some mantid algorithm to run',
                        'script': 'script to run if no algorithm is provided',
                        'alg_properties': {},
                        'predecessors': [list of IDs]
                       }

            @param job_order: ordered list of job names
            @param job_info: dictionary describing each job
            @param run_options: general run options for submitting the jobs
            @param common_properties: common properties for the jobs
        """
        # Remove old log files
        out_log = os.path.join(self.log_dir, os.path.basename(self.data_file) + ".log")
        out_err = os.path.join(self.log_dir, os.path.basename(self.data_file) + ".err")
        if os.path.isfile(out_err):
            os.remove(out_err)
        if os.path.isfile(out_log):
            os.remove(out_log)

        # Run each job, one at a time, in order
        job_ids = {}
        for i in range(len(job_order)):
            item = job_order[i]
            
            # For remote jobs, only wait on the last job and let the scheduling system
            # take care of the dependencies
            wait = 'remote' in run_options and run_options['remote'] is True and i == len(job_order)-1
            if not 'remote' in run_options or run_options['remote'] is False:
                wait = i == len(job_order)-1
            
            if item in job_info:
                # Check for completeness
                if 'script' not in job_info[item] and 'algorithm' not in job_info[item]:
                    self.process_error(self.configuration.reduction_error, 
                                       "JobTreeProcessor: no job to run for [%s]" % item)
                    continue
                
                self.data['information'] = "Job [%s] started on %s" % (item, socket.gethostname())
                self.send('/queue/'+self.configuration.reduction_started, json.dumps(self.data))
                
                # Sort out the job dependencies
                deps = []
                if 'predecessors' in job_info[item]:
                    for dep in job_info[item]['predecessors']:
                        if dep in job_ids:
                            deps.append(str(job_ids[dep]))
                        else:
                            self.process_error(self.configuration.reduction_error, 
                                               "JobTreeProcessor: no job id for dependency [%s]" % dep)
                            
                job_ids[item] = self._run_job(item, job_info[item], run_options, common_properties, 
                                              wait, dependencies=deps)
                if wait:
                    self.data['information'] = "Last job [%s] ended on %s" % (item, socket.gethostname())
                    self.send('/queue/'+self.configuration.reduction_complete, json.dumps(self.data))
            else:
                self.process_error(self.configuration.reduction_error, 
                                   "JobTreeProcessor: job %s does not exist in job dictionary" % item)
