import json
import pytest

from stompest.config import StompConfig
from stompest.sync import Stomp
from stompest.error import StompConnectTimeout


def test_heartbeat():
    """While the queue processor is running, every 30 seconds it should send a message to /topic/SNS.COMMON.STATUS.AUTOREDUCE.0 with the hostname and pid"""

    client = Stomp(StompConfig("tcp://localhost:61613"))
    try:
        client.connect()
    except StompConnectTimeout:
        pytest.skip("Requires activemq running")

    client.subscribe("/topic/SNS.COMMON.STATUS.AUTOREDUCE.0")

    assert client.canRead(60)  # wait for heartbeat, should be one every 30 seconds
    frame = client.receiveFrame()

    client.disconnect()

    data = json.loads(frame.body)
    assert "src_name" in data
    assert data["role"] == "postprocessing"
    assert data["status"] == "0"
    assert data["pid"].isnumeric()


def test_heartbeat_ping():
    """When a message is received at /topic/SNS.COMMON.STATUS.PING this should respond with a heartbeat to reply_to"""

    client = Stomp(StompConfig("tcp://localhost:61613"))
    try:
        client.connect()
    except StompConnectTimeout:
        pytest.skip("Requires activemq running")

    # request a response on /queue/PING_TEST
    client.send(
        "/topic/SNS.COMMON.STATUS.PING",
        json.dumps({"reply_to": "/queue/PING_TEST"}).encode(),
    )

    client.subscribe("/queue/PING_TEST")

    assert client.canRead(5)
    frame = client.receiveFrame()

    client.disconnect()

    data = json.loads(frame.body)
    assert "src_name" in data
    assert data["role"] == "postprocessing"
    assert data["status"] == "0"
    assert data["pid"].isnumeric()
