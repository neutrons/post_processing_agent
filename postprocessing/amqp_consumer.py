"""
ActiveMQ post-processing consumer over AMQP 1.0.

The agent holds no credit on its queues, so the broker never hands it a message it isn't ready
for. When it's free it asks the next queue in turn for one message (a drain of 1), accepts it
and runs the job in a worker thread. That keeps runs spread across the autoreducers instead of
piling up behind a busy one, which STOMP can't do because it always prefetches at least one
message per subscription.

Like the STOMP consumer, each agent runs one job at a time.

@copyright: 2026 Oak Ridge National Laboratory
"""

import logging
import os
import signal
import socket
import subprocess
import threading

from proton import symbol
from proton.handlers import MessagingHandler
from proton.reactor import ApplicationEvent, Container, EventInjector, ReceiverOption

from postprocessing.Consumer import post_processing_command

# How long to wait after finding every queue empty before asking them all again
IDLE_RETRY_SEC = 1.0


class QueueSource(ReceiverOption):
    """
    Tell Artemis the address is a queue (anycast) and not a topic
    """

    def apply(self, receiver):
        receiver.source.capabilities.put_object(symbol("queue"))


def amqp_address(destination):
    """
    Turn a STOMP destination like /queue/REDUCTION.DATA_READY into the AMQP address
    """
    return destination.split("/", 2)[-1] if destination.startswith("/") else destination


class AmqpConsumer(MessagingHandler):
    """
    ActiveMQ consumer that pulls one message at a time over AMQP
    """

    def __init__(self, config):
        super().__init__(prefetch=0, auto_accept=False)
        self.config = config
        self.container = None
        self.connection = None
        self.injector = None

        # Queue destination -> input queue of its processor, which is what PostProcessAdmin expects
        self.input_queues = {}
        self.receivers = []
        self.opened = set()
        self.next_index = 0
        self.empty_in_a_row = 0
        # The receiver we asked for a message, while we wait for the answer
        self.pending = None
        self.busy = False
        self._exit = False

        for queue in config.queues:
            self.input_queues[queue] = queue

        # Signals registered for systemd
        signal.signal(signal.SIGTERM, self.exit_gracefully)
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGQUIT, self.exit_gracefully)

    def exit_gracefully(self, *args):
        """
        Tells the consumer to stop after the current job is finished
        """
        self._exit = True
        if self.injector is not None:
            self.injector.trigger(ApplicationEvent("exit_request"))

    def listen_and_wait(self, waiting_period=None):
        """
        Run until asked to exit. The waiting period is only there to match the STOMP consumer.
        """
        Container(self).run()

    def add_queue(self, queue, input_queue=None):
        """
        Start pulling from another queue
        @param queue: queue destination, like /queue/REDUCTION.CG2.DATA_READY
        @param input_queue: input queue of the processor for that queue, if different
        """
        self.input_queues[queue] = input_queue or queue
        if self.connection is not None:
            self._create_receiver(queue)

    def _create_receiver(self, queue):
        # The link name shows up in the broker console, so make it say who we are
        name = f"{socket.gethostname()}-{os.getpid()}-{queue}"
        receiver = self.container.create_receiver(
            self.connection, amqp_address(queue), name=name, options=QueueSource()
        )
        self.receivers.append((receiver, queue))

    # Connection

    def on_start(self, event):
        self.container = event.container
        self.injector = EventInjector()
        self.container.selectable(self.injector)
        urls = [f"amqp://{host}:{port}" for host, port in self.config.amqp_brokers]
        logging.info("Connecting over AMQP to %s", urls)
        self.connection = self.container.connect(
            urls=urls,
            user=self.config.amq_user,
            password=self.config.amq_pwd,
            allowed_mechs="PLAIN",
            allow_insecure_mechs=True,
        )
        for queue in list(self.input_queues):
            self._create_receiver(queue)
        logging.info("Pulling from %s", sorted(self.input_queues))
        if self._exit:
            self._stop()

    def on_link_opened(self, event):
        if event.receiver is None:
            return
        self.opened.add(event.receiver.name)
        self.next_queue()

    def on_link_closed(self, event):
        if event.receiver is not None and event.receiver.name in self.opened and not self._exit:
            logging.error("The broker closed the link for %s", event.receiver.source.address)
            self.opened.discard(event.receiver.name)
            if self.pending is not None and self.pending.name == event.receiver.name:
                self.pending = None
                self.next_queue()

    def on_disconnected(self, event):
        # proton reconnects and reopens the links by itself; start asking again once they're back
        logging.warning("Lost the AMQP connection, reconnecting")
        self.opened.clear()
        self.pending = None

    def on_transport_error(self, event):
        condition = event.transport.condition
        logging.error("AMQP connection error: %s", condition.description if condition else "unknown")

    # Pulling, all on the container thread

    def next_queue(self):
        """
        Ask the next queue for one message, unless we're busy or already waiting for one
        """
        if self.busy or self.pending is not None or self._exit or not self.opened:
            return
        if self.empty_in_a_row >= len(self.opened):
            # Every queue was empty: wait a moment before going round again
            self.empty_in_a_row = 0
            self.container.schedule(IDLE_RETRY_SEC, self)
            return
        # Take the next queue in turn, skipping any whose link isn't open
        for _ in range(len(self.receivers)):
            receiver, _queue = self.receivers[self.next_index % len(self.receivers)]
            self.next_index = (self.next_index + 1) % len(self.receivers)
            if receiver.name in self.opened:
                self.pending = receiver
                receiver.drain(1)
                return

    def on_timer_task(self, event):
        self.next_queue()

    def on_link_flow(self, event):
        receiver = event.receiver
        if (
            receiver is not None
            and self.pending is not None
            and receiver.name == self.pending.name
            and receiver.credit == 0
            and not receiver.draining()
        ):
            # The drain came back empty, so that queue has nothing for us
            self.pending = None
            self.empty_in_a_row += 1
            self.next_queue()

    def on_message(self, event):
        if self.busy or self._exit:
            # Can happen if a drain from before a reconnect delivers late: give it back for another node
            self.release(event.delivery, delivered=False)
            return
        try:
            # Messages sent over STOMP arrive as binary, which proton hands over as bytes or memoryview
            body = event.message.body
            data = bytes(body).decode() if isinstance(body, (bytes, memoryview)) else str(body)
            # proton returns a new link object for each event, so match receivers by name
            queue = next(q for r, q in self.receivers if r.name == event.receiver.name)
        except Exception:
            # Counts as a failed delivery, so a message we can never read ends up on the dead letter queue
            logging.exception("Could not read a message, giving it back")
            self.release(event.delivery, delivered=True)
            self.pending = None
            self.next_queue()
            return
        logging.info("Received %s: %s", queue, data)

        # Accept before running the job, as the STOMP consumer acks before it
        self.accept(event.delivery)
        self.pending = None
        self.empty_in_a_row = 0
        self.busy = True
        threading.Thread(target=self._run_job, args=(self.input_queues[queue], data), daemon=True).start()

    def _run_job(self, input_queue, data):
        try:
            command_args = post_processing_command(self.config, input_queue, data)
            logging.warning("Command: %s", str(command_args))
            proc = subprocess.Popen(command_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for line in proc.stdout:
                logging.subprocess(line.decode().strip())
            proc.wait()
            logging.warning("end")
        except Exception:
            logging.exception("Error running post-processing for %s", input_queue)
        finally:
            self.injector.trigger(ApplicationEvent("job_done"))

    def on_job_done(self, event):
        self.busy = False
        if self._exit:
            self._stop()
        else:
            self.next_queue()

    def on_exit_request(self, event):
        if not self.busy:
            self._stop()

    def _stop(self):
        logging.info("Stopping the AMQP consumer")
        if self.connection is not None:
            self.connection.close()
        self.injector.close()
        self.container.stop()
