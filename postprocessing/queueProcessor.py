#!/usr/bin/env python
"""
    Post-processing agent start script
    
    @copyright: 2014 Oak Ridge National Laboratory
"""
import logging, json, sys, os

CONFIG_FILE = '/etc/autoreduce/post_processing.conf'
CONFIG_FILE_ALTERNATE = '/sw/fermi/autoreduce/postprocessing/configuration/post_processing.conf'

# Make sure we have a configuration file to read
config_file = CONFIG_FILE
if os.access(config_file, os.R_OK) == False:
    config_file = CONFIG_FILE_ALTERNATE
    if os.access(config_file, os.R_OK) == False:
        raise RuntimeError, "Configuration file doesn't exist or is not readable: %s" % CONFIG_FILE

cfg = open(config_file, 'r')
json_encoded = cfg.read()
config = json.loads(json_encoded)
sw_dir = config['sw_dir'] if 'sw_dir' in config else '/opt/postprocessing'

sys.path.insert(0, sw_dir)

import postprocessing
# The configuration includes setting up logging, which should be done first
from postprocessing.Configuration import read_configuration
configuration = read_configuration(config_file)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s/%(process)d %(message)s",
    filename=configuration.log_file,
    filemode='a'
)

from postprocessing.Consumer import Consumer
from twisted.internet import reactor

logging.info("Starting post-processing listener %s" % postprocessing.__version__)
configuration.log_configuration()

consumer = Consumer(configuration)
consumer.heartbeat()
consumer.run()
reactor.run()
