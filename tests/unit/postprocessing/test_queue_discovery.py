# package imports
from postprocessing.queue_discovery import JolokiaQueueLister, find_per_instrument_queues

# third-party imports
import pytest
import requests

BROKER_QUEUES = [
    "REDUCTION.DATA_READY",
    "REDUCTION.CG2.DATA_READY",
    "REDUCTION.EQSANS.DATA_READY",
    "REDUCTION.BL_3.DATA_READY",
    "REDUCTION.HIMEM.DATA_READY",
    "REDUCTION.HIMEM.CG2.DATA_READY",
    "REDUCTION.TESTPROCESSOR.DATA_READY",
    "REDUCTION_CATALOG.DATA_READY",
    "REDUCTION_CATALOG.CG2.DATA_READY",
    "CATALOG.ONCAT.DATA_READY",
    "CALVERA.RAW.DATA_READY",
    "REDUCTION.cg2.DATA_READY",
    "REDUCTION.CG2.STARTED",
    "REDUCTION.CG2.EXTRA.DATA_READY",
    "DLQ",
]


class TestFindPerInstrumentQueues:
    def test_regular_reduction(self):
        found = find_per_instrument_queues(BROKER_QUEUES, ["/queue/REDUCTION.DATA_READY"])
        assert found == {
            "/queue/REDUCTION.CG2.DATA_READY": "/queue/REDUCTION.DATA_READY",
            "/queue/REDUCTION.EQSANS.DATA_READY": "/queue/REDUCTION.DATA_READY",
            "/queue/REDUCTION.BL_3.DATA_READY": "/queue/REDUCTION.DATA_READY",
        }

    def test_high_memory_reduction(self):
        found = find_per_instrument_queues(BROKER_QUEUES, ["/queue/REDUCTION.HIMEM.DATA_READY"])
        assert found == {"/queue/REDUCTION.HIMEM.CG2.DATA_READY": "/queue/REDUCTION.HIMEM.DATA_READY"}

    def test_reduction_cataloging(self):
        found = find_per_instrument_queues(BROKER_QUEUES, ["/queue/REDUCTION_CATALOG.DATA_READY"])
        assert found == {"/queue/REDUCTION_CATALOG.CG2.DATA_READY": "/queue/REDUCTION_CATALOG.DATA_READY"}

    def test_queues_that_are_not_split(self):
        input_queues = [
            "/queue/CATALOG.ONCAT.DATA_READY",
            "/queue/CALVERA.RAW.DATA_READY",
            "/queue/REDUCTION.TESTPROCESSOR.DATA_READY",
            "/topic/SNS.COMMON.STATUS.PING",
        ]
        assert find_per_instrument_queues(BROKER_QUEUES, input_queues) == {}

    def test_all_processors(self):
        input_queues = [
            "/queue/CATALOG.ONCAT.DATA_READY",
            "/queue/REDUCTION_CATALOG.DATA_READY",
            "/queue/REDUCTION.DATA_READY",
            "/queue/REDUCTION.HIMEM.DATA_READY",
        ]
        found = find_per_instrument_queues(BROKER_QUEUES, input_queues)
        assert sorted(found) == [
            "/queue/REDUCTION.BL_3.DATA_READY",
            "/queue/REDUCTION.CG2.DATA_READY",
            "/queue/REDUCTION.EQSANS.DATA_READY",
            "/queue/REDUCTION.HIMEM.CG2.DATA_READY",
            "/queue/REDUCTION_CATALOG.CG2.DATA_READY",
        ]
        assert found["/queue/REDUCTION.HIMEM.CG2.DATA_READY"] == "/queue/REDUCTION.HIMEM.DATA_READY"


def jolokia_reply(mocker, body, status_code=200):
    reply = mocker.Mock(status_code=status_code)
    reply.json.return_value = body
    if status_code != 200:
        reply.raise_for_status.side_effect = requests.HTTPError(f"{status_code} Client Error")
    return reply


class TestJolokiaQueueLister:
    URLS = ["http://broker1:8161/console/jolokia", "http://broker2:8161/console/jolokia"]

    def test_queue_names(self, mocker):
        body = {
            "status": 200,
            "value": {
                'org.apache.activemq.artemis:broker="Artemis-Broker"': {"QueueNames": ["DLQ", "REDUCTION.DATA_READY"]}
            },
        }
        post = mocker.patch("postprocessing.queue_discovery.requests.post", return_value=jolokia_reply(mocker, body))
        lister = JolokiaQueueLister(self.URLS, "user", "secret")
        assert lister.queue_names() == ["DLQ", "REDUCTION.DATA_READY"]
        post.assert_called_once()
        args, kwargs = post.call_args
        assert args == (self.URLS[0],)
        assert kwargs["auth"] == ("user", "secret")
        assert kwargs["json"]["mbean"] == "org.apache.activemq.artemis:broker=*"
        assert kwargs["headers"]["Origin"] == "http://localhost"

    def test_failover(self, mocker):
        body = {"status": 200, "value": {"broker": {"QueueNames": ["REDUCTION.CG2.DATA_READY"]}}}
        post = mocker.patch(
            "postprocessing.queue_discovery.requests.post",
            side_effect=[requests.ConnectionError("refused"), jolokia_reply(mocker, body)],
        )
        assert JolokiaQueueLister(self.URLS, "user", "secret").queue_names() == ["REDUCTION.CG2.DATA_READY"]
        assert [c.args[0] for c in post.call_args_list] == self.URLS

    @pytest.mark.parametrize(
        "status_code, body, message",
        [
            (403, {}, "403 Client Error"),
            (200, {"status": 404, "error": "No MBean found"}, "No MBean found"),
            (200, {"status": 200, "value": {}}, "no broker MBean visible"),
        ],
    )
    def test_errors(self, mocker, status_code, body, message):
        mocker.patch(
            "postprocessing.queue_discovery.requests.post", return_value=jolokia_reply(mocker, body, status_code)
        )
        with pytest.raises(RuntimeError) as exception_info:
            JolokiaQueueLister(self.URLS, "user", "secret").queue_names()
        # both brokers are named in the error
        assert str(exception_info.value).count(message) == 2
        assert self.URLS[1] in str(exception_info.value)
