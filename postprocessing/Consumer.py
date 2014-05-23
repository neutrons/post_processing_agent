"""
    ActiveMQ post-processing consumer.
    
    The original code for this class was take from https://github.com/mantidproject/autoreduce
    
    @copyright: 2014 Oak Ridge National Laboratory
"""
import json, logging, time, subprocess, sys, socket
import os

from twisted.internet import reactor, defer
from stompest import async, sync
from stompest.config import StompConfig
from stompest.async.listener import SubscriptionListener
from stompest.protocol import StompSpec, StompFailoverUri


class Consumer(object):
    """
        ActiveMQ consumer
    """
    def __init__(self, config):
        self.stompConfig = StompConfig(config.uri, config.amq_user, config.amq_pwd)
        self.config = config
        self.procList = []
        
    @defer.inlineCallbacks
    def run(self):
        """
            Run method to start listening
        """
        self.heartbeat()
        client = yield async.Stomp(self.stompConfig).connect()
        headers = {
            # client-individual mode is necessary for concurrent processing
            # (requires ActiveMQ >= 5.2)
            StompSpec.ACK_HEADER: StompSpec.ACK_CLIENT_INDIVIDUAL,
            # the maximal number of messages the broker will let you work on at the same time
            'activemq.prefetchSize': '1',
        }
        for q in self.config.queues:
            client.subscribe(q, headers, listener=SubscriptionListener(self.consume, errorDestination=self.config.postprocess_error))
        try:
            client = yield client.disconnected
        except:
            reactor.callLater(5, self.run)
            
    def consume(self, client, frame):
        """
            Consume an AMQ message.
            @param client: Stomp connection object
            @param frame: StompFrame object
        """
        try:
            headers = frame.headers
            destination = headers['destination']
            data = frame.body
            logging.info("Received %s: %s" % (destination, data))
            
            post_proc_script = os.path.join(self.config.python_dir, self.config.task_script)
            proc = subprocess.Popen([self.config.start_script, post_proc_script, destination, str(data).replace(' ','') ],
                                    stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            self.procList.append(proc)
            
            # Check whether the maximum number of processes has been reached
            max_procs_reached = len(self.procList) > self.config.max_procs
            if max_procs_reached:
                logging.debug("Maxmimum number of sub-processes reached: %s" % len(self.procList))
                
            # If we have reached the max number of processes, block until we have
            # at least on free slot
            while len(self.procList) > self.config.max_procs:
                time.sleep(1.0)
                self.update_processes()
                
            if max_procs_reached:
                logging.debug("Resuming. Number of sub-processes: %s" % len(self.procList))
            self.update_processes()
        except:
            logging.error(sys.exc_value)
            # Raising an exception here may result in an ActiveMQ result being sent.
            # We therefore pick a message that will mean someone to the users.
            raise RuntimeError, "Error processing incoming message: contact post-processing expert"
        
    def update_processes(self):
        """
            Go through finished processed and process any log that came
            out of them.
        """
        for i in self.procList:
            if i.poll() is not None:
                logging.info(i.stdout.read())
                logging.error(i.stderr.read())
                self.procList.remove(i)
                
    def heartbeat(self):
        """
            Send heartbeats at a regular time interval
        """
        try:
            stomp = sync.Stomp(self.stompConfig)
            stomp.connect()
            data_dict = {"src_name": socket.gethostname(), "status": "0", "pid": str(os.getpid())}
            stomp.send(self.config.heart_beat, json.dumps(data_dict))
            stomp.disconnect()
        except:
            logging.error("Could not send heartbeat: %s" % sys.exc_value)
        reactor.callLater(30.0, self.heartbeat)
