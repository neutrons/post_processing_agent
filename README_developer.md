# Post Processing Agent - Developer Documentation

## Tasks and queues

There are four tasks handled by the post processing agent:

1. Catalog raw data
2. Reduce data
3. Catalog reduced data
4. Create reduction script

The four tasks each correspond to one message queue in the ActiveMQ message broker. For historical reasons,
there are two ways the queue - task connection is made, which will be described in the following two sections.

### Fixed tasks with configurable queue names

The message queues for tasks 2. and 4. are configured in the postprocessor configuration file.

| Configuration parameter | Description | Default value |
| ----------------------- | --- | ------------- |
| `"amq_queues"` | List of queues the agent will subscribe to |
| `"reduction_data_ready"` | Messages from this queue will be handled by the `reduce` method | `REDUCTION.DATA_READY` |
| `"create_reduction_script"` | Messages from this queue will be handled by the `create_reduction_script` method | `REDUCTION.CREATE_SCRIPT` |

The Post Processing Agent subscribes to the queues in `"amq_queues"`. When a message is received,
the handler of the message is determined by checking if the queue matches one of the queues
`"reduction_data_ready"` or `"create_reduction_script"`.

### Optional tasks with fixed queue names

The message queues for tasks 1. and 3. are hard coded in their respective post processor classes.
Instead, the user configures the active post processors using the parameter `"processors"` and the Post
Processing Agent subscribes to the queues for the registered post processors.

| Configuration parameter | Description | Default value |
| ----------------------- | --- | ------------- |
| `"processors"` | List of post-processors to register | `[]`, but should probably be `["oncat_processor.ONCatProcessor", "oncat_reduced_processor.ONCatProcessor"]` |

## Starting the Post Processing Agent

The Post Processing Agent is an ActiveMQ client, which is started by running

    python <installation folder>/queueProcessor.py

Upon startup, the Post Processing Agent creates a connection to the ActiveMQ message broker and
subscribes to the required queues, as described in [Tasks and queues](#tasks-and-queues).

#### Related configuration parameters

| Configuration parameter | Description | Default value |
| ----------------------- | --- | ------------- |
| `"failover_uri"` | URI of the message broker (the first argument to `StompConfig`) | `tcp://amqbroker.sns.gov:61613` |
| `"amq_queues"` | List of queues the agent will subscribe to |
| `"amq_user"` | Message broker username |
| `"amq_pwd"` | Message broker password |
| `"log_file"` | Path to the log file | `post_processing.log` |
| `"heart_beat"` | Topic the agent will send heartbeats to | `/topic/SNS.COMMON.STATUS.AUTOREDUCE.0` |
| `"heartbeat_ping"` | Topic the agent will subscribe to for ping requests | `/topic/SNS.COMMON.STATUS.PING` |

## Consuming a message

When a message is published to on one of the queues:
   1. `Consumer` checks how many subprocesses are running for that instrument and either
   accepts or rejects the message.
   2. If the message is accepted, `Consumer` starts a subprocess that runs the script
    `PostProcessAdmin.py`

#### Related configuration parameters

| Configuration parameter | Description | Default value |
| ----------------------- | ------------- | ---- |
| `"jobs_per_instrument"` | If > 0, the maximum number of concurrent jobs per instrument | 2 |
| `"python_dir"` | Path to `PostProcessorAdmin.py` | |
| `"start_script"` | Script runner | `python` |
| `"task_script"` | Script to pass the message payload to | `PostProcessorAdmin.py` |
| `"task_script_queue_arg"` | Flag passed to the task script before the message queue name | `-q` |
| `"task_script_data_arg"` | Flag passed to the task script before the message payload | `-d` |
| `"max_procs"` | Maximum number of concurrent processes | 5 |
| `"postprocess_error"` | If consuming the message fails (exception is raised), the message will be forwarded to this error topic | `POSTPROCESS.ERROR` |

## `PostProcessorAdmin` started by `Consumer`

The class `PostProcessorAdmin` routes the consumed message based on the queue name. See [Tasks and queues](#tasks-and-queues).

| Configuration parameter | Description | Default value |
| ----------------------- | --- | ------------- |
| `"failover_uri"` | URI of the message broker | `tcp://amqbroker.sns.gov:61613` |
| `"amq_user"` | Message broker username |
| `"amq_pwd"` | Message broker password |
| `"exceptions"` | List of exceptions (exception messages) that are not treated as errors | |
| `"reduction_data_ready"` | Messages from this queue will be handled by the `reduce` method | `REDUCTION.DATA_READY` |
| `"create_reduction_script"` | Messages from this queue will be handled by the `create_reduction_script` method | `REDUCTION.CREATE_SCRIPT` |

## Tasks handled by Post Processing Agent

This section describes the four tasks handled by the post processing agent: reduce data,
create reduction script, catalog raw data and catalog reduced data.

### Reduce data

#### Related configuration parameters

| Configuration parameter | Description | Default value |
| ----------------------- | ------ | ------------- |
| `"reduction_data_ready"` | Messages from this queue will be handled by the `reduce` method | `REDUCTION.DATA_READY` |
| `"reduction_started"` | Topic for status message | |
| `"reduction_complete"` | Topic for status message | |
| `"reduction_error"` | Topic for status message | |
| `"reduction_disabled"` | Topic for status message | |
| `"python_exec"` | Python executable used to run the reduction script | `python` |

#### Test message

Default ActiveMQ queue: `REDUCTION.DATA_READY`.

    {
      "information": "mac83808.sns.gov",
      "run_number": "30892",
      "instrument": "EQSANS",
      "ipts": "IPTS-10674",
      "facility": "SNS",
      "data_file": "/SNS/EQSANS/IPTS-10674/0/30892/NeXus/EQSANS_30892_event.nxs"
    }

### Create reduction script

#### Related configuration parameters

| Configuration parameter | Description | Default value |
| ----------------------- | ------ | ------------- |
| `"create_reduction_script"` | Messages from this queue will be handled by the `create_reduction_script` method | `REDUCTION.CREATE_SCRIPT` |
| `"service_status"` | Topic for status messages related to creating a reduction script | `/topic/SNS.${instrument}.STATUS.POSTPROCESS` |

#### Test message

Default ActiveMQ queue: `REDUCTION.CREATE_SCRIPT`.

Test message using default parameters in the template:

    {
       'instrument': 'EQSANS',
       'use_default': True
    }

Test message with custom parameter values:

    {
      'instrument': 'SEQ',
      'use_default': False,
      'template_data': { dictionary of template arguments }
    }

### Catalog raw data

Listens to queue: `CATALOG.ONCAT.DATA_READY`. The queue name is hard coded and
automatically subscribed to if the configuration parameter `"processors"`
contains `"oncat_processor.ONCatProcessor"`.

#### Related configuration parameters

| Configuration parameter | Description | Default value |
| ----------------------- | --- | ------------- |
| `"processors"` | List of post-processors to register | `[]`, but should probably be `["oncat_processor.ONCatProcessor", "oncat_reduced_processor.ONCatProcessor"]` |
| `"python_exec"` | Python executable used to run the ONCat ingest script | `python` |

### Catalog reduced data

Listens to queue: `REDUCTION_CATALOG.DATA_READY`. The queue name is hard coded and
automatically subscribed to if the configuration parameter `"processors"`
contains `"oncat_reduced_processor.ONCatProcessor"`.

#### Related configuration parameters

| Configuration parameter | Description | Default value |
| ----------------------- | --- | ------------- |
| `"processors"` | List of post-processors to register | `[]`, but should probably be `["oncat_processor.ONCatProcessor", "oncat_reduced_processor.ONCatProcessor"]` |
| `"python_exec"` | Python executable used to run the ONCat reduced ingest script | `python` |

## Testing Post Processing Agent locally

### To run a local ActiveMQ message broker

1. Download ActiveMQ from the website: https://activemq.apache.org/.
2. Install Java using `sudo apt install default-jdk`
3. Start the message broker using `apache-activemq-*.*.*/bin/activemq start`
4. Access the Apache ActiveMQ Console at ``http://localhost:8161/`` to add queues etc. (Default user/password is admin/admin.)
5. Purge pending messages using `activemq purge`
6. Stop the message broker using `activemq stop`

### To simulate incoming messages

With a local ActiveMQ message broker running, we can simulate messages from the workflow manager by publishing messages to the queues, either using the ActiveMQ Console or the `stompy.py` command-line client.

#### Use ActiveMQ Console

Open the Apache ActiveMQ Console at ``http://localhost:8161/`` (default user/password is admin/admin). Locate the queue and
the "Send To" operation, paste the JSON in the Message body and press "Send".

#### Use `stomp.py` command-line client

Install `stomp.py` and use its [command-line client](https://jasonrbriggs.github.io/stomp.py/commandline.html).

    $ python -m stomp -H localhost -P 61613
    > send /queue/REDUCTION.DATA_READY {"information":"mac83808.sns.gov", "run_number":"30892", "instrument":"EQSANS", "ipts":"IPTS-10674", "facility":"SNS", "data_file":"/Volumes/RAID/SNS/EQSANS/IPTS-10674/0/30892/NeXus/EQSANS_30892_event.nxs"}
