import json
import pytest
import stomp


def test_oncat_catalog():
    """This should run ONCatProcessor"""
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

    # expect a message on CATALOG.ONCAT.COMPLETE
    conn.subscribe("/queue/CATALOG.ONCAT.COMPLETE", id="123", ack="auto")

    # send data ready
    conn.send("/queue/CATALOG.ONCAT.DATA_READY", json.dumps(message).encode())

    listener.wait_for_message()

    conn.disconnect()

    header, body = listener.get_latest_message()

    msg = json.loads(body)
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

    conn = stomp.Connection(host_and_ports=[("localhost", 61613)])

    listener = stomp.listener.TestListener(print_to_log=False)
    conn.set_listener("", listener)

    try:
        conn.connect()
    except stomp.exception.ConnectFailedException:
        pytest.skip("Requires activemq running")

    # expect a message on REDUCTION_CATALOG.COMPLETE
    conn.subscribe("/queue/REDUCTION_CATALOG.COMPLETE", id="123", ack="auto")

    # send data ready
    conn.send("/queue/REDUCTION_CATALOG.DATA_READY", json.dumps(message).encode())

    listener.wait_for_message()

    conn.disconnect()

    header, body = listener.get_latest_message()

    msg = json.loads(body)
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

    conn = stomp.Connection(host_and_ports=[("localhost", 61613)])

    listener = stomp.listener.TestListener(print_to_log=False)
    conn.set_listener("", listener)

    try:
        conn.connect()
    except stomp.exception.ConnectFailedException:
        pytest.skip("Requires activemq running")

    # expect an error
    conn.subscribe("/queue/CALVERA.RAW.ERROR", id="123", ack="auto")

    # send data ready
    conn.send("/queue/CALVERA.RAW.DATA_READY", json.dumps(message).encode())

    listener.wait_for_message()

    conn.disconnect()

    header, body = listener.get_latest_message()

    msg = json.loads(body)
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

    conn = stomp.Connection(host_and_ports=[("localhost", 61613)])

    listener = stomp.listener.TestListener(print_to_log=False)
    conn.set_listener("", listener)

    try:
        conn.connect()
    except stomp.exception.ConnectFailedException:
        pytest.skip("Requires activemq running")

    # expect an error
    conn.subscribe("/queue/CALVERA.REDUCED.ERROR", id="123", ack="auto")

    # send data ready
    conn.send("/queue/CALVERA.REDUCED.DATA_READY", json.dumps(message).encode())

    listener.wait_for_message()

    conn.disconnect()

    header, body = listener.get_latest_message()

    msg = json.loads(body)
    assert msg["run_number"] == message["run_number"]
    assert msg["instrument"] == message["instrument"]
    assert msg["ipts"] == message["ipts"]
    assert msg["facility"] == message["facility"]
    assert msg["data_file"] == message["data_file"]

    assert msg["error"] == "SENDING TO Calvera: Cannot read reduced data info"
