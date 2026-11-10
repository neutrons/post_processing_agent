"""
`   Processor for Calvera cataloging

   @copyright: 2023 Oak Ridge National Laboratory
"""

import copy
import logging
import json
import os
import re
import requests
import yaml
from .base_processor import BaseProcessor

## Per-instrument config, in /<facility>/<instrument>/shared/, used when there is no reduction JSON file
AUTOREGISTER_CONFIG_FILE = "tiled-autoregister-config.yaml"


def autoregister_config_path(facility, instrument):
    """Return the path of the instrument's autoregister config"""
    return os.path.join("/", facility, instrument, "shared", AUTOREGISTER_CONFIG_FILE)


def load_file_patterns(config_path):
    """Return the list of regexes under ``file_patterns`` in the autoregister config"""
    with open(config_path) as f:
        config = yaml.safe_load(f) or {}
    file_patterns = config.get("file_patterns") if isinstance(config, dict) else None
    if not isinstance(file_patterns, list) or not file_patterns:
        raise ValueError(f"{config_path} does not define a list of file_patterns")
    return [str(pattern) for pattern in file_patterns]


def compile_file_patterns(file_patterns, raw_file_name):
    """
    Compile the file patterns for one run.

    The placeholders ``{instrument}`` and ``{run_number}`` in a pattern are replaced with the
    values from the raw file name, ``<instrument>_<run_number>.nxs.h5``.
    """
    instrument, run_number = os.path.basename(raw_file_name).removesuffix(".nxs.h5").rsplit("_", 1)
    return [
        re.compile(
            pattern.replace("{instrument}", re.escape(instrument)).replace("{run_number}", re.escape(run_number))
        )
        for pattern in file_patterns
    ]


def find_matching_files(regexes, output_dir):
    """
    Return the sorted paths of the files under ``output_dir`` that match any of the regexes.

    A regex must match the whole path of the file relative to ``output_dir``, with ``/`` as the
    separator, so a pattern can include subdirectories.
    """
    matching_files = []
    for dir_path, _, file_names in os.walk(output_dir):
        for file_name in file_names:
            file_path = os.path.join(dir_path, file_name)
            relative_path = os.path.relpath(file_path, output_dir).replace(os.sep, "/")
            if any(regex.fullmatch(relative_path) for regex in regexes):
                matching_files.append(file_path)
    return sorted(matching_files)


def build_reduced_data_info(data_file, output_files):
    """Return the reduced data info in the shape of a reduction JSON file"""
    return {"input_files": [data_file], "output_files": [{"location": path} for path in output_files]}


class CalveraProcessor(BaseProcessor):
    """
    Define post-processing task
    """

    ## Input queue
    _message_queue = "/queue/CALVERA.RAW.DATA_READY"
    COMPLETE_QUEUE = "/queue/CALVERA.RAW.COMPLETE"
    ERROR_QUEUE = "/queue/CALVERA.RAW.ERROR"

    def _prepare_send_data(self):
        to_send = copy.deepcopy(self.data)
        to_send["type"] = "raw"
        return to_send

    def send_to_calvera(self):
        res = {}
        try:
            data_to_send = self._prepare_send_data()
            response = requests.post(self.configuration.calvera_ingest_url, json=data_to_send, timeout=3)
            if response.status_code == 200:
                success = True
            else:
                success = False
                res["error"] = f"SENDING TO Calvera: {response.text}"
        except Exception as e:
            success = False
            res["error"] = f"SENDING TO Calvera: {e}"

        return success, res

    def __call__(self):
        """
        Execute the job
        """
        success, status_data = self.send_to_calvera()
        self.data.update(status_data)
        if success:
            self.send(self.COMPLETE_QUEUE, json.dumps(self.data))
        else:
            self.send(self.ERROR_QUEUE, json.dumps(self.data))


class CalveraReducedProcessor(CalveraProcessor):
    """
    Defines post-processing task for reduced data
    """

    ## Input queue
    _message_queue = "/queue/CALVERA.REDUCED.DATA_READY"
    COMPLETE_QUEUE = "/queue/CALVERA.REDUCED.COMPLETE"
    ERROR_QUEUE = "/queue/CALVERA.REDUCED.ERROR"

    def _read_reduced_data(self, filepath):
        if not os.path.exists(filepath):
            logging.info("Could not find %s so will not send to Calvera", filepath)
            return None

        with open(filepath) as f:
            contents = json.load(f)
            if "input_files" not in contents or "output_files" not in contents:
                logging.info(
                    "%s does not appear to be a JSON reduction file so will not send to Calvera",
                    filepath,
                )
                return None

        return contents

    def _autoregister_config_path(self):
        return autoregister_config_path(self.facility, self.instrument)

    def _build_reduced_data_info(self, config_path, raw_file_name):
        """Build the reduced data info from the files in the output directory that match the autoregister config"""
        if not os.path.exists(config_path):
            logging.info("Could not find %s so will not send to Calvera", config_path)
            return None

        regexes = compile_file_patterns(load_file_patterns(config_path), raw_file_name)
        output_files = find_matching_files(regexes, self.output_dir)
        if not output_files:
            logging.info(
                "No files in %s match the patterns in %s so will not send to Calvera",
                self.output_dir,
                config_path,
            )
            return None

        return build_reduced_data_info(self.data_file, output_files)

    def _prepare_send_data(self):
        to_send = copy.deepcopy(self.data)
        to_send["type"] = "reduced"
        raw_file_name = os.path.basename(self.data["data_file"])
        reduction_file_name = raw_file_name.replace(".nxs.h5", ".json")
        reduction_file_path = os.path.join(self.output_dir, reduction_file_name)
        reduced_data_info = self._read_reduced_data(reduction_file_path)
        if not reduced_data_info:
            reduced_data_info = self._build_reduced_data_info(self._autoregister_config_path(), raw_file_name)
        if not reduced_data_info:
            raise Exception("Cannot read reduced data info")
        to_send["reduced_data_info"] = reduced_data_info
        return to_send
