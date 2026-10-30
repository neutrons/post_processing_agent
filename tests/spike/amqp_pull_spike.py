"""
Spike for EWM 18473: a pull-based AMQP consumer against Artemis.

Each consumer holds zero credit on every queue. When it's free it drains the next queue in
its rotation for one message, accepts it, and runs the job in a worker thread, so the
connection thread stays live for pings and heartbeats. Producers use STOMP, as the
workflow manager does.

Runs in an EL9 image with EPEL's python3-qpid-proton, against the integration broker:
    docker compose -f tests/integration/docker-compose.yml up -d activemq
    docker build -t amqp-spike tests/spike
    docker run --rm --network integration_default -v "$PWD/tests/spike:/spike" amqp-spike \\
        python3 amqp_pull_spike.py pull

  pull       one consumer, CG2 flood then EQSANS and a shared queue
  multi      3 consumers, 20 instrument queues, idle and busy-node cases
  interop    STOMP-sent messages, ping topic, reply and heartbeat to STOMP listeners
  longjob    90 s job (past the 60 s broker TTL) with a ping during it
"""

import base64
import json
import multiprocessing
import statistics
import sys
import threading
import time
import urllib.request

import stomp
from proton import Message, symbol
from proton.handlers import MessagingHandler
from proton.reactor import ApplicationEvent, Container, EventInjector, ReceiverOption, SenderOption

BROKER = "activemq"
AMQP_URL = f"amqp://{BROKER}:5672"
USER, PWD = "icat", "icat"
PING = "SNS.COMMON.STATUS.PING"


class SourceCapability(ReceiverOption):
    """Tell Artemis whether the source is a queue (anycast) or a topic (multicast)"""

    def __init__(self, cap):
        self.cap = cap

    def apply(self, receiver):
        receiver.source.capabilities.put_object(symbol(self.cap))


class TargetCapability(SenderOption):
    def __init__(self, cap):
        self.cap = cap

    def apply(self, sender):
        sender.target.capabilities.put_object(symbol(self.cap))


class PullConsumer(MessagingHandler):
    """Zero credit while busy; when free, drain the next queue for exactly one message"""

    def __init__(self, name, queues, report, idle_retry=0.25, listen_ping=False, stop_after=None):
        super().__init__(prefetch=0, auto_accept=False)
        self.name, self.queue_names, self.report = name, queues, report
        self.idle_retry, self.listen_ping, self.stop_after = idle_retry, listen_ping, stop_after
        self.busy, self.pending, self.got, self.idx, self.empty_streak = False, None, False, 0, 0
        self.senders, self.outbox, self.done_jobs, self.drains = {}, [], 0, 0

    # --- connection setup
    def on_start(self, event):
        self.container = event.container
        self.injector = EventInjector()
        self.container.selectable(self.injector)
        self.conn = self.container.connect(
            AMQP_URL, user=USER, password=PWD, allowed_mechs="PLAIN", allow_insecure_mechs=True
        )
        self.receivers = [
            self.container.create_receiver(self.conn, q, name=f"{self.name}-{q}", options=SourceCapability("queue"))
            for q in self.queue_names
        ]
        if self.listen_ping:
            # Pings don't use the job slot, so this link keeps a little standing credit
            self.ping_rx = self.container.create_receiver(
                self.conn, PING, name=f"{self.name}-ping", options=SourceCapability("topic")
            )
        else:
            self.ping_rx = None
        self.opened = 0

    def is_ping(self, link):
        # proton returns a new wrapper per event, so compare links by name, not identity
        return link is not None and self.ping_rx is not None and link.name == self.ping_rx.name

    def on_link_opened(self, event):
        if self.is_ping(event.receiver):
            self.ping_rx.flow(10)
        if event.receiver is not None and event.receiver.name in {r.name for r in self.receivers}:
            self.opened += 1
            if self.opened == len(self.receivers):
                self.report.put(("ready", self.name))
                self.next_queue()

    # --- pull loop, all on the container thread
    def next_queue(self, event=None):
        if self.busy or self.pending is not None:
            return
        if self.empty_streak >= len(self.receivers):
            # Every queue was empty in a full pass: wait a moment before the next pass
            self.empty_streak = 0
            self.container.schedule(self.idle_retry, self)
            return
        receiver = self.receivers[self.idx]
        self.idx = (self.idx + 1) % len(self.receivers)
        self.pending, self.got = receiver, False
        self.drains += 1
        receiver.drain(1)

    def on_timer_task(self, event):
        self.next_queue()

    def on_link_flow(self, event):
        r = event.receiver
        if (
            r is not None
            and self.pending is not None
            and r.name == self.pending.name
            and not self.got
            and r.credit == 0
            and not r.draining()
        ):
            # The drain came back with nothing: that queue is empty, try the next one
            self.pending = None
            self.empty_streak += 1
            self.next_queue()

    def on_message(self, event):
        body = event.message.body
        raw_type = type(body).__name__
        text = body.decode() if isinstance(body, (bytes, memoryview)) else body
        data = json.loads(text)
        if self.is_ping(event.receiver):
            self.accept(event.delivery)
            self.ping_rx.flow(1)
            self.send(
                data["reply_to"],
                {
                    "src_name": self.name,
                    "role": "postprocessing",
                    "status": "0",
                    "pid": "0",
                    "busy": self.busy,
                    "request_time": data.get("request_time"),
                },
            )
            self.report.put(("ping", self.name, time.time(), self.busy))
            return
        # Accept before the job, as Consumer.py acks today
        self.accept(event.delivery)
        self.got, self.pending, self.busy, self.empty_streak = True, None, True, 0
        start = time.time()
        source = event.receiver.source.address
        self.report.put(("start", self.name, source, data, start, raw_type, dict(event.message.properties or {})))
        threading.Thread(target=self.run_job, args=(data, source, start), daemon=True).start()

    def run_job(self, data, source, start):
        time.sleep(data.get("job_s", 0.1))  # stands in for the PostProcessAdmin subprocess
        self.injector.trigger(ApplicationEvent("job_done", subject=(data, source, start)))

    def on_job_done(self, event):
        data, source, start = event.subject
        self.report.put(("done", self.name, source, data, start, time.time()))
        self.busy = False
        self.done_jobs += 1
        if self.stop_after and self.done_jobs >= self.stop_after:
            self.report.put(("drains", self.name, self.drains))
            self.conn.close()
            self.injector.close()
            return
        self.next_queue()

    def on_shutdown_request(self, event):
        self.report.put(("drains", self.name, self.drains))
        self.conn.close()
        self.injector.close()

    # --- sending (heartbeats, ping replies) from the container thread
    def send(self, destination, payload):
        cap = "topic" if destination.startswith("/topic/") else "queue"
        address = destination.split("/", 2)[-1] if destination.startswith("/") else destination
        if address not in self.senders:
            self.senders[address] = self.container.create_sender(self.conn, address, options=TargetCapability(cap))
        self.outbox.append((address, json.dumps(payload)))
        self.flush()

    def flush(self):
        for item in list(self.outbox):
            sender = self.senders[item[0]]
            if sender.credit:
                sender.send(Message(body=item[1]))
                self.outbox.remove(item)

    def on_sendable(self, event):
        self.flush()

    def on_disconnected(self, event):
        self.report.put(("disconnected", self.name, time.time()))

    def on_heartbeat(self, event):
        self.send("/topic/SNS.COMMON.STATUS.AUTOREDUCE.0", {"src_name": self.name, "role": "postprocessing"})


def run_consumer(name, queues, report, ctrl, listen_ping=False, stop_after=None):
    handler = PullConsumer(name, queues, report, listen_ping=listen_ping, stop_after=stop_after)
    container = Container(handler)

    def watch():
        ctrl.wait()  # shut down when the driver says so
        handler.injector.trigger(ApplicationEvent("shutdown_request"))

    threading.Thread(target=watch, daemon=True).start()
    if listen_ping:

        def beat():
            while not hasattr(handler, "injector"):  # created in on_start
                time.sleep(0.1)
            while not ctrl.is_set():
                handler.injector.trigger(ApplicationEvent("heartbeat"))
                ctrl.wait(5)

        threading.Thread(target=beat, daemon=True).start()
    container.run()


# --- broker helpers
def stomp_conn(listener=None, **kw):
    conn = stomp.Connection([(BROKER, 61613)], **kw)
    if listener:
        conn.set_listener("", listener)
    conn.connect(USER, PWD, wait=True)
    return conn


def jolokia_delivering(queues):
    """Sum of DeliveringCount: messages the broker has handed to consumers but not yet settled"""
    total = 0
    auth = base64.b64encode(f"{USER}:{PWD}".encode()).decode()
    for q in queues:
        mbean = (
            f'org.apache.activemq.artemis:broker="Artemis-Broker",component=addresses,address="{q}",'
            f'subcomponent=queues,routing-type="anycast",queue="{q}"'
        )
        body = json.dumps({"type": "read", "mbean": mbean, "attribute": "DeliveringCount"}).encode()
        req = urllib.request.Request(
            f"http://{BROKER}:8161/console/jolokia",
            body,
            {"Content-Type": "application/json", "Origin": "http://localhost", "Authorization": "Basic " + auth},
        )
        reply = json.load(urllib.request.urlopen(req, timeout=5))
        # Jolokia reports errors in the body with HTTP 200, and a failed read shouldn't count as 0 held
        if reply.get("status") != 200:
            raise RuntimeError(f"Jolokia read of {q} failed: {reply.get('error')}")
        total += reply["value"]
    return total


def start_consumers(n, queues, **kw):
    report, ctrl = multiprocessing.Queue(), multiprocessing.Event()
    procs = [
        multiprocessing.Process(target=run_consumer, args=(f"node{i}", queues(i), report, ctrl), kwargs=kw)
        for i in range(n)
    ]
    for p in procs:
        p.start()
    ready = 0
    while ready < n:
        if report.get(timeout=30)[0] == "ready":
            ready += 1
    return report, ctrl, procs


def collect(report, until, timeout=300, watch_queues=None):
    events, peak, deadline, next_sample = [], 0, time.time() + timeout, 0
    while not until(events) and time.time() < deadline:
        if watch_queues and time.time() > next_sample:
            peak, next_sample = max(peak, jolokia_delivering(watch_queues)), time.time() + 0.5
        try:
            events.append(report.get(timeout=0.2))
        except Exception:
            pass
    return events, peak


def stop(ctrl, procs, report):
    ctrl.set()
    drains = {}
    for p in procs:
        p.join(10)
    while not report.empty():
        e = report.get()
        if e[0] == "drains":
            drains[e[1]] = e[2]
    return drains


# --- scenarios
def pull():
    queues = ["SPIKE.CG2.DATA_READY", "SPIKE.EQSANS.DATA_READY", "SPIKE.SHARED.DATA_READY"]
    report, ctrl, procs = start_consumers(1, lambda i: queues)
    prod = stomp_conn()
    for q, label, n in ((queues[0], "cg2", 100), (queues[1], "eqsans", 10), (queues[2], "shared", 5)):
        for seq in range(n):
            prod.send(f"/queue/{q}", json.dumps({"label": label, "seq": seq, "sent": time.time(), "job_s": 0.1}))
    prod.disconnect()
    events, peak = collect(report, lambda ev: sum(e[0] == "done" for e in ev) >= 115, watch_queues=queues)
    drains = stop(ctrl, procs, report)
    order = [e[3]["label"] for e in events if e[0] == "start"]
    print("First 30 deliveries:", " ".join(order[:30]))
    for victim in ("eqsans", "shared"):
        last = len(order) - order[::-1].index(victim)
        print(f"  {victim}: first at {order.index(victim) + 1}, CG2 before its last = {order[:last].count('cg2')}")
    print(
        f"  received {len(order)} of 115, duplicates {len(order) - len({(e[3]['label'], e[3]['seq']) for e in events if e[0] == 'start'})}"
    )
    print(f"  peak messages held by the broker for the consumer (DeliveringCount): {peak}")
    print(f"  drain requests: {drains}")


def multi():
    insts = [f"SPIKE.I{i:02d}.DATA_READY" for i in range(20)]
    busy_q = "SPIKE.BUSY.DATA_READY"
    for scenario in ("idle-spread", "busy-node"):
        qs = (lambda i: insts + [busy_q] if i == 0 else insts) if scenario == "busy-node" else (lambda i: insts)
        report, ctrl, procs = start_consumers(3, qs)
        prod = stomp_conn()
        expected = 20
        if scenario == "busy-node":
            prod.send(f"/queue/{busy_q}", json.dumps({"label": "busy", "seq": 0, "sent": time.time(), "job_s": 30}))
            while True:
                e = report.get(timeout=30)
                if e[0] == "start" and e[3]["label"] == "busy":
                    busy_start = time.time()
                    break
        for i, q in enumerate(insts):
            prod.send(f"/queue/{q}", json.dumps({"label": f"I{i:02d}", "seq": i, "sent": time.time(), "job_s": 1.0}))
        prod.disconnect()
        events, peak = collect(
            report,
            lambda ev: sum(e[0] == "done" and e[3]["label"] != "busy" for e in ev) >= expected,
            watch_queues=insts,
        )
        drains = stop(ctrl, procs, report)
        starts = [e for e in events if e[0] == "start" and e[3]["label"] != "busy"]
        per_node = {n: sum(e[1] == n for e in starts) for n in ("node0", "node1", "node2")}
        waits = [e[4] - e[3]["sent"] for e in starts]
        print(
            f"=== {scenario}: runs per node {per_node}, wait mean {statistics.mean(waits):.1f} s, "
            f"max {max(waits):.1f} s, peak held {peak}"
        )
        if scenario == "busy-node":
            pinned = [e for e in starts if e[1] == "node0" and e[4] - busy_start < 29]
            print(f"  runs taken by the busy node while its 30 s job ran: {len(pinned)}")
        print(f"  drain requests per node: {drains}")


def interop():
    q = "SPIKE.INTEROP.DATA_READY"
    got = []

    class Catch(stomp.ConnectionListener):
        def on_message(self, frame):
            got.append((frame.headers["destination"], json.loads(frame.body)))

    watcher = stomp_conn(Catch())
    watcher.subscribe("/topic/SNS.COMMON.STATUS.ACK", id="ack", ack="auto")
    watcher.subscribe("/topic/SNS.COMMON.STATUS.AUTOREDUCE.0", id="hb", ack="auto")
    report, ctrl, procs = start_consumers(1, lambda i: [q], listen_ping=True)
    prod = stomp_conn()
    msg = {"instrument": "EQSANS", "run_number": "1", "data_file": "/SNS/x.nxs.h5", "job_s": 0.1}
    prod.send(f"/queue/{q}", json.dumps(msg), headers={"custom-header": "abc"})  # stomp.py adds content-length
    text_prod = stomp_conn(auto_content_length=False)  # no content-length, so Artemis stores a text message
    text_prod.send(f"/queue/{q}", json.dumps(msg), headers={"custom-header": "abc"})
    text_prod.disconnect()
    prod.send(
        "/topic/SNS.COMMON.STATUS.PING",
        json.dumps({"reply_to": "/topic/SNS.COMMON.STATUS.ACK", "request_time": time.time()}),
    )
    prod.disconnect()
    events, _ = collect(
        report, lambda ev: sum(e[0] == "done" for e in ev) >= 2 and any(e[0] == "ping" for e in ev), timeout=30
    )
    time.sleep(6)  # let a heartbeat go out
    stop(ctrl, procs, report)
    watcher.disconnect()
    for e in events:
        if e[0] == "start":
            print(
                f"  queue message: AMQP body type {e[5]}, source {e[2]}, decoded ok {e[3]['run_number'] == '1'}, "
                f"properties {e[6]}"
            )
    print(f"  ping received over AMQP: {any(e[0] == 'ping' for e in events)}")
    print(f"  STOMP listener got ping reply on STATUS.ACK: {any('ACK' in d for d, _ in got)}")
    print(f"  STOMP listener got heartbeat on STATUS.AUTOREDUCE.0: {any('AUTOREDUCE' in d for d, _ in got)}")


def longjob():
    q = "SPIKE.LONG.DATA_READY"
    report, ctrl, procs = start_consumers(1, lambda i: [q], listen_ping=True)
    prod = stomp_conn()
    prod.send(f"/queue/{q}", json.dumps({"label": "long", "seq": 0, "sent": time.time(), "job_s": 90}))
    time.sleep(45)
    ping_sent = time.time()
    prod.send(
        "/topic/SNS.COMMON.STATUS.PING",
        json.dumps({"reply_to": "/topic/SNS.COMMON.STATUS.ACK", "request_time": ping_sent}),
    )
    prod.disconnect()
    events, _ = collect(report, lambda ev: any(e[0] == "done" for e in ev), timeout=150)
    stop(ctrl, procs, report)
    pings = [e for e in events if e[0] == "ping"]
    print(f"  90 s job finished: {any(e[0] == 'done' for e in events)}")
    print(f"  disconnects during the job: {sum(e[0] == 'disconnected' for e in events)}")
    if pings:
        print(f"  ping answered while busy={pings[0][3]}, {pings[0][2] - ping_sent:.2f} s after it was sent")


if __name__ == "__main__":
    {"pull": pull, "multi": multi, "interop": interop, "longjob": longjob}[sys.argv[1]]()
