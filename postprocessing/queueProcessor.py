#!/usr/bin/env python
"""
    Post-processing agent start script
    
    @copyright: 2014 Oak Ridge National Laboratory
"""
import logging, json, sys, os

# Get the location of the software installation
if sys.argv[1] is None:
    CONFIG_FILE = '/etc/autoreduce/post_process_consumer.conf'
else:
    CONFIG_FILE = sys.argv[1]

if os.access(CONFIG_FILE, os.R_OK) == False:
    raise RuntimeError, "Configuration file doesn't exist or is not readable."

cfg = open(CONFIG_FILE, 'r')
json_encoded = cfg.read()
config = json.loads(json_encoded)
sw_dir = config['sw_dir'] if 'sw_dir' in config else '/opt/postprocessing'

sys.path.insert(0, sw_dir)

import postprocessing
# The configuration includes setting up logging, which should be done first
from postprocessing.Configuration import configuration
from postprocessing.Consumer import Consumer
from twisted.internet import reactor

logging.info("Starting post-processing listener %s" % postprocessing.__version__)
Consumer(configuration).run()
reactor.run()
