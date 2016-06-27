from __future__ import print_function
from Configuration import read_configuration
import requests
import string

PUBLISHER_USER_DEFAULT = 'admin'
PUBLISHER_PASS_DEFAULT  = 'adminadmin'
PUBLISHER_URL_TEMPLATE = "http://127.0.0.1:8000/plots/$instrument/$run_number/upload_plot_data/"

def getUser(config_file=None):
    try:
        config = read_configuration(config_file)
        return {'username':config.publisher_username,  # TODO
                'password':config.publisher_password}  # TODO
    except IOError:
        pass  # use hard coded defaults
    except RuntimeError:
        pass  # use hard coded defaults

    return {'username': PUBLISHER_USER_DEFAULT,
            'password': PUBLISHER_PASS_DEFAULT}

def publishPlots(instrument, run_number, files, config_file=None):
    """
    files should be a dict of file contents to publish e.g. files={'file':div}
    """
    url_template = string.Template(PUBLISHER_URL_TEMPLATE)
    url = url_template.substitute(instrument=instrument,
                                  run_number=str(run_number))
    request = requests.post(url, data=getUser(config_file),
                            files=files, verify=False)

    status_code = request.status_code
    if status_code != 200:
        raise RuntimeError("post returned %d" % status_code)

if __name__ == "__main__":
    print('getUser()', getUser())
    print('********************')
    publishPlots('DAS', 12345, {'file':'bob'})
