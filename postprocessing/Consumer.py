"""
ActiveMQ post-processing consumer.

The original code for this class was take from https://github.com/mantidproject/autoreduce

@copyright: 2014 Oak Ridge National Laboratory
"""
import json
import logging
import time
import subprocess
import sys
import socket
import os
import signal
import stomp

HEARTBEAT_DELAY = 30


class Listener(stomp.ConnectionListener):
    def __init__(self, config, connection):
        super().__init__()
        self.config = config
        self.conn = connection
        self.procList = []
        self.instrument_jobs = {}

    def on_message(self, frame):
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
                self.conn.ack(
                    frame.headers["message-id"], frame.headers["subscription"]
                )
                return
            logging.info("Received %s: %s", destination, data)
            instrument = None
            if self.config.jobs_per_instrument > 0 and "instrument" in data_dict:
                instrument = data_dict["instrument"].upper()
                if instrument in self.instrument_jobs:
                    self.update_processes()
                    if (
                        len(self.instrument_jobs[instrument])
                        >= self.config.jobs_per_instrument
                    ):
                        self.conn.nack(
                            frame.headers["message-id"], frame.headers["subscription"]
                        )
                        logging.error(
                            "Too many jobs for %s on %s: rejecting",
                            instrument,
                            os.getpid(),
                        )
                        return
                else:
                    self.instrument_jobs[instrument] = []
            self.conn.ack(frame.headers["message-id"], frame.headers["subscription"])
        except:  # noqa: E722
            logging.error(sys.exc_info()[1])
            # Raising an exception here may result in an ActiveMQ result being sent.
            # We therefore pick a message that will mean someone to the users.
            raise RuntimeError(
                "Error processing incoming message: contact post-processing expert"
            )

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

            logging.warning("Command: %s", str(command_args))

            ### open and log subprocess
            proc = subprocess.Popen(
                command_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )  ### start subprocess

            for line in proc.stdout.readlines():  ### log with custom level
                logging.subprocess(line.decode().strip())

            logging.warning("end")
            self.procList.append(proc)
            if instrument is not None:
                self.instrument_jobs[instrument].append(proc)

            # Check whether the maximum number of processes has been reached
            max_procs_reached = len(self.procList) > self.config.max_procs
            if max_procs_reached:
                logging.info(
                    "Maxmimum number of sub-processes reached: %s", len(self.procList)
                )

            # If we have reached the max number of processes, block until we have
            # at least on free slot
            while len(self.procList) > self.config.max_procs:
                time.sleep(1.0)
                self.update_processes()

            if max_procs_reached:
                logging.info(
                    "Resuming. Number of sub-processes: %s", len(self.procList)
                )
            self.update_processes()
        except:  # noqa: E722
            logging.error(sys.exc_info()[1])
            # Raising an exception here may result in an ActiveMQ result being sent.
            # We therefore pick a message that will mean someone to the users.
            raise RuntimeError(
                "Error processing message: contact post-processing expert"
            )

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

    def ack_ping(self, data):
        """
        Send an ACK message in response to a ping
        @param data: data that was received with the ping request
        """
        if "reply_to" in data:
            heartbeat(self.conn, data["reply_to"], data)
        else:
            logging.error("Incomplete ping request %s", str(data))


def heartbeat(conn, destination, data_dict={}):
    """
    Send heartbeats at a regular time interval
    @param: destination where to send the heartbeat
    @param data_dict: optional dictionary to pass along
    """

    try:
        if not isinstance(data_dict, dict):
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
        conn.send(destination, json.dumps(data_dict).encode())
    except:  # noqa: E722
        logging.error("Could not send heartbeat: %s", sys.exc_info()[1])


class Consumer:
    """
    ActiveMQ consumer
    """

    def __init__(self, config):
        self.config = config
        self.procList = []
        self.instrument_jobs = {}
        self._connection = None
        self._exit = False

        # Signals registered for systemd
        signal.signal(signal.SIGTERM, self.exit_gracefully)
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGQUIT, self.exit_gracefully)

    def exit_gracefully(self, *args):
        """
        Tells Consumer to stop listening after current job is finished
        """
        self._exit = True

    def get_connection(self, listener=None):
        """
        Establish and return a connection to ActiveMQ

        :param listener: listener object
        """
        conn = stomp.Connection(host_and_ports=self.config.brokers, keepalive=True)

        listener = Listener(self.config, conn)

        conn.set_listener("postprocessing", listener)
        conn.connect(self.config.amq_user, self.config.amq_pwd, wait=True)

        time.sleep(0.5)
        return conn

    def connect(self):
        """
        Connect to a broker
        """
        if self._connection is None or not self._connection.is_connected():
            self._disconnect()
            self._connection = self.get_connection()

            if self.config.heartbeat_ping not in self.config.queues:
                self.config.queues.append(self.config.heartbeat_ping)

        for q in self.config.queues:
            self._connection.subscribe(destination=q, id=q, ack="client")

    def _disconnect(self):
        """
        Clean disconnect
        """
        if self._connection is not None and self._connection.is_connected():
            self._connection.disconnect()
        self._connection = None

    def listen_and_wait(self, waiting_period=1.0):
        """
        Listen for the next message from the brokers.
        This method will simply return once the connection is
        terminated.

        :param waiting_period: sleep time between connection to a broker
        """

        last_heartbeat = 0
        while not self._exit:
            try:
                if self._connection is None or self._connection.is_connected() is False:
                    self.connect()

                try:
                    if time.time() - last_heartbeat > HEARTBEAT_DELAY:
                        last_heartbeat = time.time()
                        heartbeat(self._connection, self.config.heart_beat)
                except:  # noqa: E722
                    logging.exception("Problem writing heartbeat")

                time.sleep(waiting_period)
            except:  # noqa: E722
                logging.exception("Problem connecting to AMQ broker")
                time.sleep(5.0)
