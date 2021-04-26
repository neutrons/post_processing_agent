import pytest
import os
from scripts import mantidpython
from scripts.mantidpython import generate_subprocess_command, get_mantid_loc

"""
Expected test result

(autoreduction) mac102648:post_processing_agent wzz$ python scripts/mantidpython.py tests/reduce_EQSANS.py aa bb
command type: <class 'list'>
command     : ['/opt/mantid50/bin/mantidpython', '--classic', 'tests/reduce_EQSANS.py', 'aa', 'bb']
(autoreduction) mac102648:post_processing_agent wzz$ python scripts/mantidpython.py tests/reduce_HYS.py aa bb
Failed to determine mantid version from script: 'tests/reduce_HYS.py'
Defaulting to system python
command type: <class 'list'>
command     : ['python3', 'tests/reduce_HYS.py', 'aa', 'bb']
(autoreduction) mac102648:post_processing_agent wzz$ python scripts/mantidpython.py tests/reduce_NOM.py aa bb
Failed to determine mantid version from script: 'tests/reduce_NOM.py'
Defaulting to system python
command type: <class 'list'>
command     : ['python3', 'tests/reduce_NOM.py', 'aa', 'bb']
(autoreduction) mac102648:post_processing_agent wzz$ python scripts/mantidpython.py tests/reduce_REF_L.py aa bb
command type: <class 'list'>
command     : ['/opt/mantidnightly/bin/mantidpython', '--classic', 'tests/reduce_REF_L.py', 'aa', 'bb']
(autoreduction) mac102648:post_processing_agent wzz$ python scripts/mantidpython.py tests/reduce_SNAP.py aa bb
command type: <class 'list'>
command     : ['/opt/mantidnightly/bin/mantidpython', '--classic', 'tests/reduce_SNAP.py', 'aa', 'bb']

"""


def test_get_mantid_location():
    """ testing for the extraction function
    """
    # backward compatible
    assert get_mantid_loc("from mantid.simpleapi import ")[0] is None
    assert get_mantid_loc('sys.path.append(os.path.join("/opt/Mantid/bin"))')[0] == '/opt/Mantid/bin'
    assert get_mantid_loc("sys.path.insert(0,'/opt/Mantid/bin')")[0] == '/opt/Mantid/bin'
    assert get_mantid_loc('sys.path.append("/opt/mantidnightly/bin")')[0] == '/opt/mantidnightly/bin'

    # new
    assert get_mantid_loc("MANTID_VERSION='nightly'")[0] == "/opt/mantidnightly/bin"
    assert get_mantid_loc("MANTID_VERSION='60'")[0] == "/opt/mantid60/bin"
    assert get_mantid_loc("MANTID_VERSION='stable'")[0] == "/opt/Mantid/bin"

    # conda
    assert get_mantid_loc("CONDA_ENV='sasview'")[1] == 'sasview'
    assert get_mantid_loc("CONDA_ENV='imaging'")[1] == 'imaging'


@pytest.mark.parametrize('auto_reduce_script, expected_command_arg0, expected_command_arg1',
                         [('tests/reduce_EQSANS.py', '/opt/mantid50/bin/mantidpython', '--classic'),
                          ('tests/reduce_HYS.py', 'python3', None),
                          ('tests/reduce_REF_L.py', '/opt/mantidnightly/bin/mantidpython', '--classic'),
                          ('tests/reduce_SNAP.py', '/opt/mantidnightly/bin/mantidpython', '--classic')],
                         ids=('eqsans', 'hyspec', 'ref_l', 'snap'))
def test_mantid_python_location(auto_reduce_script, expected_command_arg0, expected_command_arg1):

    # set up test cases
    auto_reduce_script = os.path.join(os.getcwd(), auto_reduce_script)
    nexus_file_name = '/SNS/INS/IPTS-1234/nexus/INS_98765_events.nxs.h5'
    output_dir = 'Any/Dir'

    # Construct the gold command
    gold_command = [expected_command_arg0]
    if expected_command_arg1:
        gold_command.append(expected_command_arg1)
    gold_command.extend([auto_reduce_script, nexus_file_name, output_dir])

    # Verify
    verify_subprocess_command(auto_reduce_script, nexus_file_name, output_dir, gold_command)


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

    assert sub_process_command == expected_output


if __name__ == '__main__':
    pytest.main([__file__])
