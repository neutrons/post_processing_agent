#!/usr/bin/env python
"""
    Post-processing agent start script

    @copyright: 2014 Oak Ridge National Laboratory
"""
import logging
import postprocessing

# The configuration includes setting up logging, which should be done first
from postprocessing.Configuration import read_configuration

configuration = read_configuration()

from postprocessing.Consumer import Consumer
from twisted.internet import reactor, task

logging.info("Starting post-processing listener %s", postprocessing.__version__)
configuration.log_configuration()

consumer = Consumer(configuration)
heartbeat = task.LoopingCall(consumer.heartbeat)
heartbeat.start(30.0)
consumer.run()
reactor.run()
