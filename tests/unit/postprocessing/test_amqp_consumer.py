# package imports
from postprocessing import amqp_consumer
from postprocessing.amqp_consumer import AmqpConsumer, amqp_address, capability
from postprocessing.Consumer import HEARTBEAT_DELAY

# third-party imports
import pytest

# standard imports
import json
import logging

CATALOG = "/queue/CATALOG.ONCAT.DATA_READY"
REDUCTION_CATALOG = "/queue/REDUCTION_CATALOG.DATA_READY"
REDUCTION = "/queue/REDUCTION.DATA_READY"
CG2 = "/queue/REDUCTION.CG2.DATA_READY"
PING = "/topic/SNS.COMMON.STATUS.PING"


def make_link(mocker, name, address, is_sender=False, credit=0):
    # Mock(name=...) names the mock itself, so set the link name afterwards
    link = mocker.Mock(is_sender=is_sender, credit=credit)
    link.name = name
    link.draining.return_value = False
    link.remote_condition = None
    if is_sender:
        link.target.address = address
    else:
        link.source.address = address
    return link


@pytest.fixture
def threads(mocker):
    """Threads the consumer would start, as (target, args)"""
    started = []

    def thread(target, args=(), daemon=None):
        started.append((target, args))
        return mocker.Mock()

    mocker.patch("postprocessing.amqp_consumer.threading.Thread", side_effect=thread)
    return started


@pytest.fixture
def start(make_config, mocker, threads):
    """A started consumer with a mocked container, connection and injector"""
    mocker.patch("postprocessing.amqp_consumer.signal.signal")
    mocker.patch("postprocessing.amqp_consumer.EventInjector")

    def _start(**overrides):
        consumer = AmqpConsumer(make_config(**overrides))
        container = mocker.Mock()
        container.create_receiver.side_effect = lambda conn, address, name, options: make_link(mocker, name, address)
        container.create_sender.side_effect = lambda conn, address, name, options: make_link(
            mocker, name, address, is_sender=True
        )
        mocker.patch.object(consumer, "accept")
        mocker.patch.object(consumer, "release")
        consumer.on_start(mocker.Mock(container=container))
        return consumer

    return _start


def event(mocker, **kwargs):
    return mocker.Mock(**kwargs)


def receiver(consumer, queue):
    return next(r for r, q in consumer.receivers if q == queue)


def open_links(consumer, mocker, queues=None):
    for r, q in consumer.receivers:
        if queues is None or q in queues:
            consumer.on_link_opened(event(mocker, receiver=r))


def come_back_empty(consumer, mocker, r):
    """The broker answers a drain with no message"""
    r.credit = 0
    consumer.on_link_flow(event(mocker, receiver=r))


def message(consumer, mocker, r, body):
    e = event(mocker, receiver=r)
    e.message.body = body
    consumer.on_message(e)
    return e


def scheduled(consumer, delay):
    """Callbacks of the timers scheduled with this delay"""
    return [c.args[1].callback for c in consumer.container.schedule.call_args_list if c.args[0] == delay]


def test_addresses():
    assert amqp_address(REDUCTION) == "REDUCTION.DATA_READY"
    assert amqp_address(PING) == "SNS.COMMON.STATUS.PING"
    assert amqp_address("REDUCTION.DATA_READY") == "REDUCTION.DATA_READY"
    assert capability(PING) == "topic"
    assert capability(REDUCTION) == capability("REDUCTION.DATA_READY") == "queue"


class TestStart:
    def test_connects_and_opens_links(self, start):
        consumer = start()
        consumer.container.connect.assert_called_once_with(
            urls=["amqp://broker1:5672", "amqp://broker2:5672"],
            user="user",
            password="secret",
            allowed_mechs="PLAIN",
            allow_insecure_mechs=True,
        )
        assert [q for _, q in consumer.receivers] == [CATALOG, REDUCTION_CATALOG, REDUCTION]
        links = {c.args[1]: c.kwargs["options"].capability for c in consumer.container.create_receiver.call_args_list}
        assert links == {
            "CATALOG.ONCAT.DATA_READY": "queue",
            "REDUCTION_CATALOG.DATA_READY": "queue",
            "REDUCTION.DATA_READY": "queue",
            "SNS.COMMON.STATUS.PING": "topic",
        }

    def test_ping_topic_is_not_pulled(self, make_config, mocker):
        mocker.patch("postprocessing.amqp_consumer.signal.signal")
        config = make_config()
        # The STOMP consumer adds the ping topic to the queues
        config.queues.append(PING)
        assert PING not in AmqpConsumer(config).input_queues

    def test_no_discovery_by_default(self, start, threads):
        start()
        assert threads == []


class TestPulling:
    def test_takes_queues_in_turn(self, start, mocker):
        consumer = start()
        open_links(consumer, mocker)
        catalog, reduction_catalog, reduction = (r for r, _ in consumer.receivers)
        catalog.drain.assert_called_once_with(1)
        come_back_empty(consumer, mocker, catalog)
        reduction_catalog.drain.assert_called_once_with(1)
        come_back_empty(consumer, mocker, reduction_catalog)
        reduction.drain.assert_called_once_with(1)

        # Every queue was empty: wait before going round again
        come_back_empty(consumer, mocker, reduction)
        assert consumer.pending is None
        retry = scheduled(consumer, amqp_consumer.IDLE_RETRY_SEC)
        assert len(retry) == 1
        retry[0]()
        assert catalog.drain.call_count == 2

    def test_skips_links_that_are_not_open(self, start, mocker):
        consumer = start()
        open_links(consumer, mocker, [CATALOG, REDUCTION])
        come_back_empty(consumer, mocker, receiver(consumer, CATALOG))
        receiver(consumer, REDUCTION_CATALOG).drain.assert_not_called()
        receiver(consumer, REDUCTION).drain.assert_called_once_with(1)

    def test_runs_one_job_at_a_time(self, start, mocker, threads):
        consumer = start()
        open_links(consumer, mocker)
        catalog = receiver(consumer, CATALOG)
        e = message(consumer, mocker, catalog, memoryview(b'{"run_number": "1"}'))
        consumer.accept.assert_called_once_with(e.delivery)
        assert consumer.busy
        assert threads == [(consumer._run_job, (CATALOG, '{"run_number": "1"}'))]
        # Nothing else is asked for while the job runs
        receiver(consumer, REDUCTION_CATALOG).drain.assert_not_called()

        consumer.on_job_done(event(mocker))
        assert not consumer.busy
        receiver(consumer, REDUCTION_CATALOG).drain.assert_called_once_with(1)

    def test_per_instrument_queue_runs_on_shared_queue(self, start, mocker, threads):
        consumer = start()
        consumer.add_queue(CG2, REDUCTION)
        consumer.add_queue(CG2, REDUCTION)
        assert [q for _, q in consumer.receivers].count(CG2) == 1
        cg2 = receiver(consumer, CG2)
        consumer.on_link_opened(event(mocker, receiver=cg2))
        message(consumer, mocker, cg2, b"{}")
        assert threads == [(consumer._run_job, (REDUCTION, "{}"))]

    def test_late_message_is_given_back(self, start, mocker, threads):
        consumer = start()
        open_links(consumer, mocker)
        consumer.busy = True
        e = message(consumer, mocker, receiver(consumer, REDUCTION), b"{}")
        consumer.release.assert_called_once_with(e.delivery, delivered=False)
        consumer.accept.assert_not_called()
        assert threads == []

    def test_unreadable_message_counts_as_failed(self, start, mocker, threads, caplog):
        consumer = start()
        open_links(consumer, mocker)
        stranger = make_link(mocker, "not ours", "SOMEWHERE")
        e = message(consumer, mocker, stranger, b"{}")
        consumer.release.assert_called_once_with(e.delivery, delivered=True)
        assert threads == []
        assert "Could not read a message" in caplog.text
        # and it moves on to the next queue
        receiver(consumer, REDUCTION_CATALOG).drain.assert_called_once_with(1)

    def test_queue_added_before_start(self, make_config, mocker):
        mocker.patch("postprocessing.amqp_consumer.signal.signal")
        consumer = AmqpConsumer(make_config())
        consumer.add_queue(CG2, REDUCTION)
        assert consumer.input_queues[CG2] == REDUCTION
        assert consumer.receivers == []


class TestRunJob:
    def test_runs_post_processing(self, start, mocker):
        consumer = start()
        popen = mocker.patch("postprocessing.amqp_consumer.subprocess.Popen")
        popen.return_value.stdout = [b"reducing\n"]
        logged = mocker.patch("postprocessing.amqp_consumer.logging.subprocess", create=True)
        consumer._run_job(REDUCTION, '{"a": 1}')
        assert popen.call_args.args[0] == [
            "python",
            "/opt/postprocessing/postprocessing/PostProcessAdmin.py",
            "-q",
            REDUCTION,
            "-d",
            '{"a":1}',
        ]
        logged.assert_called_once_with("reducing")
        assert consumer.injector.trigger.call_args.args[0].type.name == "job_done"

    def test_waits_for_the_job_after_a_bad_byte(self, start, mocker):
        consumer = start()
        popen = mocker.patch("postprocessing.amqp_consumer.subprocess.Popen")
        popen.return_value.stdout = [b"bad \xff byte\n", b"done\n"]
        logged = mocker.patch("postprocessing.amqp_consumer.logging.subprocess", create=True)
        consumer._run_job(REDUCTION, "{}")
        assert [c.args[0] for c in logged.call_args_list] == ["bad � byte", "done"]
        popen.return_value.wait.assert_called_once()

    def test_job_done_after_an_error(self, start, mocker, caplog):
        consumer = start()
        mocker.patch("postprocessing.amqp_consumer.subprocess.Popen", side_effect=OSError("no such file"))
        consumer._run_job(REDUCTION, "{}")
        assert "Error running post-processing" in caplog.text
        assert consumer.injector.trigger.call_args.args[0].type.name == "job_done"


class TestExit:
    def test_finishes_the_job_first(self, start, mocker):
        consumer = start()
        consumer.busy = True
        consumer.exit_gracefully()
        assert consumer.injector.trigger.call_args.args[0].type.name == "exit_request"
        consumer.on_exit_request(event(mocker))
        consumer.container.stop.assert_not_called()
        consumer.on_job_done(event(mocker))
        consumer.connection.close.assert_called_once()
        consumer.container.stop.assert_called_once()

    def test_stops_right_away_when_idle(self, start, mocker):
        consumer = start()
        consumer.exit_gracefully()
        consumer.on_exit_request(event(mocker))
        consumer.container.stop.assert_called_once()

    def test_no_new_work_while_exiting(self, start, mocker):
        consumer = start()
        consumer.exit_gracefully()
        open_links(consumer, mocker)
        for r, _ in consumer.receivers:
            r.drain.assert_not_called()


class TestHeartbeats:
    def test_sent_at_start_and_every_30_s(self, start, mocker):
        consumer = start()
        sender = consumer.senders["SNS.COMMON.STATUS.AUTOREDUCE.0"]
        assert consumer.container.create_sender.call_args.kwargs["options"].capability == "topic"
        # no credit yet, so it waits
        assert json.loads(consumer.outbox["SNS.COMMON.STATUS.AUTOREDUCE.0"])["role"] == "postprocessing"
        sender.credit = 1
        consumer.on_sendable(event(mocker))
        sent = sender.send.call_args.args[0]
        assert json.loads(sent.body)["status"] == "0"
        assert sent.creation_time > 0
        assert consumer.outbox == {}
        assert len(scheduled(consumer, HEARTBEAT_DELAY)) == 1

    def test_only_the_latest_waits_for_credit(self, start, mocker):
        consumer = start()
        for i in range(3):
            consumer.send("/topic/SOMEWHERE", str(i))
        sender = consumer.senders["SOMEWHERE"]
        sender.send.assert_not_called()
        sender.credit = 5
        consumer.on_sendable(event(mocker))
        sender.send.assert_called_once()
        assert sender.send.call_args.args[0].body == "2"


class TestPings:
    def ping(self, consumer, mocker, body):
        return message(consumer, mocker, consumer.ping_receiver, body)

    def test_answered_during_a_job(self, start, mocker):
        consumer = start()
        consumer.busy = True
        e = self.ping(consumer, mocker, b'{"reply_to": "/topic/SNS.COMMON.STATUS.ACK", "request_time": 12.5}')
        consumer.accept.assert_called_once_with(e.delivery)
        consumer.ping_receiver.flow.assert_called_with(1)
        reply = json.loads(consumer.outbox["SNS.COMMON.STATUS.ACK"])
        assert reply["request_time"] == 12.5
        assert reply["role"] == "postprocessing"
        assert reply["pid"].isnumeric()
        assert consumer.container.create_sender.call_args.kwargs["options"].capability == "topic"

    def test_reply_to_a_queue(self, start, mocker):
        consumer = start()
        self.ping(consumer, mocker, '{"reply_to": "/queue/PING_TEST"}')
        assert "PING_TEST" in consumer.outbox
        assert consumer.container.create_sender.call_args.kwargs["options"].capability == "queue"

    @pytest.mark.parametrize(
        "body, error",
        [(b'{"no": "reply_to"}', "Incomplete ping request"), (b"not json", "Could not read ping request")],
    )
    def test_bad_ping(self, start, mocker, caplog, body, error):
        consumer = start()
        self.ping(consumer, mocker, body)
        assert error in caplog.text
        assert list(consumer.outbox) == ["SNS.COMMON.STATUS.AUTOREDUCE.0"]

    def test_credit_topped_up_when_the_link_opens(self, start, mocker):
        consumer = start()
        ping = consumer.ping_receiver
        ping.credit = 4
        consumer.on_link_opened(event(mocker, receiver=ping))
        ping.flow.assert_called_once_with(amqp_consumer.PING_CREDIT - 4)
        assert ping.name not in consumer.opened


class TestLinkFailures:
    def test_one_bad_link_keeps_the_connection(self, start, mocker, caplog):
        consumer = start()
        link = receiver(consumer, REDUCTION)
        link.remote_condition = mocker.Mock(description="queue deleted")
        consumer.on_link_error(event(mocker, link=link))
        assert "The broker closed the link for REDUCTION.DATA_READY: queue deleted" in caplog.text
        consumer.connection.close.assert_not_called()

    def test_configured_queue_is_tried_again(self, start, mocker):
        consumer = start()
        open_links(consumer, mocker)
        catalog = receiver(consumer, CATALOG)
        assert consumer.pending is catalog
        consumer.on_link_closed(event(mocker, link=catalog))
        assert CATALOG not in consumer.input_queues
        assert catalog.name not in consumer.opened
        # it stops waiting on that queue and asks the next one
        receiver(consumer, REDUCTION_CATALOG).drain.assert_called_once_with(1)

        retry = scheduled(consumer, amqp_consumer.RELINK_DELAY_SEC)
        assert len(retry) == 1
        retry[0]()
        assert consumer.input_queues[CATALOG] == CATALOG
        assert receiver(consumer, CATALOG) is not catalog

    def test_discovered_queue_is_left_to_discovery(self, start, mocker):
        consumer = start(per_instrument_queues=True)
        consumer.add_queue(CG2, REDUCTION)
        consumer.on_link_closed(event(mocker, link=receiver(consumer, CG2)))
        assert CG2 not in consumer.input_queues
        assert scheduled(consumer, amqp_consumer.RELINK_DELAY_SEC) == []
        consumer.on_queues_listed(event(mocker, subject=(["REDUCTION.CG2.DATA_READY"], None)))
        assert consumer.input_queues[CG2] == REDUCTION

    def test_ping_link_is_tried_again(self, start, mocker):
        consumer = start()
        ping = consumer.ping_receiver
        consumer.on_link_closed(event(mocker, link=ping))
        scheduled(consumer, amqp_consumer.RELINK_DELAY_SEC)[0]()
        assert consumer.ping_receiver is not ping
        assert consumer.ping_receiver.source.address == "SNS.COMMON.STATUS.PING"

    def test_closed_sender_is_made_again(self, start, mocker):
        consumer = start()
        sender = consumer.senders["SNS.COMMON.STATUS.AUTOREDUCE.0"]
        consumer.on_link_closed(event(mocker, link=sender))
        assert consumer.senders == {}
        assert consumer.outbox == {}
        consumer.send_heartbeat()
        assert consumer.senders["SNS.COMMON.STATUS.AUTOREDUCE.0"] is not sender

    def test_reconnect_waits_for_links(self, start, mocker):
        consumer = start()
        open_links(consumer, mocker)
        e = event(mocker)
        consumer.on_disconnected(e)
        assert consumer.opened == set()
        assert consumer.pending is None
        # closing our side is what makes proton reconnect right away
        e.transport.close_head.assert_called_once()
        consumer.next_queue()
        assert receiver(consumer, REDUCTION_CATALOG).drain.call_count == 0

    def test_outage_logged_once(self, start, mocker, caplog):
        caplog.set_level(logging.INFO)
        consumer = start()
        for _ in range(4):
            # proton reports each failed attempt
            consumer.on_disconnected(event(mocker))
        assert caplog.text.count("Lost the AMQP connection") == 1
        consumer.on_connection_opened(event(mocker))
        assert "Reconnected over AMQP" in caplog.text
        consumer.on_disconnected(event(mocker))
        assert caplog.text.count("Lost the AMQP connection") == 2

    def test_closes_ignored_while_exiting(self, start, mocker):
        consumer = start()
        consumer._exit = True
        consumer.on_link_closed(event(mocker, link=receiver(consumer, CATALOG)))
        assert CATALOG in consumer.input_queues


class TestDiscovery:
    def test_runs_in_a_thread(self, start, threads):
        consumer = start(per_instrument_queues=True)
        assert threads == [(consumer._list_queues, ())]

    def test_adds_new_queues(self, start, mocker, caplog):
        caplog.set_level(logging.INFO)
        consumer = start(per_instrument_queues=True, queue_discovery_interval_sec=5)
        broker = ["REDUCTION.CG2.DATA_READY", "REDUCTION.HIMEM.CG2.DATA_READY", "SOMETHING.ELSE"]
        consumer.on_queues_listed(event(mocker, subject=(broker, None)))
        # HIMEM isn't one of this agent's processors
        assert consumer.input_queues[CG2] == REDUCTION
        assert "/queue/REDUCTION.HIMEM.CG2.DATA_READY" not in consumer.input_queues
        assert "Subscribed to new per-instrument queues: ['/queue/REDUCTION.CG2.DATA_READY']" in caplog.text
        assert len(scheduled(consumer, 5)) == 1

        receivers = len(consumer.receivers)
        consumer.on_queues_listed(event(mocker, subject=(broker, None)))
        assert len(consumer.receivers) == receivers

    def test_failure_keeps_the_queues(self, start, mocker, caplog):
        consumer = start(per_instrument_queues=True)
        consumer.add_queue(CG2, REDUCTION)
        consumer.on_queues_listed(event(mocker, subject=([], RuntimeError("broker down"))))
        assert "Per-instrument queue discovery failed, keeping 4 queues: broker down" in caplog.text
        assert CG2 in consumer.input_queues
        assert len(scheduled(consumer, 60.0)) == 1

    def test_lists_queues_off_the_container_thread(self, start, mocker):
        consumer = start(per_instrument_queues=True)
        consumer._queue_lister = mocker.Mock()
        consumer._queue_lister.queue_names.return_value = ["REDUCTION.CG2.DATA_READY"]
        consumer._list_queues()
        sent = consumer.injector.trigger.call_args.args[0]
        assert sent.type.name == "queues_listed"
        assert sent.subject == (["REDUCTION.CG2.DATA_READY"], None)

        error = RuntimeError("403")
        consumer._queue_lister.queue_names.side_effect = error
        consumer._list_queues()
        assert consumer.injector.trigger.call_args.args[0].subject == ([], error)

        consumer.injector.trigger.reset_mock()
        consumer._exit = True
        consumer._list_queues()
        consumer.injector.trigger.assert_not_called()
