import json
import pytest
import stomp


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
