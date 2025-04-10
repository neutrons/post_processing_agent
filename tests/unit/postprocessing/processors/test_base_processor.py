import pytest
from unittest.mock import Mock, patch

from postprocessing.processors.base_processor import BaseProcessor


test_message = {
    "run_number": "30892",
    "instrument": "EQSANS",
    "ipts": "IPTS-10674",
    "facility": "SNS",
    "data_file": "/SNS/EQSANS/IPTS-10674/0/30892/NeXus/EQSANS_30892_event.nxs",
}


@pytest.mark.parametrize(
    "exception, error_msg",
    [
        (FileNotFoundError, "Data file not found"),
        (PermissionError, "Data file permission denied"),
        (OSError, "Data file open error"),
        (IsADirectoryError, "Data file open error"),
    ],
)
def test_data_file_open_errors(exception, error_msg):
    data = test_message
    mock_conf = Mock()
    mock_send_function = Mock()
    with patch(
        "postprocessing.processors.base_processor.open",
        create=True,
        side_effect=exception,
    ):
        with pytest.raises(ValueError) as exc_info:
            BaseProcessor(data, mock_conf, mock_send_function)
    assert error_msg in str(exc_info.value)
