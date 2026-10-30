import json
import os
import threading
import time

import pytest
import stomp


class Collector(stomp.ConnectionListener):
    """Keeps every message with its subscription and arrival time"""

    def __init__(self):
        self.messages = []
        self._condition = threading.Condition()

    def on_message(self, frame):
        with self._condition:
            self.messages.append((frame.headers["subscription"], json.loads(frame.body), time.time()))
            self._condition.notify_all()

    def wait_for(self, subscription, predicate, timeout=60):
        def find():
            return next((m for m in self.messages if m[0] == subscription and predicate(m[1])), None)

        with self._condition:
            if not self._condition.wait_for(find, timeout=timeout):
                pytest.fail(f"Timed out after {timeout} s waiting on {subscription}, received {self.messages}")
            return find()


def test_heartbeat():
    """While the queue processor is running, every 30 seconds it should send a message to /topic/SNS.COMMON.STATUS.AUTOREDUCE.0 with the hostname and pid"""

    conn = stomp.Connection(host_and_ports=[("localhost", 61613)])

    listener = stomp.listener.TestListener()
    conn.set_listener("", listener)

    try:
        conn.connect("icat", "icat")
    except stomp.exception.ConnectFailedException:
        pytest.skip("Requires activemq running")

    conn.subscribe("/topic/SNS.COMMON.STATUS.AUTOREDUCE.0", id="123", ack="auto")

    listener.wait_for_message()

    conn.disconnect()

    header, body = listener.get_latest_message()

    data = json.loads(body)
    assert "src_name" in data
    assert data["role"] == "postprocessing"
    assert data["status"] == "0"
    assert data["pid"].isnumeric()


def test_heartbeat_ping():
    """When a message is received at /topic/SNS.COMMON.STATUS.PING this should respond with a heartbeat to reply_to"""

    conn = stomp.Connection(host_and_ports=[("localhost", 61613)])

    listener = stomp.listener.TestListener()
    conn.set_listener("", listener)

    try:
        conn.connect("icat", "icat")
    except stomp.exception.ConnectFailedException:
        pytest.skip("Requires activemq running")

    conn.subscribe("/queue/PING_TEST", id="123", ack="auto")

    conn.send(
        "/topic/SNS.COMMON.STATUS.PING",
        json.dumps({"reply_to": "/queue/PING_TEST"}).encode(),
    )

    listener.wait_for_message()

    conn.disconnect()

    header, body = listener.get_latest_message()

    data = json.loads(body)
    assert "src_name" in data
    assert data["role"] == "postprocessing"
    assert data["status"] == "0"
    assert data["pid"].isnumeric()


@pytest.mark.skipif(
    os.environ.get("CONSUMER_PROTOCOL", "stomp") != "amqp",
    reason="the STOMP agent only reads its next message after the job is done",
)
def test_ping_answered_during_a_job():
    """The AMQP agent runs jobs in their own thread, so it answers pings while it reduces"""

    conn = stomp.Connection(host_and_ports=[("localhost", 61613)])
    collector = Collector()
    conn.set_listener("", collector)

    try:
        conn.connect("icat", "icat", wait=True)
    except stomp.exception.ConnectFailedException:
        pytest.skip("Requires activemq running")

    for queue in ("/queue/REDUCTION.STARTED", "/queue/REDUCTION.COMPLETE", "/queue/PING_DURING_JOB"):
        conn.subscribe(queue, id=queue, ack="auto")

    # reduce_SLOW.py takes 5 s
    run = {
        "run_number": "1",
        "instrument": "SLOW",
        "ipts": "IPTS-1",
        "facility": "SNS",
        "data_file": "/SNS/SLOW/IPTS-1/nexus/SLOW_1.nxs.h5",
    }
    conn.send("/queue/REDUCTION.DATA_READY", json.dumps(run).encode())
    collector.wait_for("/queue/REDUCTION.STARTED", lambda m: m.get("instrument") == "SLOW")

    request_time = time.time()
    conn.send(
        "/topic/SNS.COMMON.STATUS.PING",
        json.dumps({"reply_to": "/queue/PING_DURING_JOB", "request_time": request_time}).encode(),
    )
    reply = collector.wait_for("/queue/PING_DURING_JOB", lambda m: m.get("request_time") == request_time)
    complete = collector.wait_for("/queue/REDUCTION.COMPLETE", lambda m: m.get("instrument") == "SLOW")
    conn.disconnect()

    assert reply[1]["role"] == "postprocessing"
    assert reply[2] < complete[2], "the ping was only answered after the job"
