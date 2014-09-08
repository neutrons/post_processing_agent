#!/usr/bin/env python
"""
    Post-processing tasks
    
    The original code for this class was take from https://github.com/mantidproject/autoreduce
    
    Example input dictionaries:
    {"information": "mac83808.sns.gov", "run_number": "30892", "instrument": "EQSANS", "ipts": "IPTS-10674", "facility": "SNS", "data_file": "/Volumes/RAID/SNS/EQSANS/IPTS-10674/0/30892/NeXus/EQSANS_30892_event.nxs"}
    {"information": "autoreducer1.sns.gov", "run_number": "85738", "instrument": "CNCS", "ipts": "IPTS-10546", "facility": "SNS", "data_file": "/SNS/CNCS/IPTS-10546/0/85738/NeXus/CNCS_85738_event.nxs"}
    
    @copyright: 2014 Oak Ridge National Laboratory
"""
import logging, json, socket, os, sys, subprocess, time, glob, requests
import re
import string
from stompest.config import StompConfig
from stompest.sync import Stomp

class PostProcessAdmin:
    def __init__(self, data, conf):
        logging.debug("json data: %s [%s]" % (str(data), type(data)))
        if not type(data) == dict:
            raise ValueError, "PostProcessAdmin expects a data dictionary"
        data["information"] = socket.gethostname()
        self.data = data
        self.conf = conf
        
        # List of error messages to be handled as information
        self.exceptions = self.conf.exceptions

        stompConfig = StompConfig(self.conf.failover_uri, self.conf.amq_user, self.conf.amq_pwd)
        self.client = Stomp(stompConfig)
        
        self.data_file = None
        self.facility = None
        self.instrument = None
        self.proposal = None
        self.run_number = None
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

    def reduce(self, remote=False):
        """
            Reduction process using job submission.
            @param remote: If True, the job will be submitted to a compute node
        """
        try:
            self.send('/queue/'+self.conf.reduction_started, json.dumps(self.data))
            instrument_shared_dir = os.path.join('/', self.facility, self.instrument, 'shared', 'autoreduce')
            proposal_shared_dir = os.path.join('/', self.facility, self.instrument, self.proposal, 'shared', 'autoreduce')
            log_dir = os.path.join(proposal_shared_dir, "reduction_log")
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            # Allow for an alternate output directory, if defined
            if len(self.conf.dev_output_dir.strip())>0:
                proposal_shared_dir = self.conf.dev_output_dir
            logging.info("Using output directory: %s" % proposal_shared_dir)
            
            # Look for run summary script
            summary_script = os.path.join(instrument_shared_dir, "sumRun_%s.py" % self.instrument)
            if os.path.exists(summary_script) == True:
                summary_output = os.path.join(proposal_shared_dir, "%s_%s_runsummary.csv" % (self.instrument, self.proposal))
                cmd = "python " + summary_script + " " + self.instrument + " " + self.data_file + " " + summary_output
                logging.debug("Run summary subprocess started: " + cmd)
                subprocess.call(cmd, shell=True)
                logging.debug("Run summary subprocess completed, see " + summary_output)

            # Look for auto-reduction script
            reduce_script_path = os.path.join(instrument_shared_dir, "reduce_%s.py" % self.instrument)
            if os.path.exists(reduce_script_path) == False:
                self.send('/queue/' + self.conf.reduction_disabled, json.dumps(self.data))
                return
            
            monitor_user = {'username': self.conf.amq_user, 'password': self.conf.amq_pwd}
            
            # Run the reduction
            out_log = os.path.join(log_dir, os.path.basename(self.data_file) + ".log")
            out_err = os.path.join(log_dir, os.path.basename(self.data_file) + ".err")
            if remote:
                self.remote_reduction(reduce_script_path, proposal_shared_dir, out_log, out_err)
            else:
                self.local_reduction(reduce_script_path, proposal_shared_dir, out_log, out_err)
                
            # If the reduction succeeded, upload the images we might find in the reduction directory
            success = not os.path.isfile(out_err) or os.stat(out_err).st_size == 0
            if not success:
                # Go through each line and report the error message.
                # If we can't fine the actual error, report the last line
                last_line = None
                error_line = None
                fp=file(out_err, "r")
                for l in fp.readlines():
                    if len(l.replace('-','').strip())>0:
                        last_line = l.strip()
                    result = re.search('Error: ([\w ]+)$',l)
                    if result is not None:
                        error_line = result.group(1)
                if error_line is None:
                    error_line = last_line
                for item in self.exceptions:
                    if re.search(item, error_line):
                        success = True
                        self.data["information"] = error_line
                        logging.error("Reduction error ignored: %s" % error_line)
                
                if not success:
                    self.data["error"] = "REDUCTION: %s" % error_line
                    self.send('/queue/'+self.conf.reduction_error , json.dumps(self.data))
            
            if success:
                if os.path.isfile(out_err):
                    os.remove(out_err)
                self.send('/queue/'+self.conf.reduction_complete , json.dumps(self.data))
                
                # Send image to the web monitor
                if len(self.conf.web_monitor_url.strip())>0:
                    url_template = string.Template(self.conf.web_monitor_url)
                    url = url_template.substitute(instrument=self.instrument, run_number=self.run_number)
    
                    pattern=self.instrument+"_"+self.run_number+"*"
                    for dirpath, dirnames, filenames in os.walk(proposal_shared_dir):
                        listing = glob.glob(os.path.join(dirpath, pattern))
                        for filepath in listing:
                            f, e = os.path.splitext(filepath)
                            if e.startswith(os.extsep):
                                e = e[len(os.extsep):]
                                if e == "png" or e == "jpg":
                                    files={'file': open(filepath, 'rb')}
                                    # Post the image if it's small enough
                                    if len(files) != 0 and os.path.getsize(filepath) < self.conf.max_image_size:
                                        request=requests.post(url, data=monitor_user, files=files, verify=False)
                                        logging.info("Submitted %s [status: %s]" % (filepath,
                                                                                   request.status_code))
        except:
            logging.error("reduce: %s" % sys.exc_value)
            self.data["error"] = "Reduction: %s " % sys.exc_value
            self.send('/queue/'+self.conf.reduction_error , json.dumps(self.data))

    def remote_reduction(self, script, output_dir, out_log, out_err):
        """
            Run auto-reduction remotely
            @param script: full path to the reduction script to run
            @param output_dir: reduction output directory
            @param out_log: reduction log file
            @param out_err: reduction error file
        """
        #MaxChunkSize is set to 8G specifically for the jobs run on fermi, which has 32 nodes and 64GB/node
        #We would like to get MaxChunkSize from an env variable in the future
        if self.conf.comm_only is False:
            import mantid.simpleapi as api
            chunks = api.DetermineChunking(Filename=self.data_file,MaxChunkSize=self.conf.max_memory)
            nodes_desired = min(chunks.rowCount(), self.conf.max_nodes)
            if nodes_desired == 0:
                nodes_desired = 1
        else:
            chunks = 1
            nodes_desired = 1
        logging.debug("Chunks: %s  / Nodes: %s" % (chunks, nodes_desired))
        
        # Build qsub command
        cmd_out = " -o %s -e %s" % (out_log, out_err)
        cmd_l = " -l nodes=%s:ppn=1" % nodes_desired
        cmd_v = " -v data_file='%s',n_nodes=%s,reduce_script='%s',proposal_shared_dir='%s/'" % (self.data_file, nodes_desired, script, output_dir)
        cmd = "qsub %s %s %s %s" % (cmd_out, cmd_l, cmd_v, self.conf.remote_script)
        logging.info("Reduction process: " + cmd)

        # If we are only dry-running, return immediately
        if self.conf.comm_only is True:
            return
        
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        
        # Catch errors in the job submission and raise them as exception
        proc_err = proc.stderr.read()
        if len(proc_err)>0:
            raise RuntimeError, proc_err
            
        # Read in the job ID
        proc_out = proc.stdout.read()
        toks = proc_out.split(".")
        if len(toks) > 0:
            pid = toks[0].rstrip()
        logging.info("Job ID: %s" % pid)
        
        # Wait for the job to finish
        t_0 = time.time()
        t_cycle = t_0
        while True:
            qstat_cmd = "qstat " + pid
            ret = subprocess.Popen(qstat_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True).stdout.read().rstrip()
            logging.debug("Popen return code: " + ret)
            if ret.startswith("qstat: Unknown Job Id") or \
               ret.endswith("C batch") or \
               len(ret)==0:
                break
            else:
                time.sleep(30)
            # If we've been waiting for more than a configured waiting time,
            # log the event as information
            if time.time()-t_cycle > self.conf.wait_notification_period:
                wait_time = time.time()-t_0
                t_cycle = time.time()
                logging.info("Waiting for job ID %s for more than %g seconds" % (pid, wait_time))
    
    def local_reduction(self, script, output_dir, out_log, out_err):
        """
            Run auto-reduction locally
            @param script: full path to the reduction script to run
            @param output_dir: reduction output directory
            @param out_log: reduction log file
            @param out_err: reduction error file
        """
        cmd = "python %s %s %s/" % (script, self.data_file, output_dir)
        logFile=open(out_log, "w")
        errFile=open(out_err, "w")
        if self.conf.comm_only is False:
            proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                                    stdout=logFile, stderr=errFile, universal_newlines = True)
            proc.communicate()
        logFile.close()
        errFile.close()

    def catalog_raw(self):
        """
            Catalog a nexus file containing raw data
        """        
        try:
            from ingest_nexus import IngestNexus
            self.send('/queue/'+self.conf.catalog_started, json.dumps(self.data))
            if self.conf.comm_only is False:
                ingestNexus = IngestNexus(self.data_file)
                ingestNexus.execute()
                ingestNexus.logout()
                self.send('/queue/'+self.conf.catalog_complete, json.dumps(self.data))  
        except:
            logging.error("catalog_raw: %s" % sys.exc_value)
            self.data["error"] = "Catalog: %s" % sys.exc_value
            self.send('/queue/'+self.conf.catalog_error, json.dumps(self.data))
            
    def catalog_reduced(self):
        """
            Catalog reduced data files for a given run
        """
        try:
            from ingest_reduced import IngestReduced
            self.send('/queue/'+self.conf.reduction_catalog_started, json.dumps(self.data))
            if self.conf.comm_only is False:
                ingestReduced = IngestReduced(self.facility, self.instrument, self.proposal, self.run_number)
                ingestReduced.execute()
                ingestReduced.logout()
            self.send('/queue/'+self.conf.reduction_catalog_complete , json.dumps(self.data))
        except:
            logging.error("catalog_reduced: %s" % sys.exc_value)
            self.data["error"] = "Reduction catalog: %s" % sys.exc_value
            self.send('/queue/'+self.conf.reduction_catalog_error , json.dumps(self.data))
            
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
    parser = argparse.ArgumentParser(description='Post-processing agent')
    parser.add_argument('-q', metavar='queue', help='ActiveMQ queue name', dest='queue', required=True)
    parser.add_argument('-c', metavar='config', help='Configuration file', dest='config')
    parser.add_argument('-d', metavar='data', help='JSON data', dest='data')
    parser.add_argument('-f', metavar='data_file', help='Nexus data file', dest='data_file')
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
                toks = file_name.split('_')
                if len(toks)>1:
                    data["instrument"] = toks[0].upper()
                    try:
                        data["run_number"] = str(int(toks[1]))
                    except:
                        logging.error("Could not determine run number")
                    ipts_toks = namespace.data_file.upper().split(toks[0].upper())
                    if len(ipts_toks)>1:
                        sep_toks = ipts_toks[1].split('/')
                        if len(sep_toks)>1:
                            data["ipts"] = sep_toks[1]
            else:
                raise RuntimeError, "Expected a JSON object or a file path"
        else:
            data = json.loads(namespace.data)
            
        # Process the data
        try:
            pp = PostProcessAdmin(data, configuration)
            if namespace.queue == '/queue/%s' % configuration.reduction_data_ready:
                pp.reduce(configuration.remote_execution)
            elif namespace.queue == '/queue/%s' % configuration.catalog_data_ready:
                pp.catalog_raw()
            elif namespace.queue == '/queue/%s' % configuration.reduction_catalog_data_ready:
                pp.catalog_reduced()
        except:
            # If we have a proper data dictionary, send it back with an error message
            if type(data) == dict:
                data["error"] = str(sys.exc_value)
                stomp = Stomp(StompConfig(configuration.failover_uri, configuration.amq_user, configuration.amq_pwd))
                stomp.connect()
                stomp.send(configuration.postprocess_error, json.dumps(data))
                stomp.disconnect()
            raise
    except:
        logging.error("PostProcessAdmin: %s" % sys.exc_value)
