import pytest
import os
from scripts.mantidpython import generate_subprocess_command, get_conda_env


def test_get_conda_env():
    """testing for the conda environment extraction function"""
    # Test valid conda environment specifications
    assert get_conda_env("CONDA_ENV='sasview'") == "sasview"
    assert get_conda_env("CONDA_ENV='imaging'") == "imaging"
    assert get_conda_env("CONDA_ENV = 'jean'") == "jean"
    assert get_conda_env('CONDA_ENV="sans-dev"') == "sans-dev"
    assert get_conda_env("CONDA_ENV= 'reduction'") == "reduction"

    # Test lines that should not match
    assert get_conda_env("from mantid.simpleapi import ") is None
    assert get_conda_env('sys.path.append(os.path.join("/opt/Mantid/bin"))') is None
    assert get_conda_env("sys.path.insert(0,'/opt/Mantid/bin')") is None
    assert get_conda_env('sys.path.append("/opt/mantidnightly/bin")') is None
    assert get_conda_env("MANTID_VERSION='nightly'") is None
    assert get_conda_env("# CONDA_ENV='commented_out'") is None


def test_generate_subprocess_command_valid_conda():
    """Test generate_subprocess_command with valid conda environment"""
    # Create a temporary script with valid CONDA_ENV
    script_content = """CONDA_ENV = "test-env"
import sys
print("Hello world")
"""
    script_path = "/tmp/test_reduce_script.py"
    with open(script_path, "w") as f:
        f.write(script_content)

    try:
        cmd = generate_subprocess_command(script_path, ["input.nxs", "output/"], False)
        expected = ["/usr/bin/nsd-conda-wrap.sh", "test-env", "--classic", script_path, "input.nxs", "output/"]
        assert cmd == expected
    finally:
        if os.path.exists(script_path):
            os.remove(script_path)


def test_generate_subprocess_command_no_conda_env():
    """Test generate_subprocess_command fails when no CONDA_ENV is specified"""
    # Create a temporary script without CONDA_ENV
    script_content = """import sys
print("Hello world")
"""
    script_path = "/tmp/test_reduce_script_no_conda.py"
    with open(script_path, "w") as f:
        f.write(script_content)

    try:
        with pytest.raises(RuntimeError) as exc_info:
            generate_subprocess_command(script_path, ["input.nxs", "output/"], False)

        assert "does not specify a CONDA_ENV" in str(exc_info.value)
        assert "conda environment must be specified" in str(exc_info.value)
    finally:
        if os.path.exists(script_path):
            os.remove(script_path)


def test_generate_subprocess_command_multiple_conda_envs():
    """Test generate_subprocess_command fails when multiple CONDA_ENVs are specified"""
    # Create a temporary script with multiple CONDA_ENV specifications
    script_content = """CONDA_ENV = "first-env"
CONDA_ENV = "second-env"
import sys
print("Hello world")
"""
    script_path = "/tmp/test_reduce_script_multiple_conda.py"
    with open(script_path, "w") as f:
        f.write(script_content)

    try:
        with pytest.raises(RuntimeError) as exc_info:
            generate_subprocess_command(script_path, ["input.nxs", "output/"], False)

        assert "specifies multiple conda environments" in str(exc_info.value)
        assert "first-env" in str(exc_info.value)
        assert "second-env" in str(exc_info.value)
    finally:
        if os.path.exists(script_path):
            os.remove(script_path)


@pytest.mark.parametrize(
    "auto_reduce_script, expected_conda_env",
    [
        ("tests/reduce_CONDA.py", "sans-dev"),
    ],
    ids=("conda",),
)
def test_conda_environment_extraction(auto_reduce_script, expected_conda_env):
    """Test that existing conda-based scripts work correctly"""
    # set up test cases
    auto_reduce_script = os.path.join(os.getcwd(), auto_reduce_script)
    nexus_file_name = "/SNS/INS/IPTS-1234/nexus/INS_98765_events.nxs.h5"
    output_dir = "Any/Dir"

    # Construct the expected command
    expected_command = [
        "/usr/bin/nsd-conda-wrap.sh",
        expected_conda_env,
        "--classic",
        auto_reduce_script,
        nexus_file_name,
        output_dir,
    ]

    # Verify
    verify_subprocess_command(auto_reduce_script, nexus_file_name, output_dir, expected_command)


@pytest.mark.parametrize(
    "auto_reduce_script",
    [
        "tests/reduce_EQSANS.py",
        "tests/reduce_Mantid50.py",
        "tests/reduce_HYS.py",
        "tests/reduce_REF_L.py",
        "tests/reduce_SNAP.py",
    ],
    ids=("eqsans", "mantid50", "hyspec", "ref_l", "snap"),
)
def test_legacy_scripts_fail(auto_reduce_script):
    """Test that legacy scripts without CONDA_ENV fail with appropriate error messages"""
    # set up test cases
    auto_reduce_script = os.path.join(os.getcwd(), auto_reduce_script)
    nexus_file_name = "/SNS/INS/IPTS-1234/nexus/INS_98765_events.nxs.h5"
    output_dir = "Any/Dir"

    # Verify that these scripts now fail with appropriate error messages
    with pytest.raises(RuntimeError) as exc_info:
        generate_subprocess_command(auto_reduce_script, [nexus_file_name, output_dir], False)

    assert "does not specify a CONDA_ENV" in str(exc_info.value)


def verify_subprocess_command(reduce_script, nexus_file, output_dir, expected_output):
    """Get subprocess command from auto reduction script

    Exception: AssertionError if the output does not meet expected output

    Parameters
    ----------
    reduce_script: str
        auto reduction script
    nexus_file: str
        nexus file name
    output_dir: str
        output directory
    expected_output: ~list
        expected output

    Returns
    -------
    None

    """
    # generate command
    sub_process_command = generate_subprocess_command(reduce_script, [nexus_file, output_dir], False)

    assert sub_process_command == expected_output, "Expected: {}.  But: {}" "".format(
        expected_output, sub_process_command
    )


if __name__ == "__main__":
    pytest.main([__file__])
