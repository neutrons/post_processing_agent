import json
import pytest

from stompest.config import StompConfig
from stompest.sync import Stomp
from stompest.error import StompConnectTimeout


def test_oncat_catalog():
    """This should run ONCatProcessor"""
    message = {
        "run_number": "30892",
        "instrument": "EQSANS",
        "ipts": "IPTS-10674",
        "facility": "SNS",
        "data_file": "/SNS/EQSANS/IPTS-10674/0/30892/NeXus/EQSANS_30892_event.nxs",
    }

    client = Stomp(StompConfig("tcp://localhost:61613"))
    try:
        client.connect()
    except StompConnectTimeout:
        pytest.skip("Requires activemq running")

    # send data ready
    client.send("/queue/CATALOG.ONCAT.DATA_READY", json.dumps(message).encode())

    # expect a message on CATALOG.ONCAT.COMPLETE
    client.subscribe("/queue/CATALOG.ONCAT.COMPLETE")

    assert client.canRead(5)
    frame = client.receiveFrame()

    client.disconnect()

    msg = json.loads(frame.body)
    assert msg["run_number"] == message["run_number"]
    assert msg["instrument"] == message["instrument"]
    assert msg["ipts"] == message["ipts"]
    assert msg["facility"] == message["facility"]
    assert msg["data_file"] == message["data_file"]


def test_oncat_reduction_catalog():
    """This should run reduction ONCatProcessor"""
    message = {
        "run_number": "30892",
        "instrument": "EQSANS",
        "ipts": "IPTS-10674",
        "facility": "SNS",
        "data_file": "/SNS/EQSANS/IPTS-10674/0/30892/NeXus/EQSANS_30892_event.nxs",
    }

    client = Stomp(StompConfig("tcp://localhost:61613"))
    try:
        client.connect()
    except StompConnectTimeout:
        pytest.skip("Requires activemq running")

    # send data ready
    client.send("/queue/REDUCTION_CATALOG.DATA_READY", json.dumps(message).encode())

    # expect a message on REDUCTION_CATALOG.COMPLETE
    client.subscribe("/queue/REDUCTION_CATALOG.COMPLETE")

    assert client.canRead(5)
    frame = client.receiveFrame()

    client.disconnect()

    msg = json.loads(frame.body)
    assert msg["run_number"] == message["run_number"]
    assert msg["instrument"] == message["instrument"]
    assert msg["ipts"] == message["ipts"]
    assert msg["facility"] == message["facility"]
    assert msg["data_file"] == message["data_file"]


def test_calvera():
    """Test calvera, expect an error as we don't have a real endpoint"""
    message = {
        "run_number": "30892",
        "instrument": "EQSANS",
        "ipts": "IPTS-10674",
        "facility": "SNS",
        "data_file": "/SNS/EQSANS/IPTS-10674/0/30892/NeXus/EQSANS_30892_event.nxs",
    }

    client = Stomp(StompConfig("tcp://localhost:61613"))
    try:
        client.connect()
    except StompConnectTimeout:
        pytest.skip("Requires activemq running")

    # send data ready
    client.send("/queue/CALVERA.RAW.DATA_READY", json.dumps(message).encode())

    # expect an error
    client.subscribe("/queue/CALVERA.RAW.ERROR")

    assert client.canRead(5)
    frame = client.receiveFrame()

    client.disconnect()

    msg = json.loads(frame.body)
    assert msg["run_number"] == message["run_number"]
    assert msg["instrument"] == message["instrument"]
    assert msg["ipts"] == message["ipts"]
    assert msg["facility"] == message["facility"]
    assert msg["data_file"] == message["data_file"]

    assert msg["error"].startswith(
        "SENDING TO Calvera: HTTPConnectionPool(host='not-valid.localhost', port=12345)"
    )
    assert "Failed to establish a new connect" in msg["error"]


def test_calvera_reduced():
    """Test calvera for reduced data, expect error because there is no reduced data"""
    message = {
        "run_number": "30892",
        "instrument": "EQSANS",
        "ipts": "IPTS-10674",
        "facility": "SNS",
        "data_file": "/SNS/EQSANS/IPTS-10674/0/30892/NeXus/EQSANS_30892_event.nxs",
    }

    client = Stomp(StompConfig("tcp://localhost:61613"))
    try:
        client.connect()
    except StompConnectTimeout:
        pytest.skip("Requires activemq running")

    # send data ready
    client.send("/queue/CALVERA.REDUCED.DATA_READY", json.dumps(message).encode())

    # expect an error
    client.subscribe("/queue/CALVERA.REDUCED.ERROR")

    assert client.canRead(5)
    frame = client.receiveFrame()

    client.disconnect()

    msg = json.loads(frame.body)
    assert msg["run_number"] == message["run_number"]
    assert msg["instrument"] == message["instrument"]
    assert msg["ipts"] == message["ipts"]
    assert msg["facility"] == message["facility"]
    assert msg["data_file"] == message["data_file"]

    assert msg["error"] == "SENDING TO Calvera: Cannot read reduced data info"
