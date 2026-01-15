import time
import json
import pytest
import stomp
from tests.conftest import docker_exec_and_cat


def test_oncat_catalog():
    """This should run ONCatProcessor"""
    message = {
        "run_number": "29666",
        "instrument": "CORELLI",
        "ipts": "IPTS-15526",
        "facility": "SNS",
        "data_file": "/SNS/CORELLI/IPTS-15526/nexus/CORELLI_29666.nxs.h5",
    }

    conn = stomp.Connection(host_and_ports=[("localhost", 61613)])

    listener = stomp.listener.TestListener()
    conn.set_listener("", listener)

    try:
        conn.connect("icat", "icat")
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

    time.sleep(1)  # give oncat_server time to write its log
    log = docker_exec_and_cat("/oncat_server.log", "oncat").splitlines()
    # last two lines should be the requested file then the 'related' file
    assert log[-2].endswith(
        "INFO Received datafile ingest request for /SNS/CORELLI/IPTS-15526/nexus/CORELLI_29666.nxs.h5"
    )
    assert log[-1].endswith(
        "INFO Received datafile ingest request for /SNS/CORELLI/IPTS-15526/images/det_main/CORELLI_29666_det_main_000001.tiff"
    )


def test_oncat_catalog_error():
    """This should run ONCatProcessor but get an error"""
    message = {
        "run_number": "99999999",
        "instrument": "CORELLI",
        "ipts": "IPTS-15526",
        "facility": "SNS",
        "data_file": "/bin/true",
    }

    conn = stomp.Connection(host_and_ports=[("localhost", 61613)])

    listener = stomp.listener.TestListener()
    conn.set_listener("", listener)

    try:
        conn.connect("icat", "icat")
    except stomp.exception.ConnectFailedException:
        pytest.skip("Requires activemq running")

    # expect a message on CATALOG.ONCAT.ERROR
    conn.subscribe("/queue/CATALOG.ONCAT.ERROR", id="123", ack="auto")

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
    assert msg["error"] == "ONCAT: Bad request"

    time.sleep(1)  # give oncat_server time to write its log
    log = docker_exec_and_cat("/oncat_server.log", "oncat").splitlines()
    # last line should indicate the file was ingested
    assert log[-1].endswith("ERROR Invalid path format: /bin/true")


def test_oncat_catalog_venus_images():
    """This should run ONCatProcessor and catalog VENUS image files using batch API"""
    message = {
        "run_number": "12345",
        "instrument": "VENUS",
        "ipts": "IPTS-99999",
        "facility": "SNS",
        "data_file": "/SNS/VENUS/IPTS-99999/nexus/VENUS_12345.nxs.h5",
    }

    conn = stomp.Connection(host_and_ports=[("localhost", 61613)])

    listener = stomp.listener.TestListener()
    conn.set_listener("", listener)

    try:
        conn.connect("icat", "icat")
    except stomp.exception.ConnectFailedException:
        pytest.skip("Requires activemq running")

    # expect a message on CATALOG.ONCAT.COMPLETE
    conn.subscribe("/queue/CATALOG.ONCAT.COMPLETE", id="123", ack="auto")

    # send data ready
    conn.send("/queue/CATALOG.ONCAT.DATA_READY", json.dumps(message).encode())

    # Wait for the correct message, skipping any stale messages from previous tests
    max_attempts = 10
    for attempt in range(max_attempts):
        listener.wait_for_message(timeout=5)
        header, body = listener.get_latest_message()
        msg = json.loads(body)

        # Check if this is our VENUS message
        if msg.get("instrument") == "VENUS" and msg.get("run_number") == "12345":
            break

        # If not our message, keep waiting for the next one
        if attempt == max_attempts - 1:
            pytest.fail(f"Did not receive VENUS message after {max_attempts} attempts. Last message: {msg}")

    conn.disconnect()

    assert msg["run_number"] == message["run_number"]
    assert msg["instrument"] == message["instrument"]
    assert msg["ipts"] == message["ipts"]
    assert msg["facility"] == message["facility"]
    assert msg["data_file"] == message["data_file"]

    time.sleep(1)  # give oncat_server time to write its log
    log = docker_exec_and_cat("/oncat_server.log", "oncat").splitlines()

    # Check that the NeXus file was ingested
    assert any(
        "INFO Received datafile ingest request for /SNS/VENUS/IPTS-99999/nexus/VENUS_12345.nxs.h5" in line
        for line in log
    )

    # Check that batch ingestion was called with the image files
    assert any("INFO Received batch datafile ingest request for 3 files" in line for line in log)

    # Verify all three image files were logged
    assert any("INFO   - /SNS/VENUS/IPTS-99999/images/image_001.fits" in line for line in log)
    assert any("INFO   - /SNS/VENUS/IPTS-99999/images/image_002.fits" in line for line in log)
    assert any("INFO   - /SNS/VENUS/IPTS-99999/images/image_003.tiff" in line for line in log)


def test_oncat_reduction_catalog():
    """This should run reduction ONCatProcessor"""
    message = {
        "run_number": "29666",
        "instrument": "CORELLI",
        "ipts": "IPTS-15526",
        "facility": "SNS",
        "data_file": "/SNS/CORELLI/IPTS-15526/nexus/CORELLI_29666.nxs.h5",
    }

    conn = stomp.Connection(host_and_ports=[("localhost", 61613)])

    listener = stomp.listener.TestListener()
    conn.set_listener("", listener)

    try:
        conn.connect("icat", "icat")
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

    time.sleep(1)  # give oncat_server time to write its log
    log = docker_exec_and_cat("/oncat_server.log", "oncat").splitlines()
    # last line should indicate the file was ingested
    assert log[-1].endswith(
        "INFO Received reduction ingest request for /SNS/CORELLI/IPTS-15526/shared/autoreduce/CORELLI_29666.json"
    )


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

    listener = stomp.listener.TestListener()
    conn.set_listener("", listener)

    try:
        conn.connect("icat", "icat")
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

    assert msg["error"].startswith("SENDING TO Calvera: HTTPConnectionPool(host='not-valid.localhost', port=12345)")
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

    listener = stomp.listener.TestListener()
    conn.set_listener("", listener)

    try:
        conn.connect("icat", "icat")
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


def test_intersect():
    """Test intersect, expect an error as we don't have a real endpoint"""
    message = {
        "run_number": "30892",
        "instrument": "EQSANS",
        "ipts": "IPTS-10674",
        "facility": "SNS",
        "data_file": "/SNS/EQSANS/IPTS-10674/0/30892/NeXus/EQSANS_30892_event.nxs",
    }

    conn = stomp.Connection(host_and_ports=[("localhost", 61613)])

    listener = stomp.listener.TestListener()
    conn.set_listener("", listener)

    try:
        conn.connect("icat", "icat")
    except stomp.exception.ConnectFailedException:
        pytest.skip("Requires activemq running")

    # expect an error
    conn.subscribe("/queue/INTERSECT.RAW.ERROR", id="123", ack="auto")

    # send data ready
    conn.send("/queue/INTERSECT.RAW.DATA_READY", json.dumps(message).encode())

    listener.wait_for_message()

    conn.disconnect()

    header, body = listener.get_latest_message()

    msg = json.loads(body)
    assert msg["run_number"] == message["run_number"]
    assert msg["instrument"] == message["instrument"]
    assert msg["ipts"] == message["ipts"]
    assert msg["facility"] == message["facility"]
    assert msg["data_file"] == message["data_file"]

    assert msg["error"].startswith("SENDING TO Intersect: HTTPConnectionPool(host='not-valid.localhost', port=12345)")
    assert "Failed to establish a new connect" in msg["error"]


def test_intersect_reduced():
    """Test intersect for reduced data, expect error because there is no reduced data"""
    message = {
        "run_number": "30892",
        "instrument": "EQSANS",
        "ipts": "IPTS-10674",
        "facility": "SNS",
        "data_file": "/SNS/EQSANS/IPTS-10674/0/30892/NeXus/EQSANS_30892_event.nxs",
    }

    conn = stomp.Connection(host_and_ports=[("localhost", 61613)])

    listener = stomp.listener.TestListener()
    conn.set_listener("", listener)

    try:
        conn.connect("icat", "icat")
    except stomp.exception.ConnectFailedException:
        pytest.skip("Requires activemq running")

    # expect an error
    conn.subscribe("/queue/INTERSECT.REDUCED.ERROR", id="123", ack="auto")

    # send data ready
    conn.send("/queue/INTERSECT.REDUCED.DATA_READY", json.dumps(message).encode())

    listener.wait_for_message()

    conn.disconnect()

    header, body = listener.get_latest_message()

    msg = json.loads(body)
    assert msg["run_number"] == message["run_number"]
    assert msg["instrument"] == message["instrument"]
    assert msg["ipts"] == message["ipts"]
    assert msg["facility"] == message["facility"]
    assert msg["data_file"] == message["data_file"]

    assert msg["error"] == "SENDING TO Intersect: Cannot read reduced data info"
