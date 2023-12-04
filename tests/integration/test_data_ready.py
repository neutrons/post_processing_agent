import json
import pytest

from stompest.config import StompConfig
from stompest.sync import Stomp
from stompest.error import StompConnectTimeout
from tests.conftest import docker_exec_and_cat


def test_missing_data():
    message = {
        "run_number": "30892",
        "instrument": "EQSANS",
        "ipts": "IPTS-10674",
        "facility": "SNS",
        "data_file": "/SNS/DOES_NOT_EXIST.nxs",
    }

    client = Stomp(StompConfig("tcp://localhost:61613"))
    try:
        client.connect()
    except StompConnectTimeout:
        pytest.skip("Requires activemq running")

    # send data ready
    client.send("/queue/REDUCTION.DATA_READY", json.dumps(message).encode())

    # expect a error for missing file
    client.subscribe("/queue/POSTPROCESS.ERROR")

    assert client.canRead(5)
    frame = client.receiveFrame()

    client.disconnect()

    msg = json.loads(frame.body)
    assert (
        msg["error"]
        == "Data file does not exist or is not readable: /SNS/DOES_NOT_EXIST.nxs"
    )


def test_disabled_reduction():
    message = {
        "run_number": "30892",
        "instrument": "INSTRUMENT",
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
    client.send("/queue/REDUCTION.DATA_READY", json.dumps(message).encode())

    # expect a reduction disabled
    client.subscribe("/queue/REDUCTION.DISABLED")

    assert client.canRead(5)
    frame = client.receiveFrame()

    client.disconnect()

    msg = json.loads(frame.body)
    assert msg["run_number"] == message["run_number"]
    assert msg["instrument"] == message["instrument"]
    assert msg["ipts"] == message["ipts"]
    assert msg["facility"] == message["facility"]
    assert msg["data_file"] == message["data_file"]


def test_reduction():
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
    client.send("/queue/REDUCTION.DATA_READY", json.dumps(message).encode())

    # expect a reduction complete
    client.subscribe("/queue/REDUCTION.COMPLETE")

    assert client.canRead(5)
    frame = client.receiveFrame()

    client.disconnect()

    msg = json.loads(frame.body)
    assert msg["run_number"] == message["run_number"]
    assert msg["instrument"] == message["instrument"]
    assert msg["ipts"] == message["ipts"]
    assert msg["facility"] == message["facility"]
    assert msg["data_file"] == message["data_file"]

    # we can also check that the reduction did run by checking the reduction_log
    reduction_log = docker_exec_and_cat(
        "/SNS/EQSANS/IPTS-10674/shared/autoreduce/reduction_log/EQSANS_30892_event.nxs.log"
    )

    assert (
        reduction_log
        == "['/SNS/EQSANS/IPTS-10674/0/30892/NeXus/EQSANS_30892_event.nxs', '/SNS/EQSANS/IPTS-10674/shared/autoreduce/']\n"
    )


def test_reduction_error():
    message = {
        "run_number": "29666",
        "instrument": "CORELLI",
        "ipts": "IPTS-15526",
        "facility": "SNS",
        "data_file": "/SNS/CORELLI/IPTS-15526/nexus/CORELLI_29666.nxs.h5",
    }

    client = Stomp(StompConfig("tcp://localhost:61613"))
    try:
        client.connect()
    except StompConnectTimeout:
        pytest.skip("Requires activemq running")

    # send data ready
    client.send("/queue/REDUCTION.DATA_READY", json.dumps(message).encode())

    # expect a reduction error
    client.subscribe("/queue/REDUCTION.ERROR")

    assert client.canRead(5)
    frame = client.receiveFrame()

    client.disconnect()

    msg = json.loads(frame.body)
    assert msg["run_number"] == message["run_number"]
    assert msg["instrument"] == message["instrument"]
    assert msg["ipts"] == message["ipts"]
    assert msg["facility"] == message["facility"]
    assert msg["data_file"] == message["data_file"]
    assert msg["error"] == "REDUCTION: This is an ERROR!"
