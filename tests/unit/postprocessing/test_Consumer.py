# package imports
from postprocessing.Consumer import Consumer, Listener

# third-party imports
import pytest

# standard imports
import json
import logging

SHARED_QUEUES = [
    "/queue/CATALOG.ONCAT.DATA_READY",
    "/queue/REDUCTION_CATALOG.DATA_READY",
    "/queue/REDUCTION.DATA_READY",
    "/topic/SNS.COMMON.STATUS.PING",
]


@pytest.fixture
def connection(mocker):
    """Replace the STOMP connection with a mock"""
    conn = mocker.Mock()
    mocker.patch("postprocessing.Consumer.stomp.Connection", return_value=conn)
    mocker.patch("postprocessing.Consumer.time.sleep")
    return conn


@pytest.fixture
def broker_queues(mocker):
    """Queue names returned by the broker, editable by the test"""
    queues = []
    mocker.patch("postprocessing.Consumer.JolokiaQueueLister.queue_names", side_effect=lambda: list(queues))
    return queues


def subscribed(conn):
    return [c.kwargs["destination"] for c in conn.subscribe.call_args_list]


class TestPerInstrumentConfiguration:
    def test_defaults(self, make_config):
        conf = make_config()
        assert conf.per_instrument_queues is False
        assert conf.queue_discovery_interval_sec == 60.0
        assert conf.jolokia_urls == ["http://broker1:8161/console/jolokia", "http://broker2:8161/console/jolokia"]
        assert (conf.jolokia_user, conf.jolokia_pwd) == ("user", "secret")

    def test_log_mode(self, make_config, test_logger):
        make_config().log_configuration(logger=test_logger.logger)
        make_config(per_instrument_queues=True).log_configuration(logger=test_logger.logger)
        log_contents = open(test_logger.log_file).read()
        assert "Per-instrument queues: disabled" in log_contents
        assert "Per-instrument queues: ENABLED, discovered every 60.0 s" in log_contents


class TestConsumerProtocol:
    def test_default_is_stomp(self, make_config):
        conf = make_config()
        assert conf.consumer_protocol == "stomp"
        assert conf.amqp_brokers == [("broker1", 5672), ("broker2", 5672)]

    def test_amqp(self, make_config, test_logger):
        conf = make_config(consumer_protocol="AMQP", amqp_brokers=[["broker1", 5673]])
        assert conf.consumer_protocol == "amqp"
        assert conf.amqp_brokers == [("broker1", 5673)]
        conf.log_configuration(logger=test_logger.logger)
        assert "Consumer protocol: AMQP" in open(test_logger.log_file).read()

    def test_unknown(self, make_config):
        with pytest.raises(RuntimeError, match="consumer_protocol must be stomp or amqp, not 'openwire'"):
            make_config(consumer_protocol="openwire")


class TestConsumer:
    def test_flag_off(self, make_config, connection, mocker):
        consumer = Consumer(make_config())
        discover = mocker.patch.object(consumer, "discover_queues")
        connection.is_connected.return_value = False
        # stop after one pass through the loop
        mocker.patch("postprocessing.Consumer.time.sleep", side_effect=lambda _: setattr(consumer, "_exit", True))
        consumer.listen_and_wait()
        discover.assert_not_called()
        assert subscribed(connection) == SHARED_QUEUES
        for c in connection.subscribe.call_args_list:
            assert c.kwargs["ack"] == "client"
            assert c.kwargs["headers"] == {"activemq.prefetchSize": 0}

    def test_discovery_adds_new_queues(self, make_config, connection, broker_queues, caplog):
        caplog.set_level(logging.INFO)
        consumer = Consumer(make_config(per_instrument_queues=True))
        consumer.connect()
        broker_queues.extend(["REDUCTION.CG2.DATA_READY", "REDUCTION.HIMEM.CG2.DATA_READY"])
        consumer.discover_queues()
        assert subscribed(connection) == SHARED_QUEUES + ["/queue/REDUCTION.CG2.DATA_READY"]
        assert consumer.per_instrument_to_shared_queue_map == {
            "/queue/REDUCTION.CG2.DATA_READY": "/queue/REDUCTION.DATA_READY"
        }

        # only the new instrument's queues get subscribed
        connection.subscribe.reset_mock()
        broker_queues.extend(["REDUCTION.EQSANS.DATA_READY", "REDUCTION_CATALOG.EQSANS.DATA_READY"])
        consumer.discover_queues()
        assert subscribed(connection) == [
            "/queue/REDUCTION.EQSANS.DATA_READY",
            "/queue/REDUCTION_CATALOG.EQSANS.DATA_READY",
        ]
        assert consumer.per_instrument_to_shared_queue_map["/queue/REDUCTION_CATALOG.EQSANS.DATA_READY"] == (
            "/queue/REDUCTION_CATALOG.DATA_READY"
        )

        # nothing changed
        connection.subscribe.reset_mock()
        caplog.clear()
        consumer.discover_queues()
        connection.subscribe.assert_not_called()
        assert "per-instrument" not in caplog.text

    def test_discovery_logs_new_queues(self, make_config, connection, broker_queues, caplog):
        caplog.set_level(logging.INFO)
        consumer = Consumer(make_config(per_instrument_queues=True))
        consumer.connect()
        consumer.discover_queues()
        assert "per-instrument" not in caplog.text
        broker_queues.append("REDUCTION.CG2.DATA_READY")
        consumer.discover_queues()
        assert "Subscribed to new per-instrument queues: ['/queue/REDUCTION.CG2.DATA_READY']" in caplog.text

    def test_discovery_failure_keeps_subscriptions(self, make_config, connection, mocker, caplog):
        consumer = Consumer(make_config(per_instrument_queues=True))
        consumer.connect()
        consumer.per_instrument_to_shared_queue_map["/queue/REDUCTION.CG2.DATA_READY"] = "/queue/REDUCTION.DATA_READY"
        mocker.patch(
            "postprocessing.Consumer.JolokiaQueueLister.queue_names", side_effect=RuntimeError("broker unreachable")
        )
        connection.subscribe.reset_mock()
        consumer.discover_queues()
        connection.unsubscribe.assert_not_called()
        connection.subscribe.assert_not_called()
        assert consumer.per_instrument_to_shared_queue_map == {
            "/queue/REDUCTION.CG2.DATA_READY": "/queue/REDUCTION.DATA_READY"
        }
        assert "discovery failed, keeping 1 subscriptions: broker unreachable" in caplog.text

    def test_resubscribe_after_reconnect(self, make_config, connection, broker_queues):
        consumer = Consumer(make_config(per_instrument_queues=True))
        consumer.connect()
        broker_queues.append("REDUCTION.CG2.DATA_READY")
        consumer.discover_queues()
        # the broker drops the connection
        connection.is_connected.return_value = False
        connection.subscribe.reset_mock()
        consumer.connect()
        assert subscribed(connection) == SHARED_QUEUES + ["/queue/REDUCTION.CG2.DATA_READY"]

    def test_discovery_interval(self, make_config, connection, mocker):
        consumer = Consumer(make_config(per_instrument_queues=True, queue_discovery_interval_sec=30))
        discover = mocker.patch.object(consumer, "discover_queues")
        connection.is_connected.return_value = True
        consumer._connection = connection
        clock = mocker.patch("postprocessing.Consumer.time.time", return_value=1000.0)
        loops = iter([1000.0, 1010.0, 1031.0])

        def next_loop(_):
            try:
                clock.return_value = next(loops)
            except StopIteration:
                consumer._exit = True

        mocker.patch("postprocessing.Consumer.time.sleep", side_effect=next_loop)
        discover.side_effect = lambda: setattr(consumer, "_last_discovery", clock.return_value)
        consumer.listen_and_wait()
        # runs on the first pass and again at 1031
        assert discover.call_count == 2


class TestListener:
    @pytest.mark.parametrize(
        "destination, expected_queue",
        [
            ("/queue/REDUCTION.CG2.DATA_READY", "/queue/REDUCTION.DATA_READY"),
            ("/queue/REDUCTION_CATALOG.CG2.DATA_READY", "/queue/REDUCTION_CATALOG.DATA_READY"),
            ("/queue/REDUCTION.DATA_READY", "/queue/REDUCTION.DATA_READY"),
        ],
    )
    def test_queue_passed_to_post_process_admin(self, make_config, mocker, destination, expected_queue):
        popen = mocker.patch("postprocessing.Consumer.subprocess.Popen")
        popen.return_value.stdout.readlines.return_value = []
        per_instrument_to_shared_queue_map = {
            "/queue/REDUCTION.CG2.DATA_READY": "/queue/REDUCTION.DATA_READY",
            "/queue/REDUCTION_CATALOG.CG2.DATA_READY": "/queue/REDUCTION_CATALOG.DATA_READY",
        }
        conn = mocker.Mock()
        listener = Listener(make_config(), conn, per_instrument_to_shared_queue_map)
        frame = mocker.Mock(
            headers={"destination": destination, "subscription": destination, "message-id": "1"},
            body=json.dumps({"instrument": "CG2", "run_number": "1"}),
        )
        listener.on_message(frame)
        conn.ack.assert_called_once_with("1", destination)
        command_args = popen.call_args.args[0]
        assert command_args[command_args.index("-q") + 1] == expected_queue
