# Post Processing Agent - Developer Documentation

## Tasks and queues

There are four tasks handled by the Post Processing Agent:

1. Catalog raw data
2. Reduce data
3. Catalog reduced data
4. Create reduction script

The four tasks each correspond to one ActiveMQ message broker queue that the Post Processing Agent subscribes to.

### Task configuration

The user can configure the active post processors using the parameter `"processors"`. The Post
Processing Agent subscribes to the queues for the registered post processors. The queue names are hard coded
in their respective post processor classes.

| Configuration parameter | Description | Default value |
| ----------------------- | --- | ------------- |
| `"processors"` | List of post-processors to register | `["oncat_processor.ONCatProcessor", "oncat_reduced_processor.ONCatProcessor", "create_reduction_script_processor.CreateReductionScriptProcessor", "reduction_processor.ReductionProcessor"]` |

## Starting the Post Processing Agent

The Post Processing Agent is an ActiveMQ client, which is started by running

    python <installation folder>/queueProcessor.py

Upon startup, the Post Processing Agent creates a connection to the ActiveMQ message broker and
subscribes to the required queues, as described in [Tasks and queues](#tasks-and-queues).

#### Related configuration parameters

| Configuration parameter | Description                                                                                                 | Default value |
| ----------------------- |-------------------------------------------------------------------------------------------------------------| ------------- |
| `"brokers"` | List of tuples containing host name and port of ActiveMQ broker(s), for example: `[("localhost", 61613)]` |  |
| `"amq_user"` | Message broker username                                                                                     |
| `"amq_pwd"` | Message broker password                                                                                     |
| `"log_file"` | Path to the log file                                                                                        | `post_processing.log` |
| `"heart_beat"` | Topic the agent will send heartbeats to                                                                     | `/topic/SNS.COMMON.STATUS.AUTOREDUCE.0` |
| `"heartbeat_ping"` | Topic the agent will subscribe to for ping requests                                                         | `/topic/SNS.COMMON.STATUS.PING` |

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
| `"brokers"` | List of tuples containing host name and port of ActiveMQ broker(s), for example: `[("localhost", 61613)]` |  |
| `"amq_user"` | Message broker username |
| `"amq_pwd"` | Message broker password |
| `"exceptions"` | List of exceptions (exception messages) that are not treated as errors | |

## Tasks handled by Post Processing Agent

This section describes the four tasks handled by the post processing agent: reduce data,
create reduction script, catalog raw data and catalog reduced data.

### Reduce data

#### Related configuration parameters

| Configuration parameter | Description | Default value |
| ----------------------- | ------ | ------------- |
| `"reduction_started"` | Topic for status message | |
| `"reduction_complete"` | Topic for status message | |
| `"reduction_error"` | Topic for status message | |
| `"reduction_disabled"` | Topic for status message | |
| `"python_exec"` | Python executable used to run the reduction script | `python` |

#### Example message

Queue name: `REDUCTION.DATA_READY`.

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
| `"service_status"` | Topic for status messages related to creating a reduction script | `/topic/SNS.${instrument}.STATUS.POSTPROCESS` |

#### Example message

Queue name: `REDUCTION.CREATE_SCRIPT`.

Example message using default parameters in the template:

    {
       'instrument': 'EQSANS',
       'use_default': True
    }

Example message with custom parameter values:

    {
      'instrument': 'SEQ',
      'use_default': False,
      'template_data': { dictionary of template arguments }
    }

### Catalog raw data

Queue name: `CATALOG.ONCAT.DATA_READY`.

#### Related configuration parameters

| Configuration parameter | Description | Default value |
| ----------------------- | --- | ------------- |
| `"python_exec"` | Python executable used to run the ONCat ingest script | `python` |

### Catalog reduced data

Queue name: `REDUCTION_CATALOG.DATA_READY`.

#### Related configuration parameters

| Configuration parameter | Description | Default value |
| ----------------------- | --- | ------------- |
| `"python_exec"` | Python executable used to run the ONCat reduced ingest script | `python` |
