"""
`   Processor for Calvera cataloging

   @copyright: 2023 Oak Ridge National Laboratory
"""

import copy
import logging
import json
import os
import re
from typing import NamedTuple, Optional

import requests
import yaml
from .base_processor import BaseProcessor

## Per-instrument config, in /<facility>/<instrument>/shared/, which takes precedence over the reduction JSON file
AUTOREGISTER_CONFIG_FILE = "tiled-autoregister-config.yaml"

PLACEHOLDERS = ("facility", "instrument", "ipts", "run_number")


class FilePattern(NamedTuple):
    """A file pattern compiled for one run, with the template of the file's path in Tiled, if configured"""

    regex: re.Pattern
    tiled_path: Optional[str] = None


def autoregister_config_path(facility, instrument):
    """Return the path of the instrument's autoregister config"""
    return os.path.join("/", facility, instrument, "shared", AUTOREGISTER_CONFIG_FILE)


def run_placeholders(data_file, facility, ipts):
    """
    Return the placeholder values for a run.

    The instrument and run number come from the raw file name, ``<instrument>_<run_number>.nxs.h5``.
    """
    instrument, run_number = os.path.basename(data_file).removesuffix(".nxs.h5").rsplit("_", 1)
    return {"facility": facility, "instrument": instrument, "ipts": ipts, "run_number": run_number}


def load_file_patterns(config_path):
    """
    Return the entries under ``file_patterns`` in the autoregister config.

    Each entry is either a regex string or a mapping with a ``pattern`` regex and an optional
    ``tiled_path`` template. Entries are returned as ``{"pattern": ..., "tiled_path": ...}``
    dictionaries, with ``tiled_path`` set to None when it is not configured.
    """
    with open(config_path) as f:
        config = yaml.safe_load(f) or {}
    file_patterns = config.get("file_patterns") if isinstance(config, dict) else None
    if not isinstance(file_patterns, list) or not file_patterns:
        raise ValueError(f"{config_path} does not define a list of file_patterns")

    entries = []
    for file_pattern in file_patterns:
        if isinstance(file_pattern, str):
            entries.append({"pattern": file_pattern, "tiled_path": None})
        elif isinstance(file_pattern, dict) and isinstance(file_pattern.get("pattern"), str):
            tiled_path = file_pattern.get("tiled_path")
            if tiled_path is not None and not isinstance(tiled_path, str):
                raise ValueError(f"{config_path}: tiled_path of {file_pattern['pattern']!r} is not a string")
            entries.append({"pattern": file_pattern["pattern"], "tiled_path": tiled_path})
        else:
            raise ValueError(f"{config_path}: {file_pattern!r} is neither a regex nor a mapping with a pattern")
    return entries


def compile_file_patterns(file_patterns, placeholders):
    """
    Compile the file patterns from ``load_file_patterns`` for one run.

    The placeholders ``{facility}``, ``{instrument}``, ``{ipts}`` and ``{run_number}`` in a
    pattern or a Tiled path template are replaced with the values for the run.
    """
    compiled = []
    for file_pattern in file_patterns:
        pattern = file_pattern["pattern"]
        tiled_path = file_pattern["tiled_path"]
        for name in PLACEHOLDERS:
            value = str(placeholders[name])
            pattern = pattern.replace("{" + name + "}", re.escape(value))
            if tiled_path is not None:
                # Escape backslashes since the template is expanded with re.Match.expand
                tiled_path = tiled_path.replace("{" + name + "}", value.replace("\\", "\\\\"))
        compiled.append(FilePattern(re.compile(pattern), tiled_path))
    return compiled


def find_matching_files(file_patterns, output_dir):
    """
    Return the files under ``output_dir`` that match the compiled file patterns, sorted by location.

    A regex must match the whole path of the file relative to ``output_dir``, with ``/`` as the
    separator, so a pattern can include subdirectories. If a file matches more than one pattern,
    the first one sets its Tiled path, which is the pattern's template expanded with the groups
    captured by the regex. Each file is returned as ``{"location": ...}``, with a ``tiled_path``
    key when the matching pattern has a Tiled path template.
    """
    matching_files = []
    for dir_path, _, file_names in os.walk(output_dir):
        for file_name in file_names:
            file_path = os.path.join(dir_path, file_name)
            relative_path = os.path.relpath(file_path, output_dir).replace(os.sep, "/")
            for file_pattern in file_patterns:
                match = file_pattern.regex.fullmatch(relative_path)
                if match:
                    output_file = {"location": file_path}
                    if file_pattern.tiled_path is not None:
                        output_file["tiled_path"] = match.expand(file_pattern.tiled_path)
                    matching_files.append(output_file)
                    break
    matching_files.sort(key=lambda output_file: output_file["location"])

    locations_by_tiled_path = {}
    for output_file in matching_files:
        if "tiled_path" in output_file:
            locations_by_tiled_path.setdefault(output_file["tiled_path"], []).append(output_file["location"])
    duplicates = {path: locations for path, locations in locations_by_tiled_path.items() if len(locations) > 1}
    if duplicates:
        details = "; ".join(f"{path}: {', '.join(locations)}" for path, locations in duplicates.items())
        raise ValueError(f"More than one file maps to the same tiled_path: {details}")

    return matching_files


def build_reduced_data_info(data_file, output_files):
    """Return the reduced data info in the shape of a reduction JSON file"""
    return {"input_files": [data_file], "output_files": output_files}


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

    def _build_reduced_data_info(self, config_path):
        """Build the reduced data info from the files in the output directory that match the autoregister config"""
        placeholders = run_placeholders(self.data_file, self.facility, self.proposal)
        file_patterns = compile_file_patterns(load_file_patterns(config_path), placeholders)
        output_files = find_matching_files(file_patterns, self.output_dir)
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
        config_path = self._autoregister_config_path()
        if os.path.exists(config_path):
            reduced_data_info = self._build_reduced_data_info(config_path)
        else:
            reduction_file_name = raw_file_name.replace(".nxs.h5", ".json")
            reduction_file_path = os.path.join(self.output_dir, reduction_file_name)
            reduced_data_info = self._read_reduced_data(reduction_file_path)
        if not reduced_data_info:
            raise Exception("Cannot read reduced data info")
        to_send["reduced_data_info"] = reduced_data_info
        return to_send
