"""
ActiveMQ post-processing consumer.

The original code for this class was take from https://github.com/mantidproject/autoreduce

@copyright: 2014 Oak Ridge National Laboratory
"""
import json, logging, time, subprocess, sys, socket
import os

from twisted.internet import reactor, defer
from stompest import async, sync  # noqa: E999
from stompest.config import StompConfig
from stompest.async.listener import SubscriptionListener
from stompest.protocol import StompSpec, StompFailoverUri


class Consumer(object):
    """
    ActiveMQ consumer
    """

    def __init__(self, config):
        self.stompConfig = StompConfig(
            config.failover_uri,
            config.amq_user,
            config.amq_pwd,
            version=StompSpec.VERSION_1_1,
        )
        self.config = config
        self.procList = []
        self.instrument_jobs = {}

    @defer.inlineCallbacks
    def run(self):
        """
        Run method to start listening
        """
        client = async.Stomp(self.stompConfig)
        yield client.connect()
        headers = {
            # client-individual mode is necessary for concurrent processing
            # (requires ActiveMQ >= 5.2)
            StompSpec.ACK_HEADER: StompSpec.ACK_CLIENT_INDIVIDUAL,
            # the maximal number of messages the broker will let you work on at the same time
            "activemq.prefetchSize": "1",
        }
        if self.config.heartbeat_ping not in self.config.queues:
            self.config.queues.append(self.config.heartbeat_ping)
        for q in self.config.queues:
            headers[StompSpec.ID_HEADER] = "post-proc-service-%s" % q
            client.subscribe(
                q,
                headers,
                listener=SubscriptionListener(
                    self.consume,
                    ack=False,
                    errorDestination=self.config.postprocess_error,
                ),
            )
        try:
            client = yield client.disconnected
        except:
            logging.error("Connection error: %s" % sys.exc_value)
        reactor.callLater(5, self.run)

    def consume(self, client, frame):
        """
        Consume an AMQ message.

        Configuration note:
        The Configuration.limit_instrument_rate parameter can be set to a number
        greater than zero to limit the number of jobs running for an instrument
        at any given time. When using this option, you MUST put the following in
        your activemq.xml configuration. Otherwise, the rejected messages will
        not be redelivered (see http://activemq.apache.org/message-redelivery-and-dlq-handling.html)

        <plugins>
          <redeliveryPlugin fallbackToDeadLetter="true" sendToDlqIfMaxRetriesExceeded="true">
            <redeliveryPolicyMap>
              <redeliveryPolicyMap>
                <defaultEntry>
                  <redeliveryPolicy maximumRedeliveries="4" initialRedeliveryDelay="5000" redeliveryDelay="10000" />
                </defaultEntry>
              </redeliveryPolicyMap>
            </redeliveryPolicyMap>
          </redeliveryPlugin>
        </plugins>

        @param client: Stomp connection object
        @param frame: StompFrame object
        """
        try:
            headers = frame.headers
            destination = headers["destination"]
            data = frame.body
            data_dict = json.loads(data)
            # If we received a ping request, just ack
            if self.config.heartbeat_ping in destination:
                self.ack_ping(data_dict)
                client.ack(frame)
                return
            logging.info("Received %s: %s" % (destination, data))
            instrument = None
            if self.config.jobs_per_instrument > 0 and "instrument" in data_dict:
                instrument = data_dict["instrument"].upper()
                if instrument in self.instrument_jobs:
                    self.update_processes()
                    if (
                        len(self.instrument_jobs[instrument])
                        >= self.config.jobs_per_instrument
                    ):
                        client.nack(frame)
                        logging.error(
                            "Too many jobs for %s on %s: rejecting"
                            % (instrument, os.getpid())
                        )
                        return
                else:
                    self.instrument_jobs[instrument] = []
            client.ack(frame)
        except:
            logging.error(sys.exc_value)
            # Raising an exception here may result in an ActiveMQ result being sent.
            # We therefore pick a message that will mean someone to the users.
            raise RuntimeError, "Error processing incoming message: contact post-processing expert"

        try:
            # Put together the command to execute, including any optional arguments
            post_proc_script = os.path.join(
                self.config.python_dir, self.config.task_script
            )
            command_args = [self.config.start_script, post_proc_script]

            # Format the queue name argument
            if self.config.task_script_queue_arg is not None:
                command_args.append(self.config.task_script_queue_arg)
            command_args.append(destination)

            # Format the data argument
            if self.config.task_script_data_arg is not None:
                command_args.append(self.config.task_script_data_arg)
            command_args.append(str(data).replace(" ", ""))

            logging.debug("Command: %s" % str(command_args))
            proc = subprocess.Popen(command_args)
            self.procList.append(proc)
            if instrument is not None:
                self.instrument_jobs[instrument].append(proc)

            # Check whether the maximum number of processes has been reached
            max_procs_reached = len(self.procList) > self.config.max_procs
            if max_procs_reached:
                logging.info(
                    "Maxmimum number of sub-processes reached: %s" % len(self.procList)
                )

            # If we have reached the max number of processes, block until we have
            # at least on free slot
            while len(self.procList) > self.config.max_procs:
                time.sleep(1.0)
                self.update_processes()

            if max_procs_reached:
                logging.info(
                    "Resuming. Number of sub-processes: %s" % len(self.procList)
                )
            self.update_processes()
        except:
            logging.error(sys.exc_value)
            # Raising an exception here may result in an ActiveMQ result being sent.
            # We therefore pick a message that will mean someone to the users.
            raise RuntimeError, "Error processing message: contact post-processing expert"

    def update_processes(self):
        """
        Go through finished processed and process any log that came
        out of them.
        """
        for i in self.procList:
            if i.poll() is not None:
                for instrument in self.instrument_jobs:
                    if i in self.instrument_jobs[instrument]:
                        self.instrument_jobs[instrument].remove(i)
                self.procList.remove(i)

    def heartbeat(self, destination=None, data_dict={}):
        """
        Send heartbeats at a regular time interval
        @param: destination where to send the heartbeat
        @param data_dict: optional dictionary to pass along
        """
        try:
            if destination is None:
                destination = self.config.heart_beat
            stomp = sync.Stomp(self.stompConfig)
            stomp.connect()
            if not type(data_dict) == dict:
                logging.error("Heartbeat argument data_dict was not a dict")
                data_dict = {}
            data_dict.update(
                {
                    "src_name": socket.gethostname(),
                    "role": "postprocessing",
                    "status": "0",
                    "pid": str(os.getpid()),
                }
            )
            stomp.send(destination, json.dumps(data_dict))
            stomp.disconnect()
        except:
            logging.error("Could not send heartbeat: %s" % sys.exc_value)

    def ack_ping(self, data):
        """
        Send an ACK message in response to a ping
        @param data: data that was received with the ping request
        """
        if "reply_to" in data:
            self.heartbeat(data["reply_to"], data)
        else:
            logging.error("Incomplete ping request %s" % str(data))
