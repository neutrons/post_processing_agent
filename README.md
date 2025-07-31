Post Processing Agent
=====================

New version of the post-processing agent for automated reduction and cataloging.

For the old version of the post-processing agent, see https://github.com/mantidproject/autoreduce


[![codecov](https://codecov.io/github/neutrons/post_processing_agent/graph/badge.svg?token=OYoTSnbmEL)](https://codecov.io/github/neutrons/post_processing_agent)

Configuration
-------------
A configuration must be placed in `/etc/autoreduce/post_processing.conf`.

The `configuration/post_process_consumer.conf.development` file will make a good starting
point for configuration. Here are the entries to pay attention to:

    {
        "brokers": [("localhost", 61613)],
        "amq_user": "",
        "amq_pwd": "",
        "sw_dir": "/opt/postprocessing",
        "python_dir": "/opt/postprocessing/postprocessing",
        "start_script": "python",
        "task_script": "PostProcessAdmin.py",
        "task_script_queue_arg": "-q",
        "task_script_data_arg": "-d",
        "log_file": "/opt/postprocessing/log/postprocessing.log",

        "communication_only": 1,
        "jobs_per_instrument": 2
    }

#### ActiveMQ settings

   - The ActiveMQ server settings must be set by replacing `localhost` above
     by the proper address and the `"amq_user"` and `"amq_pwd"` must be filled out.

   - If `"jobs_per_instrument"` is set to an integer greater than zero, no more than
      that number of jobs will run on a given node for a given instrument.
      Set `"jobs_per_instrument"` to zero to turn this feature off.

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

#### Task time and memory limits

Post-Processing Agent will terminate a post-processing task that exceeds either the time limit or
memory usage limit. The limits and the time interval between checks are configurable in the
configuration file. The same time interval between checks applies to both the time limit and memory
usage limit.

    {
        "system_mem_limit_perc": 70.0,
        "mem_check_interval_sec": 0.2,
        "task_time_limit_minutes": 60.0
    }

#### Installation settings


#### Mantid settings

   - Don't forget to set your Mantid user's properties to send output logs to stdout:

    logging.channels.consoleChannel.class=StdoutChannel

#### Runtime settings

#### ONCat processing

The post processing agent handles cataloging raw and reduced data files in ONCat https://oncat.ornl.gov/ by
calling scripts hosted on the analysis cluster.


Installation
------------

Create the configuration files and edit according to your installation.

    cd configuration
    cp post_process_consumer.conf.developement /etc/autoreduce/post_processing.conf

To run, simply call

    python [installation path]/queueProcessor.py

Development environment
-----------------------

The conda environment for running `queueProcessor.py` and tests locally is defined in `environment.yml`. Create and activate the conda environment for development.

    conda env create  # or: mamba env create
    conda activate post_processing_agent

### Local development with plot_publisher

For developers working on both `post_processing_agent` and `plot_publisher` simultaneously, you may want to use an editable install of `plot_publisher`. After setting up both repositories locally:

1. Clone both repositories as siblings:
   ```
   /your/workspace/
   ├── post_processing_agent/
   └── plot_publisher/
   ```

2. Modify `environment.yml` to use the local editable install:
   ```yaml
   - pip:
     - --editable ../plot_publisher
   ```

3. Recreate the conda environment:
   ```bash
   conda env remove -n post_processing_agent
   conda env create
   ```

Note: The default configuration installs `plot_publisher` from GitHub to ensure CI compatibility.

Running the tests
-----------------

The tests for this project are all written using [pytest](https://docs.pytest.org/en/latest>).

    python -m pytest tests/

This is one of the ways [pytest allows for selecting tests](https://docs.pytest.org/en/latest/usage.html#specifying-tests-selecting-tests).
Specifying a directory or file will run all tests within that directory (recursively) or file.
Specifying a regular expression using ``-k`` will select all tests that match the regular expression independent of where they are defined

### Integration tests

The integration tests requires activemq and the queueprocessor to be running, they will be automatically skipped if activemq is not running. This can be achieved using the docker-compose file provided,

    docker compose -f tests/integration/docker-compose.yml up -d --build

then run

    python -m pytest tests/integration

after which you can stop docker with

    docker compose -f tests/integration/docker-compose.yml down


Running manual tests for mantidpython.py
----------------------------------------

Manual tests can be executed as

    $ python scripts/mantidpython.py /SNS/HYP/shared/auto_reduction/reduce_HYS.py [HYS nexus file] [Output Dir]

or

    $ python scripts/mantidpython.py tests/reduce_CONDA.py [Data file]  [Output dir]

as an example for how to activate a specific conda environment for reduction.


Running with docker
-------------------

```shell
docker build --tag postprocessing .
docker run --network host postprocessing
```

Creating a new release
----------------------
1. Update the version number in [SPECS/postprocessing.spec](SPECS/postprocessing.spec) and
   [pyproject.toml](pyproject.toml) and commit the change to `main`.
2. Create a new tag and create a release from the tag (see the three dots menu
   for the tag at https://github.com/neutrons/post_processing_agent/tags).
3. Build the RPM using `make build/rpm` and upload the `.rpm` and `.srpm` files as release
   assets to the GitHub release page.
