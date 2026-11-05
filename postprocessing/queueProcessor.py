#!/usr/bin/env python3
"""
Post-processing agent start script

@copyright: 2014 Oak Ridge National Laboratory
"""

import importlib.metadata
import logging

# The configuration includes setting up logging, which should be done first
from postprocessing.Configuration import read_configuration

configuration = read_configuration()

# Only load the AMQP client when it's used, so the STOMP agent runs without it
if configuration.consumer_protocol == "amqp":
    from postprocessing.amqp_consumer import AmqpConsumer as Consumer
else:
    from postprocessing.Consumer import Consumer

logging.info("Starting post-processing listener %s", importlib.metadata.version("postprocessing"))
configuration.log_configuration()

consumer = Consumer(configuration)
consumer.listen_and_wait(0.01)
