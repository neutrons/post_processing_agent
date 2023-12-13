from .base_processor import BaseProcessor
from postprocessing import reduction_script_writer


import logging
import sys


class CreateReductionScriptProcessor(BaseProcessor):
    _message_queue = "/queue/REDUCTION.CREATE_SCRIPT"

    def __init__(self, data, conf, send_function):
        """
        Initialize the processor
        @param data: data dictionary from the incoming message
        @param conf: configuration object
        @param send_function: function to call to send AMQ messages
        """
        super().__init__(data, conf, send_function)

    def __call__(self):
        """
        Create a new reduction script from a template
        """
        try:
            writer = reduction_script_writer.ScriptWriter(self.instrument)
            writer.process_request(
                self.data, configuration=self.configuration, send_function=self.send
            )
        except:  # noqa: E722
            logging.error(f"create_reduction_script: {sys.exc_info()[1]}")

    def _process_data(self, data):
        """
        Retrieve run information from the data dictionary
        provided with an incoming message.
        @param data: data dictionary
        """

        if "instrument" in data:
            self.instrument = str(data["instrument"]).upper()
        else:
            raise ValueError("Instrument is missing")

        if "use_default" in data:
            self.use_default = data["use_default"]
        else:
            raise ValueError("use_default is missing")

        if "template_data" in data:
            self.template_data = data["template_data"]
        else:
            raise ValueError("template_data is missing")
