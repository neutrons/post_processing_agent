"""
Per-instrument queues. Each test creates its queues after the agent has started, so they
have to be picked up by queue discovery.
"""

import json
import threading
import time
import uuid

import pytest
import stomp
from tests.conftest import docker_exec_and_cat

LOG_FILE = "/opt/postprocessing/log/postprocessing.log"

EQSANS_RUN = {
    "run_number": "30892",
    "instrument": "EQSANS",
    "ipts": "IPTS-10674",
    "facility": "SNS",
    "data_file": "/SNS/EQSANS/IPTS-10674/0/30892/NeXus/EQSANS_30892_event.nxs",
}


class Collector(stomp.ConnectionListener):
    """Like stomp's TestListener, but with a timeout"""

    def __init__(self):
        self.messages = []
        self._condition = threading.Condition()

    def on_message(self, frame):
        with self._condition:
            self.messages.append(json.loads(frame.body))
            self._condition.notify_all()

    def wait_for(self, predicate, timeout=60):
        with self._condition:
            if not self._condition.wait_for(lambda: predicate(self.messages), timeout=timeout):
                pytest.fail(f"Timed out after {timeout} s, received {self.messages}")


@pytest.fixture
def broker():
    conn = stomp.Connection(host_and_ports=[("localhost", 61613)])
    collector = Collector()
    conn.set_listener("", collector)
    try:
        conn.connect("icat", "icat", wait=True)
    except stomp.exception.ConnectFailedException:
        pytest.skip("Requires activemq running")
    yield conn, collector
    conn.disconnect()


def unique_instrument():
    return "TEST_" + uuid.uuid4().hex[:8].upper()


def send(conn, queue, message):
    conn.send(queue, json.dumps(message).encode())


def check_agent_log(queue, instrument, input_queue):
    """Check the agent subscribed to the queue and ran the job once, on the processor's input queue"""
    log = docker_exec_and_cat(LOG_FILE).splitlines()
    assert any("Subscribed to new per-instrument queues" in line and f"'{queue}'" in line for line in log)
    commands = [line for line in log if "Command:" in line and instrument in line]
    assert len(commands) == 1, commands
    assert f"'-q', '{input_queue}'" in commands[0]


def test_reduction(broker):
    conn, collector = broker
    instrument = unique_instrument()
    queue = f"/queue/REDUCTION.{instrument}.DATA_READY"
    conn.subscribe("/queue/REDUCTION.DISABLED", id="disabled", ack="auto")
    # there's no reduction script for this instrument, so it comes back as disabled
    send(conn, queue, dict(EQSANS_RUN, instrument=instrument))
    collector.wait_for(lambda msgs: any(m["instrument"] == instrument for m in msgs))
    check_agent_log(queue, instrument, "/queue/REDUCTION.DATA_READY")


def test_reduction_high_memory(broker):
    conn, collector = broker
    instrument = unique_instrument()
    queue = f"/queue/REDUCTION.HIMEM.{instrument}.DATA_READY"
    conn.subscribe("/queue/REDUCTION.DISABLED", id="disabled", ack="auto")
    send(conn, queue, dict(EQSANS_RUN, instrument=instrument))
    collector.wait_for(lambda msgs: any(m["instrument"] == instrument for m in msgs))
    check_agent_log(queue, instrument, "/queue/REDUCTION.HIMEM.DATA_READY")


def test_reduction_catalog(broker):
    conn, collector = broker
    message = {
        "run_number": "29666",
        "instrument": "CORELLI",
        "ipts": "IPTS-15526",
        "facility": "SNS",
        "data_file": "/SNS/CORELLI/IPTS-15526/nexus/CORELLI_29666.nxs.h5",
    }
    conn.subscribe("/queue/REDUCTION_CATALOG.COMPLETE", id="complete", ack="auto")
    send(conn, "/queue/REDUCTION_CATALOG.CORELLI.DATA_READY", message)
    collector.wait_for(lambda msgs: any(m["run_number"] == "29666" for m in msgs))

    time.sleep(1)  # give oncat_server time to write its log
    log = docker_exec_and_cat("/oncat_server.log", "oncat").splitlines()
    assert log[-1].endswith(
        "INFO Received reduction ingest request for /SNS/CORELLI/IPTS-15526/shared/autoreduce/CORELLI_29666.json"
    )


def test_flood_does_not_block_other_queues(broker):
    conn, collector = broker
    flood, victim = unique_instrument(), unique_instrument()
    flood_count = 16
    conn.subscribe("/queue/REDUCTION.DISABLED", id="disabled", ack="auto")
    for _ in range(flood_count):
        send(conn, f"/queue/REDUCTION.{flood}.DATA_READY", dict(EQSANS_RUN, instrument=flood))
    for _ in range(2):
        send(conn, f"/queue/REDUCTION.{victim}.DATA_READY", dict(EQSANS_RUN, instrument=victim))
    shared = unique_instrument()
    send(conn, "/queue/REDUCTION.DATA_READY", dict(EQSANS_RUN, instrument=shared))

    def order(msgs):
        return [m["instrument"] for m in msgs if m["instrument"] in (flood, victim, shared)]

    collector.wait_for(lambda msgs: len(order(msgs)) == flood_count + 3, timeout=180)
    received = order(collector.messages)
    # The victim and shared runs should finish within the first half of the flood. A few flood
    # runs can go first if the flood queue is discovered before the victim's.
    half_flood = [i for i, inst in enumerate(received) if inst == flood][flood_count // 2]
    last_victim = max(i for i, inst in enumerate(received) if inst == victim)
    assert last_victim < half_flood, received
    assert received.index(shared) < half_flood, received
