import time
import json
import pytest
from tests.conftest import docker_exec_and_cat

import stomp


def test_default():
    """This should just replace reduce_TOPAZ.py with reduce_TOPAZ_default.py"""

    message = {"instrument": "TOPAZ", "use_default": True, "template_data": {}}

    conn = stomp.Connection(host_and_ports=[("localhost", 61613)])
    try:
        conn.connect('icat', 'icat')
    except stomp.exception.ConnectFailedException:
        pytest.skip("Requires activemq running")

    # send data ready
    conn.send("/queue/REDUCTION.CREATE_SCRIPT", json.dumps(message).encode())

    conn.disconnect()

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

    conn = stomp.Connection(host_and_ports=[("localhost", 61613)])
    try:
        conn.connect('icat', 'icat')
    except stomp.exception.ConnectFailedException:
        pytest.skip("Requires activemq running")

    # send data ready
    conn.send("/queue/REDUCTION.CREATE_SCRIPT", json.dumps(message).encode())

    conn.disconnect()

    time.sleep(1)

    # check that reduce_TOPAZ.py is updated correctly
    reduce_TOPAZ = docker_exec_and_cat("/SNS/TOPAZ/shared/autoreduce/reduce_TOPAZ.py")

    assert reduce_TOPAZ == "a=42\n"
