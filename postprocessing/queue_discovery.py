"""
Find the per-instrument queues on the broker, such as REDUCTION.CG2.DATA_READY, so the
consumer can subscribe to each one separately.

@copyright: 2026 Oak Ridge National Laboratory
"""

import re

import requests

# Shared queue -> its per-instrument queues. The workflow manager uppercases the instrument.
PER_INSTRUMENT_QUEUE_PATTERNS = {
    "/queue/REDUCTION.DATA_READY": re.compile(r"^REDUCTION\.(?P<instrument>[A-Z0-9_]+)\.DATA_READY$"),
    "/queue/REDUCTION.HIMEM.DATA_READY": re.compile(r"^REDUCTION\.HIMEM\.(?P<instrument>[A-Z0-9_]+)\.DATA_READY$"),
    "/queue/REDUCTION_CATALOG.DATA_READY": re.compile(r"^REDUCTION_CATALOG\.(?P<instrument>[A-Z0-9_]+)\.DATA_READY$"),
}

# Shared queues that also match REDUCTION.<X>.DATA_READY
NOT_INSTRUMENTS = {"HIMEM", "TESTPROCESSOR"}


def find_per_instrument_queues(queue_names, input_queues):
    """
    Pick the per-instrument queues for the configured processors

    @param queue_names: queue names on the broker, without the /queue/ prefix
    @param input_queues: input queues of the configured processors
    @returns dict of per-instrument queue -> input queue of its processor
    """
    patterns = {
        queue: PER_INSTRUMENT_QUEUE_PATTERNS[queue] for queue in input_queues if queue in PER_INSTRUMENT_QUEUE_PATTERNS
    }
    found = {}
    for name in queue_names:
        for input_queue, pattern in patterns.items():
            match = pattern.match(name)
            if match and match.group("instrument") not in NOT_INSTRUMENTS:
                found[f"/queue/{name}"] = input_queue
    return found


class JolokiaQueueLister:
    """
    List the queues on the broker through the Artemis management API (Jolokia)
    """

    # Matches the broker MBean whatever the broker is named
    BROKER_MBEAN = "org.apache.activemq.artemis:broker=*"

    def __init__(self, urls, user, password, timeout=10):
        """
        @param urls: Jolokia URLs, tried in order
        @param user: user with a management role on the broker
        @param password: password of that user
        @param timeout: seconds to wait for each broker
        """
        self.urls = urls
        self.auth = (user, password)
        self.timeout = timeout

    def queue_names(self):
        """
        Return the queue names from the first broker that answers
        """
        errors = []
        for url in self.urls:
            try:
                return self._queue_names(url)
            except Exception as e:
                errors.append(f"{url}: {e}")
        raise RuntimeError("Could not list queues on any broker: " + "; ".join(errors))

    def _queue_names(self, url):
        reply = requests.post(
            url,
            json={"type": "read", "mbean": self.BROKER_MBEAN, "attribute": "QueueNames"},
            auth=self.auth,
            # Jolokia rejects requests without an allowed origin
            headers={"Origin": "http://localhost"},
            timeout=self.timeout,
        )
        reply.raise_for_status()
        body = reply.json()
        if body.get("status") != 200:
            raise RuntimeError(body.get("error", f"Jolokia status {body.get('status')}"))
        # A user without access to the broker MBean gets an empty value instead of an error
        if not body.get("value"):
            raise RuntimeError("no broker MBean visible, check the user's management role")
        names = []
        for attributes in body["value"].values():
            names.extend(attributes["QueueNames"])
        return names
