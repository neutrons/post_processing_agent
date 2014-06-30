#!/usr/bin/env python
"""
    Post-processing agent start script
    
    @copyright: 2014 Oak Ridge National Laboratory
"""
import logging, json, sys, os
import postprocessing
# The configuration includes setting up logging, which should be done first
from postprocessing.Configuration import read_configuration, StreamToLogger
configuration = read_configuration()
sys.path.insert(0, configuration.sw_dir)

from postprocessing.Consumer import Consumer
from twisted.internet import reactor

logging.info("Starting post-processing listener %s" % postprocessing.__version__)
configuration.log_configuration()

consumer = Consumer(configuration)
consumer.heartbeat()
consumer.run()
reactor.run()
