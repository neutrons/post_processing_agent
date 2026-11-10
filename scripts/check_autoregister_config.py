#!/usr/bin/env python3
"""
Check an instrument's autoregister config against a run.

Looks up the config at /<facility>/<instrument>/shared/tiled-autoregister-config.yaml, where the
facility, instrument and IPTS come from the NeXus file path /<facility>/<instrument>/<IPTS>/nexus/...,
and prints the files in the output directory that the Calvera reduced processor would register
for the run, with their Tiled paths, along with the reduced data info it would send.
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
    run_placeholders,
)


def facility_instrument_and_ipts(nexus_file):
    """Return the facility, instrument and IPTS from a NeXus file path /<facility>/<instrument>/<IPTS>/..."""
    parts = os.path.abspath(nexus_file).split(os.sep)
    if len(parts) < 5:
        raise ValueError(f"{nexus_file} is not under /<facility>/<instrument>/<IPTS>/")
    return parts[1].upper(), parts[2].upper(), parts[3].upper()


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
        facility, instrument, ipts = facility_instrument_and_ipts(args.nexus_file)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    config_path = autoregister_config_path(facility, instrument)
    print(f"Config: {config_path}")
    if not os.path.exists(config_path):
        print(f"Error: {config_path} does not exist", file=sys.stderr)
        return 1

    placeholders = run_placeholders(args.nexus_file, facility, ipts)
    try:
        file_patterns = compile_file_patterns(load_file_patterns(config_path), placeholders)
    except Exception as e:
        print(f"Error: cannot read the file patterns in {config_path}: {e}", file=sys.stderr)
        return 1

    print("Patterns for this run:")
    for file_pattern in file_patterns:
        print(f"  {file_pattern.regex.pattern}")
        if file_pattern.tiled_path is not None:
            print(f"    tiled_path: {file_pattern.tiled_path}")

    try:
        output_files = find_matching_files(file_patterns, args.output_dir)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if not output_files:
        print(f"Error: no files in {args.output_dir} match the patterns", file=sys.stderr)
        return 1

    print(f"Matching files ({len(output_files)}):")
    for output_file in output_files:
        print(f"  {output_file['location']}")
        if "tiled_path" in output_file:
            print(f"    tiled_path: {output_file['tiled_path']}")

    print("Reduced data info:")
    print(json.dumps(build_reduced_data_info(os.path.abspath(args.nexus_file), output_files), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
