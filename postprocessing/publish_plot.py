"""
    Utility functions to post plot data
"""
from __future__ import print_function
from postprocessing.Configuration import Configuration, CONFIG_FILE
import string
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def get_user(config_file=None):
    """
        Return username and password from config file
    """
    if config_file is None:
        config_file = CONFIG_FILE
    config = Configuration(config_file)
    return {'username': config.publisher_username,
            'password': config.publisher_password}

def publish_plot(instrument, run_number, files, config_file=None):
    """
        Files should be a dict of file contents to publish e.g. files={'file': div}
    """
    if config_file is None:
        config_file = CONFIG_FILE
    config = Configuration(config_file)

    url_template = string.Template(config.publish_url)
    url = url_template.substitute(instrument=instrument,
                                  run_number=str(run_number))
    request = requests.post(url, data={'username': config.publisher_username,
                                       'password': config.publisher_password},
                            files=files, verify=False)

    status_code = request.status_code
    if status_code != 200:
        raise RuntimeError("post returned %d" % status_code)
    return request
