"""
    Write reduction scripts using templates.

    An ActiveMQ message received from the workflow manager contains
    a dictionary of name-value pairs to fill an existing script template.

    The following files should be installed in the autoreduction
    directory of the instrument:

    /SNS/[instrument]/shared/autoreduce/reduce_[instrument].py.template
    /SNS/[instrument]/shared/autoreduce/reduce_[instrument]_default.py

    The reduce_[instrument]_default.py file can be any script (not a template)
    that can be used as a default script to revert to in order to bypass
    the template system.

    The dictionary is of the following form:

    { 'instrument': 'SEQ',
      'use_default': False,
      'template_data': { dictionary of template arguments }
    }

    If 'use_default' is set to True, the 'template_data' will be
    ignored and the reduce_[instrument]_default.py file will be copied
    to reduce_[instrument].py.

    The service sends updates and errors to ActiveMQ
    (by default /topic/SNS.${instrument}.STATUS.POSTPROCESS)

    @copyright: 2014 Oak Ridge National Laboratory
"""

# standard imports
import json
import logging
import os
import re
import sys
import shutil
import string
import time
import urllib


class ScriptWriter(object):
    """
        Script writer class
    """
    # Directory containing the templates
    _script_name = "reduce_%s.py"
    # Name of the template file
    _template_name = "reduce_%s.py.template"
    # Name of the default reduction script
    _default_script_name = "reduce_%s_default.py"
    # Path of the autoreduction directory
    _autoreduction_dir = "/SNS/%s/shared/autoreduce"
    # Log file
    _log_file = "reduction_parameters.txt"

    def __init__(self, instrument):
        """
            Initialize and find the appropriate template file
            @param str instrument: instrument name
        """
        # Instrument name
        self.instrument = instrument
        # Reduction script name
        self.script_name = self._script_name % instrument.upper()
        # Name of the reduction template file
        self.template_name = self._template_name % instrument.upper()
        # Default reduction script name
        self.default_script_name = self._default_script_name % instrument.upper()
        # Content of the template
        self._template_content = None
        # Shared autoredudction directory
        self.autoreduction_dir = self._autoreduction_dir % instrument.upper()

    @property
    def _template_path(self):
        r"""Absolute path to reduction script"""
        return os.path.join(self.autoreduction_dir, self.template_name)

    @property
    def log_file(self):
        r"""Absolute path to the log file"""
        return os.path.join(self.autoreduction_dir, self._log_file)

    def get_arguments(self):
        """
            Return a list of template arguments
        """
        if self._template_content is None:
            self._template_content = open(self._template_path).read()

        tag_list = re.findall(r"\$(\w+)", self._template_content)
        tag_list.extend(re.findall(r"\${(\w+)}", self._template_content))
        return set(tag_list)

    def check_arguments(self, **template_args):
        """
            Check that all arguments provided in the input dictionary
            are sufficient to fill the template. Otherwise raise an exception.

            @param template_args: dictionary of arguments to fill the template
        """
        missing_args = []
        for item in self.get_arguments():
            if item not in template_args:
                missing_args.append(item)
        if len(missing_args) > 0:
            raise KeyError("Template arguments missing: %s" % str(missing_args))

    def write_script(self, **template_args):
        r"""Write the script using a template
        @param dict template_args: dictionary of arguments to fill the template
        @raises KeyError: if missing template arguments
        """
        self.check_arguments(**template_args)
        # If we use a template, make sure we load it first
        if self._template_content is None:
            self._template_content = open(self._template_path).read()
        # Replace the dictionary entries
        template = string.Template(self._template_content)
        script = template.substitute(**template_args)
        # Write the script
        if os.path.isdir(self.autoreduction_dir):
            script_file = open(os.path.join(self.autoreduction_dir, self.script_name), 'w')
            script_file.write(script)
            script_file.close()
        else:
            raise RuntimeError("Script directory does not exist: %s" % self.autoreduction_dir)

    def log_entry(self, **template_args):
        r"""Log the template parameters in the reduction directory.
        @details The log file is tab delimited.
        @param dic template_args: arguments to fill the template
        """
        try:
            template_keys = sorted(template_args.keys())
            template_values = [string.replace(str(template_args[k]), '\n', '; ') for k in template_keys]
            template_keys.insert(0, "Time")
            template_values.insert(0, "%s" % time.ctime())
            log_entry = ""
            # If the file doesn't exist, create it with a header line
            if not os.path.isfile(self.log_file):
                log_entry = '\t '.join(template_keys)
                log_entry += '\n'
            log_entry += '\t '.join(template_values)
            log_entry += '\n'
            log_file = open(self.log_file, 'a')
            log_file.write(log_entry)
            log_file.close()
        except Exception:
            logging.error("ScriptWriter: Could not write log entry for %s: %s" % (self.script_name, sys.exc_value))

    def process_request(self, request_data, configuration, send_function):
        r"""Process a request to write a new reduction script from an existing template
        @param dict request_data: request dictionary with template arguments
        @param configuration: Configuration object
        @param send_function: function to call to send an AMQ message
        """
        if 'instrument' not in request_data:
            logging.error("Script writer request: missing instrument")
            return
        # Determine the ActiveMQ topic to use for reporting
        amq_template = string.Template(configuration.service_status)
        amq_topic = amq_template.substitute(instrument=request_data['instrument'])
        amq_data = {'src_id': 'postprocessing'}
        try:
            # Verify that the dictionary of template arguments is complete
            if "template_data" in request_data:
                template_data = {}
                for key, value in request_data["template_data"].items():
                    if isinstance(value, basestring):
                        # replace '+' sign with a blank space ('+' -> ' ')
                        # replace %xx escapes by their single-character equivalent
                        template_data[key] = urllib.unquote_plus(value)
                    else:
                        template_data[key] = value

                # Check for a request to use the default script
                if 'use_default' in request_data and request_data['use_default'] is True:
                    # Copy the default script to the production script
                    default_script_path = os.path.join(self.autoreduction_dir, self.default_script_name)
                    if not os.path.isfile(default_script_path):
                        raise RuntimeError("ScriptWriter: Could not find script %s" % self.default_script_name)
                    shutil.copy(default_script_path,
                                os.path.join(self.autoreduction_dir, self.script_name))
                    amq_data['status'] = "Installed default %s script" % request_data['instrument']
                else:
                    # Verify that the template file exists
                    if not os.path.isfile(self._template_path):
                        raise RuntimeError("ScriptWriter: Could not find template %s" % self.template_name)

                    self.check_arguments(**template_data)
                    self.write_script(**template_data)
                    amq_data['status'] = "Created %s reduction script" % request_data['instrument']
                self.log_entry(**template_data)
            else:
                logging.error("Script writer: missing template data")
                amq_data['status'] = "Missing %s reduction template" % request_data['instrument']
        except RuntimeError:
            logging.error("Script writer: %s" % sys.exc_value)
            amq_data['status'] = "Error creating %s reduction script: %s" % (request_data['instrument'],
                                                                             sys.exc_value)
        send_function(amq_topic, json.dumps(amq_data))
