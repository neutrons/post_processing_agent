import json

import pytest

from scripts import check_autoregister_config
from scripts.check_autoregister_config import facility_and_instrument, main

NEXUS_FILE = "/SNS/REF_L/IPTS-1/nexus/REF_L_12345.nxs.h5"


@pytest.fixture
def lookups():
    """The (facility, instrument) arguments of each config lookup"""
    return []


@pytest.fixture
def config_path(tmp_path, monkeypatch, lookups):
    """Point the standard config lookup at a file under tmp_path"""
    path = tmp_path / "config.yaml"

    def lookup(facility, instrument):
        lookups.append((facility, instrument))
        return str(path)

    monkeypatch.setattr(check_autoregister_config, "autoregister_config_path", lookup)
    return path


@pytest.fixture
def output_dir(tmp_path):
    path = tmp_path / "autoreduce"
    (path / "ort").mkdir(parents=True)
    for name in ["REF_L_12345_reduced.txt", "ort/REF_L_12345.ort", "REF_L_12346_reduced.txt"]:
        (path / name).touch()
    return path


def test_facility_and_instrument():
    assert facility_and_instrument("/sns/ref_l/IPTS-1/nexus/REF_L_12345.nxs.h5") == ("SNS", "REF_L")


def test_facility_and_instrument_too_short():
    with pytest.raises(ValueError):
        facility_and_instrument("/REF_L_12345.nxs.h5")


def test_main_lists_matching_files(config_path, lookups, output_dir, capsys):
    config_path.write_text(
        "file_patterns:\n"
        '  - "^{instrument}_{run_number}_reduced\\\\.txt$"\n'
        '  - "^ort/{instrument}_{run_number}\\\\.ort$"\n'
    )

    assert main([NEXUS_FILE, str(output_dir)]) == 0

    assert lookups == [("SNS", "REF_L")]
    out = capsys.readouterr().out
    assert "^REF_L_12345_reduced\\.txt$" in out
    reduced_data_info = json.loads(out[out.index("{") :])
    assert reduced_data_info == {
        "input_files": [NEXUS_FILE],
        "output_files": [
            {"location": str(output_dir / "REF_L_12345_reduced.txt")},
            {"location": str(output_dir / "ort" / "REF_L_12345.ort")},
        ],
    }


def test_main_no_matching_files(config_path, output_dir, capsys):
    config_path.write_text('file_patterns:\n  - "^{instrument}_{run_number}\\\\.dat$"\n')

    assert main([NEXUS_FILE, str(output_dir)]) == 1
    assert "no files" in capsys.readouterr().err


def test_main_missing_config(config_path, output_dir, capsys):
    assert main([NEXUS_FILE, str(output_dir)]) == 1
    assert "does not exist" in capsys.readouterr().err


def test_main_invalid_config(config_path, output_dir, capsys):
    config_path.write_text("other: 1\n")

    assert main([NEXUS_FILE, str(output_dir)]) == 1
    assert "does not define a list of file_patterns" in capsys.readouterr().err


def test_main_missing_output_dir(config_path, tmp_path, capsys):
    assert main([NEXUS_FILE, str(tmp_path / "missing")]) == 1
    assert "output directory" in capsys.readouterr().err


def test_main_not_nexus_file(config_path, output_dir, capsys):
    assert main(["/SNS/REF_L/IPTS-1/nexus/REF_L_12345.txt", str(output_dir)]) == 1
    assert "not a .nxs.h5 file" in capsys.readouterr().err
