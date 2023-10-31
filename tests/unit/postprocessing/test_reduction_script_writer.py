# package imports
from postprocessing.reduction_script_writer import ScriptWriter

# third-party imports
import pytest

# standard imports
from collections import namedtuple
from copy import copy
import filecmp
import os
import shutil
import tempfile


@pytest.yield_fixture(
    scope="module"
)  # 'yield_fixture' deprecated in favor of 'yield' when using python 3.x
def writer_local(data_server):
    r"""A ScriptWriter with a temporary autoreduction directory"""
    # create temporary directory and copy there the autoreduction template
    writer = ScriptWriter("CNCS")
    writer.autoreduction_dir = tempfile.mkdtemp()
    shutil.copyfile(
        data_server.path_to(writer.template_name),
        os.path.join(writer.autoreduction_dir, writer.template_name),
    )
    yield writer
    shutil.rmtree(
        writer.autoreduction_dir
    )  # called after all tests in this module finish


class TestScriptWriter(object):
    arguments = {
        "mask": """MaskBTPParameters.append({'Pixel': '121-128'})
    MaskBTPParameters.append({'Pixel': '1-8'})
    MaskBTPParameters.append({'Bank': '36-50'})
    """,
        "raw_vanadium": "/SNS/CNCS/IPTS-26786/nexus/CNCS_386574.nxs.h5",
        "processed_vanadium": "van_386574.nxs",
        "vanadium_integration_min": 49501.0,
        "vanadium_integration_max": 50501.0,
        "grouping": "8x2",
        "e_min": "-0.95",
        "e_max": "0.95",
        "e_step": "0.005",
        "e_pars_in_mev": False,
        "tib_min": "",
        "tib_max": "",
        "do_tib": True,
        "t0": "",
        "motor_names": "omega",
        "temperature_names": "SampleTemp,sampletemp,SensorB,SensorA,temp5,temp8,sensor0normal,SensorC,Temp4",
        "create_elastic_nxspe": False,
        "create_md_nxs": False,
        "a": "8.355",
        "b": "8.355",
        "c": "9.076",
        "alpha": "90.0",
        "beta": "90.0",
        "gamma": "120.0",
        "u_vector": "-1.46299,-1.46299,8.50124",
        "v_vector": "3.91295,3.91295,3.17848",
        "sub_directory": "/tmp",
        "auto_tzero_flag": False,
    }

    def test_init(self):
        writer = ScriptWriter("cncs")
        assert writer.script_name == "reduce_CNCS.py"
        assert writer.template_name == "reduce_CNCS.py.template"
        assert writer.default_script_name == "reduce_CNCS_default.py"
        assert writer.autoreduction_dir == "/SNS/CNCS/shared/autoreduce"
        assert (
            writer._template_path
            == "/SNS/CNCS/shared/autoreduce/reduce_CNCS.py.template"
        )

    def test_get_arguments(self, writer_local):
        keywords = writer_local.get_arguments()
        assert keywords == {
            "do_tib",
            "processed_vanadium",
            "e_step",
            "tib_max",
            "tib_min",
            "u_vector",
            "temperature_names",
            "sub_directory",
            "create_elastic_nxspe",
            "e_pars_in_mev",
            "create_md_nxs",
            "beta",
            "v_vector",
            "vanadium_integration_min",
            "auto_tzero_flag",
            "alpha",
            "vanadium_integration_max",
            "a",
            "motor_names",
            "c",
            "b",
            "mask",
            "t0",
            "e_min",
            "raw_vanadium",
            "grouping",
            "gamma",
            "e_max",
        }

    def test_check_arguments(self, writer_local):
        arguments = {key: None for key in writer_local.get_arguments()}
        del arguments["do_tib"]
        with pytest.raises(KeyError) as exception_info:
            writer_local.check_arguments(**arguments)
        assert "\"Template arguments missing: ['do_tib']\"" == str(exception_info.value)

    def test_write_script(self, data_server, writer_local):
        arguments = copy(self.arguments)
        writer_local.write_script(
            **arguments
        )  # create autoreduce_CNCS.py in the autoreduction directory
        script_new = os.path.join(
            writer_local.autoreduction_dir, writer_local.script_name
        )
        filecmp.cmp(
            script_new,
            data_server.path_to(writer_local.script_name),  # expected script
            shallow=False,
        )  # compare contents, not just metadata
        # test for exception if one argument is missing
        del arguments["do_tib"]
        with pytest.raises(KeyError) as exception_info:
            writer_local.write_script(**arguments)
        assert "\"Template arguments missing: ['do_tib']\"" == str(exception_info.value)

    def test_process_request(self, data_server, writer_local):
        # mock the inputs for a successful call to ScriptWriter.process_request
        request_data = {"instrument": "CNCS"}
        Configuration = namedtuple("Configuration", "service_status")
        configuration = Configuration("${instrument}")

        # file to collect debug info generated by ScriptWriter.process_request
        _, amq_data_file = tempfile.mkstemp()

        def send_function(amq_topic, amq_data_dump):
            open(amq_data_file, "w").write(amq_data_dump)

        # run the test with not reduction template
        writer_local.process_request(request_data, configuration, send_function)
        assert "Missing CNCS reduction template" in open(amq_data_file, "r").read()

        # run the test with a reduction template
        request_data["template_data"] = copy(self.arguments)
        writer_local.process_request(request_data, configuration, send_function)
        assert "Created CNCS reduction script" in open(amq_data_file, "r").read()
        assert os.path.isfile(writer_local.log_file)

        # report error when using the default script
        request_data["use_default"] = True
        writer_local.process_request(request_data, configuration, send_function)
        assert "Error creating CNCS reduction script" in open(amq_data_file, "r").read()

        # create a default script
        shutil.copyfile(
            data_server.path_to(writer_local.template_name),
            os.path.join(
                writer_local.autoreduction_dir, writer_local.default_script_name
            ),
        )
        writer_local.process_request(request_data, configuration, send_function)
        assert "Installed default CNCS script" in open(amq_data_file, "r").read()

        os.remove(amq_data_file)


if __name__ == "__main__":
    pytest.main([__file__])
