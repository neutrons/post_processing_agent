Post Processing Agent
=====================

New version of the post-processing agent for automated reduction and cataloging.

For the old version of the post-processing agent, see https://github.com/mantidproject/autoreduce


Configuration
-------------
A configuration must be placed in `/etc/post_process_consumer.conf`.

The `configuration/post_process_consumer.conf.developement` file will make a good starting
point for configuration. Here are the entries to pay attention to:

    {
        "uri": "failover:(tcp://localhost:61613)?randomize=false,startupMaxReconnectAttempts=100,initialReconnectDelay=1000,maxReconnectDelay=5000,maxReconnectAttempts=-1",
        "amq_user": "",
        "amq_pwd": "",
        "amq_queues": ["/queue/FERMI_REDUCTION.DATA_READY", "/queue/CATALOG.DATA_READY", "/queue/REDUCTION_CATALOG.DATA_READY"],
        "reduction_data_ready": "FERMI_REDUCTION.DATA_READY",
    
        "sw_dir": "/opt/postprocessing",
        "python_dir": "/opt/postprocessing/postprocessing",
        "start_script": "python",
        "task_script": "PostProcessAdmin.py",
        "task_script_queue_arg": "-q",
        "task_script_data_arg": "-d",
        "log_file": "/opt/postprocessing/log/postprocessing.log",
    
        "mantid_release": "/opt/Mantid/bin",
        "mantid_nightly": "/opt/mantidnightly/bin",
        "mantid_unstable": "/opt/mantidunstable/bin",
    
        "communication_only": 1,
        "remote_execution": 0,
        "jobs_per_instrument": 2
    }

#### ActiveMQ settings

   - The ActiveMQ server settings must be set by replacing localhost above 
     by the proper address and the "amq_user" and "amq_pwd" must be filled out.
   - List the input queues in "amq_queues".
   - Change the input queue names as needed. For example, if the standard 
     "REDUCTION.DATA_READY" queue is replaced by special-purpose queue like 
     "FERMI_REDUCTION.DATA_READY", you should change the name of that queue 
     on the configuration file.
     
    - If "jobs_per_instrument" is set to an integer greater than zero, no more than
      that number of jobs will run on a given node for a given instrument.
      Set "jobs_per_instrument" to zero to turn this feature off.
      
      If this feature is used, you must add the following to activemq.xml:
      
            <broker xmlns="http://activemq.apache.org/schema/core" brokerName="localhost" ... schedulerSupport="true">
            
            ... 
            
            <plugins>
              <redeliveryPlugin fallbackToDeadLetter="true" sendToDlqIfMaxRetriesExceeded="true">
                <redeliveryPolicyMap>
                  <redeliveryPolicyMap>
                    <defaultEntry>
                      <redeliveryPolicy maximumRedeliveries="4" initialRedeliveryDelay="5000" redeliveryDelay="10000" />
                    </defaultEntry>
                  </redeliveryPolicyMap>
                </redeliveryPolicyMap>
              </redeliveryPlugin>
            </plugins>

#### Installation settings


#### Mantid settings

   - Don't forget to set your Mantid user's properties to send output logs to stdout:

        logging.channels.consoleChannel.class=StdoutChannel

#### Runtime settings


#### ICAT processing

   - You need to create the following files:

        configuration/icat4.cfg
        configuration/icatclient.properties
        configuration/post_process_consumer.conf

     They will be installed in /etc/autoreduce when running "make install".
     Examples in the configuration directory can be renamed and modified.
     
   - The ICAT processing in ingest_nexus.py and ingest_reduced.py were taken 
     from https://github.com/mantidproject/autoreduce with only minor modifications.
     
     
Installation
------------
The typical installation is designed to be similar to earlier versions of this service.
You can modify where the software is installed by modifying the prefix at the top of the Makefile.

   - Create the configuration files:

        cd configuration
        cp icat4_prod.cfg icat4.cfg
        cp icatclient.properties.developement icatclient.properties
        cp post_process_consumer.conf.developement post_process_consumer.conf

    Edit those two files according to your installation.

   - From the top source directory, run

        sudo make install

   - Alternatively, you can package your configured installation as an RPM:

        make rpm

   - To install on a compute node with limited access, you can also do the following:
   
        sudo make install/isolated
   
   - To run, simply call 
   
        python [installation path]/queueProcessor.py
        
   - Note: For python 2.6 and below, drop the argparse.py module under the "postprocessing" directory.
   
 
Running the tests
-----------------

The tests for this project are all written using `pytest <https://docs.pytest.org/en/latest>`_.

   $ python -m pytest tests/

This is one of the ways `pytest allows for selecting tests <https://docs.pytest.org/en/latest/usage.html#specifying-tests-selecting-tests>`_.
Specifying a directory or file will run all tests within that directory (recursively) or file.
Specifying a regular expression using ``-k`` will select all tests that match the regular expression independent of where they are defined


Running manual tests for mantidpython.py
----------------------------------------

Manual tests can be executed as


   $ python2 scripts/mantidpython.py /SNS/HYP/shared/auto_reduction/reduce_HYS.py [HYS nexus file] [Output Dir]

or

   $ python scripts/mantidpython.py tests/reduce_CONDA.py [Data file]  [Output dir]

as an example for how to activating a specific conda environment for reduction.
     
