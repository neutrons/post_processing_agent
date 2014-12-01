"""
    Test Processor
    
    @copyright: 2014 Oak Ridge National Laboratory
"""
from base_processor import BaseProcessor
import json

class TestProcessor(BaseProcessor):
    
    ## Input queue
    _message_queue = "/queue/REDUCTION.TESTPROCESSOR.DATA_READY"
    
    def __init__(self, data, conf, send_function):
        """
            Initialize the processor
            
            @param data: data dictionary from the incoming message
            @param conf: configuration object
            @param send_function: function to call to send AMQ messages
        """
        super(TestProcessor, self).__init__(data, conf, send_function) 
    
    def __call__(self):
        """
            Just send back acknowledgment messages
        """
        self.send('/queue/'+self.configuration.reduction_started, json.dumps(self.data))
        self.send('/queue/'+self.configuration.reduction_complete, json.dumps(self.data))

    def send(self, destination, data):
        if self._send_function is not None:
            self._send_function(destination, data)
        else:
            print destination, data