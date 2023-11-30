import time
import json
import pytest
from tests.conftest import docker_exec_and_cat

from stompest.config import StompConfig
from stompest.sync import Stomp
from stompest.error import StompConnectTimeout


def test_default():
    """This should just replace reduce_TOPAZ.py with reduce_TOPAZ_default.py"""

    message = {"instrument": "TOPAZ", "use_default": True, "template_data": {}}

    client = Stomp(StompConfig("tcp://localhost:61613"))
    try:
        client.connect()
    except StompConnectTimeout:
        pytest.skip("Requires activemq running")

    # send data ready
    client.send("/queue/REDUCTION.CREATE_SCRIPT", json.dumps(message))

    client.disconnect()

    time.sleep(1)

    # check that reduce_TOPAZ.py is updated correctly
    reduce_TOPAZ = docker_exec_and_cat("/SNS/TOPAZ/shared/autoreduce/reduce_TOPAZ.py")

    assert reduce_TOPAZ == "a=1\n"


def test_template():
    """This should just replace reduce_TOPAZ.py with reduce_TOPAZ_default.py"""

    message = {
        "instrument": "TOPAZ",
        "use_default": False,
        "template_data": {"value": 42},
    }

    client = Stomp(StompConfig("tcp://localhost:61613"))
    try:
        client.connect()
    except StompConnectTimeout:
        pytest.skip("Requires activemq running")

    # send data ready
    client.send("/queue/REDUCTION.CREATE_SCRIPT", json.dumps(message))

    client.disconnect()

    time.sleep(1)

    # check that reduce_TOPAZ.py is updated correctly
    reduce_TOPAZ = docker_exec_and_cat("/SNS/TOPAZ/shared/autoreduce/reduce_TOPAZ.py")

    assert reduce_TOPAZ == "a=42\n"
