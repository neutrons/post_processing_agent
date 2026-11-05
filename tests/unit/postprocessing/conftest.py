# package imports
from postprocessing.Configuration import Configuration

# third-party imports
import pytest

# standard imports
import json

PROCESSORS = [
    "oncat_processor.ONCatProcessor",
    "oncat_reduced_processor.ONCatProcessor",
    "reduction_processor.ReductionProcessor",
]


@pytest.fixture
def make_config(tmp_path):
    def _make_config(**overrides):
        config_data = {
            "failover_uri": "failover:(tcp://localhost:61613)",
            "brokers": [["broker1", 61613], ["broker2", 61613]],
            "amq_user": "user",
            "amq_pwd": "secret",
            "sw_dir": "/opt/postprocessing",
            "postprocess_error": "POSTPROCESS.ERROR",
            "reduction_started": "REDUCTION.STARTED",
            "reduction_complete": "REDUCTION.COMPLETE",
            "reduction_error": "REDUCTION.ERROR",
            "reduction_disabled": "REDUCTION.DISABLED",
            "heart_beat": "/topic/SNS.COMMON.STATUS.AUTOREDUCE.0",
            "task_script_queue_arg": "-q",
            "task_script_data_arg": "-d",
            "processors": PROCESSORS,
        }
        config_data.update(overrides)
        config_file = tmp_path / "post_processing.conf"
        config_file.write_text(json.dumps(config_data))
        return Configuration(config_file.as_posix())

    return _make_config
