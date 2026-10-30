"""
ActiveMQ post-processing consumer over AMQP 1.0.

The agent holds no credit on its queues, so the broker never hands it a message it isn't ready
for. When it's free it asks the next queue in turn for one message (a drain of 1), accepts it
and runs the job in a worker thread. That keeps runs spread across the autoreducers instead of
piling up behind a busy one, which STOMP can't do because it always prefetches at least one
message per subscription.

Like the STOMP consumer, each agent runs one job at a time. Since the job runs in its own
thread, heartbeats and ping replies keep going while it runs.

@copyright: 2026 Oak Ridge National Laboratory
"""

import json
import logging
import os
import signal
import socket
import subprocess
import threading
import time

from proton import Message, symbol
from proton.handlers import MessagingHandler
from proton.reactor import ApplicationEvent, Container, EventInjector, ReceiverOption, SenderOption

from postprocessing.Consumer import HEARTBEAT_DELAY, heartbeat_message, post_processing_command
from postprocessing.queue_discovery import JolokiaQueueLister, find_per_instrument_queues

# How long to wait after finding every queue empty before asking them all again
IDLE_RETRY_SEC = 1.0
# Pings don't take the job slot, so their link keeps this much credit
PING_CREDIT = 10
# How long to wait before opening a link again after the broker closed it
RELINK_DELAY_SEC = 60.0


def amqp_address(destination):
    """
    Turn a STOMP destination like /queue/REDUCTION.DATA_READY into the AMQP address
    """
    return destination.split("/", 2)[-1] if destination.startswith("/") else destination


def capability(destination):
    """
    Artemis routing for a STOMP destination: topics are multicast, everything else anycast
    """
    return "topic" if destination.startswith("/topic/") else "queue"


class SourceCapability(ReceiverOption):
    """
    Tell Artemis whether we're reading from a queue or a topic
    """

    def __init__(self, destination):
        self.capability = capability(destination)

    def apply(self, receiver):
        receiver.source.capabilities.put_object(symbol(self.capability))


class TargetCapability(SenderOption):
    """
    Tell Artemis whether we're sending to a queue or a topic
    """

    def __init__(self, destination):
        self.capability = capability(destination)

    def apply(self, sender):
        sender.target.capabilities.put_object(symbol(self.capability))


class Timer:
    """
    Calls a function when a container timer goes off, so each timer can have its own handler
    """

    def __init__(self, callback):
        self.callback = callback

    def on_timer_task(self, event):
        self.callback()


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
        self.reconnecting = False

        self.ping_receiver = None
        # Address -> sender, and address -> latest message waiting for credit. Only the latest
        # is kept, so a long outage doesn't leave a pile of stale heartbeats to send.
        self.senders = {}
        self.outbox = {}

        for queue in config.queues:
            if queue != config.heartbeat_ping:
                self.input_queues[queue] = queue

        self._queue_lister = None
        if config.per_instrument_queues:
            self._queue_lister = JolokiaQueueLister(config.jolokia_urls, config.jolokia_user, config.jolokia_pwd)

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
        if queue in self.input_queues:
            return
        self.input_queues[queue] = input_queue or queue
        if self.connection is not None:
            self.receivers.append((self._create_receiver(queue), queue))

    def _link_name(self, kind, destination):
        # The link name shows up in the broker console, so make it say who we are
        return f"{socket.gethostname()}-{os.getpid()}-{kind}-{destination}"

    def _create_receiver(self, destination):
        return self.container.create_receiver(
            self.connection,
            amqp_address(destination),
            name=self._link_name("receive", destination),
            options=SourceCapability(destination),
        )

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
        for queue in self.input_queues:
            self.receivers.append((self._create_receiver(queue), queue))
        logging.info("Pulling from %s", sorted(self.input_queues))
        self._listen_for_pings()
        self.send_heartbeat()
        if self._queue_lister is not None:
            self.discover_queues()
        if self._exit:
            self._stop()

    def _listen_for_pings(self):
        if not self._exit:
            self.ping_receiver = self._create_receiver(self.config.heartbeat_ping)

    def is_ping(self, link):
        return link is not None and self.ping_receiver is not None and link.name == self.ping_receiver.name

    def on_link_opened(self, event):
        if event.receiver is None:
            return
        if self.is_ping(event.receiver):
            # Top up rather than add, since this runs again after every reconnect
            event.receiver.flow(max(0, PING_CREDIT - event.receiver.credit))
            return
        self.opened.add(event.receiver.name)
        self.next_queue()

    def on_link_error(self, event):
        # proton's default closes the whole connection, but one bad queue shouldn't stop the others.
        # proton closes the link next, and on_link_closed cleans up.
        link = event.link
        condition = link.remote_condition
        logging.error(
            "The broker closed the link for %s: %s",
            link_address(link),
            condition.description if condition else "no reason given",
        )

    def on_link_closed(self, event):
        link = event.link
        if self._exit or link is None:
            return
        if link.is_sender:
            # Made again on the next send
            address = link.target.address
            if address in self.senders and self.senders[address].name == link.name:
                del self.senders[address]
                self.outbox.pop(address, None)
            return
        if self.is_ping(link):
            logging.warning("Not listening for pings, trying again in %s s", RELINK_DELAY_SEC)
            self.container.schedule(RELINK_DELAY_SEC, Timer(self._listen_for_pings))
            return
        index = next((i for i, (r, _) in enumerate(self.receivers) if r.name == link.name), None)
        if index is None:
            return
        _receiver, queue = self.receivers.pop(index)
        # Keep the rotation on the queue that was next, instead of skipping it
        if index < self.next_index:
            self.next_index -= 1
        self.opened.discard(link.name)
        input_queue = self.input_queues.pop(queue)
        if queue in self.config.queues:
            logging.warning("Stopped pulling from %s, trying again in %s s", queue, RELINK_DELAY_SEC)
            self.container.schedule(RELINK_DELAY_SEC, Timer(lambda: self.add_queue(queue, input_queue)))
        else:
            # Discovery adds it back if it's still on the broker
            logging.warning("Stopped pulling from %s", queue)
        if self.pending is not None and self.pending.name == link.name:
            self.pending = None
            self.next_queue()

    def on_connection_opened(self, event):
        if self.reconnecting:
            logging.info("Reconnected over AMQP")
            self.reconnecting = False

    def on_disconnected(self, event):
        # proton reconnects and reopens the links by itself; start asking again once they're back.
        # This runs for every failed attempt too, so only say it once per outage.
        if not self.reconnecting:
            logging.warning("Lost the AMQP connection, reconnecting")
            self.reconnecting = True
        self.opened.clear()
        self.pending = None
        # This runs once the broker stops sending, but proton only reconnects after a write fails
        # too, which could be the next heartbeat. Close our side so it reconnects straight away.
        if event.transport is not None:
            event.transport.close_head()

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
            self.container.schedule(IDLE_RETRY_SEC, Timer(self.next_queue))
            return
        # Take the next queue in turn, skipping any whose link isn't open
        for _ in range(len(self.receivers)):
            receiver, _queue = self.receivers[self.next_index % len(self.receivers)]
            self.next_index = (self.next_index + 1) % len(self.receivers)
            if receiver.name in self.opened:
                self.pending = receiver
                receiver.drain(1)
                return

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
        if self.is_ping(event.receiver):
            self.accept(event.delivery)
            event.receiver.flow(1)
            self.answer_ping(event.message.body)
            return
        if self.busy or self._exit:
            # Can happen if a drain from before a reconnect delivers late: give it back for another node
            self.release(event.delivery, delivered=False)
            return
        try:
            data = message_text(event.message.body)
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

    # Heartbeats and pings

    def send(self, destination, body):
        """
        Send a message to a topic or queue, as soon as the broker gives us credit
        """
        address = amqp_address(destination)
        if address not in self.senders:
            self.senders[address] = self.container.create_sender(
                self.connection,
                address,
                name=self._link_name("send", destination),
                options=TargetCapability(destination),
            )
        self.outbox[address] = body
        self.flush()

    def flush(self):
        for address in list(self.outbox):
            sender = self.senders[address]
            if sender.credit:
                # STOMP listeners get the creation time as the timestamp header, as for STOMP-sent messages
                sender.send(Message(body=self.outbox.pop(address), creation_time=time.time()))

    def on_sendable(self, event):
        self.flush()

    def send_heartbeat(self):
        if self._exit:
            return
        self.send(self.config.heart_beat, heartbeat_message())
        self.container.schedule(HEARTBEAT_DELAY, Timer(self.send_heartbeat))

    def answer_ping(self, body):
        """
        Reply to a ping with a heartbeat, sent wherever the ping asks
        """
        try:
            data = json.loads(message_text(body))
        except Exception:
            logging.error("Could not read ping request %s", body)
            return
        if isinstance(data, dict) and "reply_to" in data:
            self.send(data["reply_to"], heartbeat_message(data))
        else:
            logging.error("Incomplete ping request %s", str(data))

    # Per-instrument queue discovery

    def discover_queues(self):
        """
        Ask the broker for its queues in another thread, since Jolokia can take a while to answer
        """
        threading.Thread(target=self._list_queues, daemon=True).start()

    def _list_queues(self):
        try:
            names, error = self._queue_lister.queue_names(), None
        except Exception as e:
            names, error = [], e
        if not self._exit:
            self.injector.trigger(ApplicationEvent("queues_listed", subject=(names, error)))

    def on_queues_listed(self, event):
        names, error = event.subject
        self.container.schedule(self.config.queue_discovery_interval_sec, Timer(self.discover_queues))
        if error is not None:
            logging.error("Per-instrument queue discovery failed, keeping %s queues: %s", len(self.input_queues), error)
            return
        found = find_per_instrument_queues(names, self.config.queues)
        new_queues = sorted(set(found) - set(self.input_queues))
        for queue in new_queues:
            self.add_queue(queue, found[queue])
        if new_queues:
            # Same wording as the STOMP consumer, so searching the logs works for both
            logging.info("Subscribed to new per-instrument queues: %s", new_queues)


def link_address(link):
    return link.target.address if link.is_sender else link.source.address


def message_text(body):
    """
    Messages sent over STOMP arrive as binary, which proton hands over as bytes or memoryview
    """
    return bytes(body).decode() if isinstance(body, (bytes, memoryview)) else str(body)
