import json
import os

import pytest

from postprocessing.processors.calvera_processor import CalveraReducedProcessor


@pytest.fixture
def processor(tmp_path, monkeypatch):
    """A reduced processor whose raw file, output directory and instrument config live under tmp_path"""
    raw_file = tmp_path / "nexus" / "REF_L_12345.nxs.h5"
    raw_file.parent.mkdir()
    raw_file.touch()
    data = {
        "data_file": str(raw_file),
        "facility": "SNS",
        "instrument": "REF_L",
        "ipts": "IPTS-1",
        "run_number": "12345",
    }
    proc = CalveraReducedProcessor(data, conf=None, send_function=None)
    proc.output_dir = str(tmp_path / "autoreduce")
    (tmp_path / "autoreduce").mkdir()
    monkeypatch.setattr(proc, "_autoregister_config_path", lambda: str(tmp_path / "config.yaml"))
    return proc


def write_config(processor, contents):
    with open(processor._autoregister_config_path(), "w") as f:
        f.write(contents)


def touch_output_files(processor, *relative_paths):
    for relative_path in relative_paths:
        path = os.path.join(processor.output_dir, relative_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w").close()


def test_autoregister_config_path():
    proc = CalveraReducedProcessor.__new__(CalveraReducedProcessor)
    proc.facility = "SNS"
    proc.instrument = "REF_L"
    assert proc._autoregister_config_path() == "/SNS/REF_L/shared/tiled-autoregister-config.yaml"


def test_reduction_json_takes_precedence(processor):
    reduction_info = {"input_files": ["a"], "output_files": [{"location": "b"}]}
    with open(f"{processor.output_dir}/REF_L_12345.json", "w") as f:
        json.dump(reduction_info, f)
    write_config(processor, 'file_patterns:\n  - "^.*$"\n')

    assert processor._prepare_send_data()["reduced_data_info"] == reduction_info


def test_files_from_config(processor):
    write_config(
        processor,
        "file_patterns:\n"
        '  - "^{instrument}_{run_number}_reduced\\\\.txt$"\n'
        '  - "^ort/{instrument}_{run_number}\\\\.ort$"\n',
    )
    touch_output_files(
        processor,
        "REF_L_12345_reduced.txt",
        "ort/REF_L_12345.ort",
        "REF_L_123456_reduced.txt",  # other run number
        "REF_L_12345_reduced.dat",  # no matching pattern
        "REF_L_12345.ort",  # wrong subdirectory
    )

    to_send = processor._prepare_send_data()

    assert to_send["type"] == "reduced"
    assert to_send["reduced_data_info"] == {
        "input_files": [processor.data_file],
        "output_files": [
            {"location": f"{processor.output_dir}/REF_L_12345_reduced.txt"},
            {"location": f"{processor.output_dir}/ort/REF_L_12345.ort"},
        ],
    }


def test_pattern_keeps_regex_quantifiers(processor):
    write_config(processor, 'file_patterns:\n  - "^{instrument}_{run_number}_\\\\d{2}\\\\.dat$"\n')
    touch_output_files(processor, "REF_L_12345_01.dat", "REF_L_12345_001.dat")

    output_files = processor._prepare_send_data()["reduced_data_info"]["output_files"]

    assert output_files == [{"location": f"{processor.output_dir}/REF_L_12345_01.dat"}]


def test_no_json_and_no_config(processor):
    with pytest.raises(Exception, match="Cannot read reduced data info"):
        processor._prepare_send_data()


def test_config_matches_no_files(processor):
    write_config(processor, 'file_patterns:\n  - "^{instrument}_{run_number}\\\\.txt$"\n')
    touch_output_files(processor, "REF_L_99999.txt")

    with pytest.raises(Exception, match="Cannot read reduced data info"):
        processor._prepare_send_data()


@pytest.mark.parametrize("contents", ["", "file_patterns: []\n", "file_patterns: foo\n", "other: 1\n"])
def test_config_without_file_patterns(processor, contents):
    write_config(processor, contents)

    with pytest.raises(ValueError, match="does not define a list of file_patterns"):
        processor._prepare_send_data()
