import json
import pytest

from stompest.config import StompConfig
from stompest.sync import Stomp
from stompest.error import StompConnectTimeout


def test_oncat_catalog():
    """This should just replace reduce_TOPAZ.py with reduce_TOPAZ_default.py"""
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
    client.send("/queue/CATALOG.ONCAT.DATA_READY", json.dumps(message))

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
