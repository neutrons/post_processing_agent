#!/usr/bin/env python3
"""
Check an instrument's autoregister config against a run.

Looks up the config at /<facility>/<instrument>/shared/tiled-autoregister-config.yaml, where the
facility and instrument come from the NeXus file path /<facility>/<instrument>/<IPTS>/nexus/...,
and prints the files in the output directory that the Calvera reduced processor would register
for the run, along with the reduced data info it would send.
"""

import argparse
import json
import os
import sys

from postprocessing.processors.calvera_processor import (
    autoregister_config_path,
    build_reduced_data_info,
    compile_file_patterns,
    find_matching_files,
    load_file_patterns,
)


def facility_and_instrument(nexus_file):
    """Return the facility and instrument from a NeXus file path /<facility>/<instrument>/..."""
    parts = os.path.abspath(nexus_file).split(os.sep)
    if len(parts) < 4:
        raise ValueError(f"{nexus_file} is not under /<facility>/<instrument>/")
    return parts[1].upper(), parts[2].upper()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="List the files the Calvera reduced processor would register for a run "
        "based on the instrument's tiled-autoregister-config.yaml"
    )
    parser.add_argument("nexus_file", help="path to the raw data file, <instrument>_<run_number>.nxs.h5")
    parser.add_argument("output_dir", help="directory containing the reduced files to register")
    args = parser.parse_args(argv)

    if not args.nexus_file.endswith(".nxs.h5"):
        print(f"Error: {args.nexus_file} is not a .nxs.h5 file", file=sys.stderr)
        return 1
    if not os.path.isdir(args.output_dir):
        print(f"Error: output directory {args.output_dir} does not exist", file=sys.stderr)
        return 1

    try:
        facility, instrument = facility_and_instrument(args.nexus_file)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    config_path = autoregister_config_path(facility, instrument)
    print(f"Config: {config_path}")
    if not os.path.exists(config_path):
        print(f"Error: {config_path} does not exist", file=sys.stderr)
        return 1

    try:
        regexes = compile_file_patterns(load_file_patterns(config_path), args.nexus_file)
    except Exception as e:
        print(f"Error: cannot read the file patterns in {config_path}: {e}", file=sys.stderr)
        return 1

    print("Patterns for this run:")
    for regex in regexes:
        print(f"  {regex.pattern}")

    output_files = find_matching_files(regexes, args.output_dir)
    if not output_files:
        print(f"Error: no files in {args.output_dir} match the patterns", file=sys.stderr)
        return 1

    print(f"Matching files ({len(output_files)}):")
    for path in output_files:
        print(f"  {path}")

    print("Reduced data info:")
    print(json.dumps(build_reduced_data_info(os.path.abspath(args.nexus_file), output_files), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
