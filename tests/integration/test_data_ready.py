import json
import pytest

import stomp
from tests.conftest import docker_exec_and_cat


def test_missing_data():
    message = {
        "run_number": "30892",
        "instrument": "EQSANS",
        "ipts": "IPTS-10674",
        "facility": "SNS",
        "data_file": "/SNS/DOES_NOT_EXIST.nxs",
    }

    conn = stomp.Connection(host_and_ports=[("localhost", 61613)])

    listener = stomp.listener.TestListener(print_to_log=False)
    conn.set_listener("", listener)

    try:
        conn.connect()
    except stomp.exception.ConnectFailedException:
        pytest.skip("Requires activemq running")

    # expect a reduction disabled
    conn.subscribe(destination="/queue/POSTPROCESS.ERROR", id="123", ack="auto")

    # send data ready
    conn.send("/queue/REDUCTION.DATA_READY", json.dumps(message).encode())

    listener.wait_for_message()

    conn.disconnect()

    header, body = listener.get_latest_message()

    msg = json.loads(body)
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

    conn = stomp.Connection(host_and_ports=[("localhost", 61613)])

    listener = stomp.listener.TestListener(print_to_log=False)
    conn.set_listener("", listener)

    try:
        conn.connect()
    except stomp.exception.ConnectFailedException:
        pytest.skip("Requires activemq running")

    # expect a reduction disabled
    conn.subscribe("/queue/REDUCTION.DISABLED", id="123", ack="auto")

    # send data ready
    conn.send("/queue/REDUCTION.DATA_READY", json.dumps(message).encode())

    listener.wait_for_message()

    conn.disconnect()

    header, body = listener.get_latest_message()

    msg = json.loads(body)
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

    conn = stomp.Connection(host_and_ports=[("localhost", 61613)])

    listener = stomp.listener.TestListener(print_to_log=False)
    conn.set_listener("", listener)

    try:
        conn.connect()
    except stomp.exception.ConnectFailedException:
        pytest.skip("Requires activemq running")

    # expect a reduction complete
    conn.subscribe("/queue/REDUCTION.COMPLETE", id="123", ack="auto")

    # send data ready
    conn.send("/queue/REDUCTION.DATA_READY", json.dumps(message).encode())

    listener.wait_for_message()

    conn.disconnect()

    header, body = listener.get_latest_message()

    msg = json.loads(body)
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

    conn = stomp.Connection(host_and_ports=[("localhost", 61613)])

    listener = stomp.listener.TestListener(print_to_log=False)
    conn.set_listener("", listener)

    try:
        conn.connect()
    except stomp.exception.ConnectFailedException:
        pytest.skip("Requires activemq running")

    # expect a reduction error
    conn.subscribe("/queue/REDUCTION.ERROR", id="123", ack="auto")

    # send data ready
    conn.send("/queue/REDUCTION.DATA_READY", json.dumps(message).encode())

    listener.wait_for_message()

    conn.disconnect()

    header, body = listener.get_latest_message()

    msg = json.loads(body)
    assert msg["run_number"] == message["run_number"]
    assert msg["instrument"] == message["instrument"]
    assert msg["ipts"] == message["ipts"]
    assert msg["facility"] == message["facility"]
    assert msg["data_file"] == message["data_file"]
    assert msg["error"] == "REDUCTION: This is an ERROR!"
