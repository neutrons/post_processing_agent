Post Processing Agent
=====================

New version of the post-processing agent for automated reduction and cataloging.

For the current version of the post-processing agent, see https://github.com/mantidproject/autoreduce


Configuration
-------------
A configuration must be placed in `/etc/post_process_consumer.conf`.

The `configuration/post_process_consumer.conf.developement` file will make a good starting
point for configuration. Here are the entries to pay attention to:


```sh
{
    "uri": "failover:(tcp://localhost:61613)?randomize=false,startupMaxReconnectAttempts=100,initialReconnectDelay=1000,maxReconnectDelay=5000,maxReconnectAttempts=-1",
    "amq_user": "",
    "amq_pwd": "",
    "amq_queues": ["/queue/FERMI_REDUCTION.DATA_READY", "/queue/CATALOG.DATA_READY", "/queue/REDUCTION_CATALOG.DATA_READY"],
    "reduction_data_ready": "FERMI_REDUCTION.DATA_READY",

    "python_dir": "/opt/postprocessing/postprocessing",
    "script_dir": "/opt/postprocessing/scripts",
    "start_script": "python",
    "task_script": "PostProcessAdmin.py",
    "task_script_queue_arg": "-q",
    "task_script_data_arg": "-d",
    "log_file": "/opt/postprocessing/log/postprocessing.log",

    "mantid_release": "/opt/Mantid/bin",
    "mantid_nightly": "/opt/mantidnightly/bin",
    "mantid_unstable": "/opt/mantidunstable/bin",

    "dev_output_dir": "/tmp/",
    "communication_only": 1,
    "max_procs": 5,
    "remote_execution": 0
}
```

#### ActiveMQ settings

   - The ActiveMQ server settings must be set by replacing localhost above 
     by the proper address and the "amq_user" and "amq_pwd" must be filled out.
   - List the input queues in "amq_queues".
   - Change the input queue names as needed. For example, if the standard 
     "REDUCTION.DATA_READY" queue is replaced by special-purpose queue like 
     "FERMI_REDUCTION.DATA_READY", you should change the name of that queue 
     on the configuration file.

#### Installation settings

#### Mantid settings

#### Runtime settings