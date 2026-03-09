"""
Processor for ONCat cataloging

@copyright: 2017 Oak Ridge National Laboratory
"""

import os
import logging
import json
import glob
from .base_processor import BaseProcessor
import pyoncat


# Batch size for image ingestion (must be less than max of 100)
IMAGE_BATCH_SIZE = 50


class ONCatProcessor(BaseProcessor):
    """
    Define post-processing task
    """

    ## Input queue
    _message_queue = "/queue/CATALOG.ONCAT.DATA_READY"
    STARTED_QUEUE = "/queue/CATALOG.ONCAT.STARTED"
    COMPLETE_QUEUE = "/queue/CATALOG.ONCAT.COMPLETE"
    ERROR_QUEUE = "/queue/CATALOG.ONCAT.ERROR"

    def __call__(self):
        """
        Execute the job
        """

        self.send(self.STARTED_QUEUE, json.dumps(self.data))

        try:
            self.ingest(self.data["data_file"])
        except Exception as e:
            logging.error("Error ingesting data file: %s", e)
            self.data["error"] = f"ONCAT: {e}"
            self.send(self.ERROR_QUEUE, json.dumps(self.data))
        else:
            self.send(self.COMPLETE_QUEUE, json.dumps(self.data))

    def ingest(self, location):
        """Will catalog the given file and any other related files.

        pyoncat ingest makes a POST request to the ONCat server to register
        the file.
        """
        oncat = pyoncat.ONCat(
            self.configuration.oncat_url,
            api_token=self.configuration.oncat_api_token,
        )

        location = location.replace("//", "/")

        logging.info("Calling ONCat for %s", location)
        datafile = oncat.Datafile.ingest(location)

        for related_file in related_files(datafile):
            # With PyONCat 1.4.0 in Python 2, we need to convert from
            # unicode to str.  See: #210.
            logging.info("Calling ONCat for %s", related_file)
            oncat.Datafile.ingest(related_file)

        # Catalog image files using batch API for efficiency
        images = image_files(datafile, self.configuration.image_filepath_metadata_paths)
        for batch in batches(images, IMAGE_BATCH_SIZE):
            logging.info("Batch ingesting %d image files", len(batch))
            oncat.Datafile.batch(batch)


def batches(items, size):
    """Yield successive batches of items.

    Args:
        items: List of items to batch
        size: Size of each batch

    Yields:
        List slices of the specified size
    """
    for i in range(0, len(items), size):
        yield items[i : i + size]


def related_files(datafile):
    """Given a datafile, return a list of related files to also catalog.
    This is a simple heuristic based on the file's location and run number.
    """
    location = datafile.location
    facility = datafile.facility
    instrument = datafile.instrument
    experiment = datafile.experiment
    run_number = datafile.get("indexed.run_number")

    if not run_number:
        return []

    return [
        path
        for path in glob.glob(
            os.path.join(
                "/",
                facility,
                instrument,
                experiment,
                "images",
                "det_*",
                instrument + "_" + str(run_number) + "_det_*",
            )
        )
        if path != location
    ]


def image_files(datafile, metadata_paths):
    """Find image files from metadata paths.

    Iterates through the configured metadata paths, retrieves values from
    the datafile metadata, and globs for image files in the discovered
    subdirectories.

    Args:
        datafile: ONCat datafile object with metadata
        metadata_paths: List of metadata paths to check for image directory locations

    Returns:
        List of absolute paths to image files (FITS and TIFF)
    """
    facility = datafile.facility
    instrument = datafile.instrument
    experiment = datafile.experiment
    image_file_paths = []

    for metadata_path in metadata_paths:
        value = datafile.get(metadata_path)
        if value is None:
            continue

        subdirs = value if isinstance(value, list) else [value]

        for subdir in subdirs:
            full_path = os.path.join("/", facility, instrument, experiment, subdir)

            if not os.path.isdir(full_path):
                continue

            fits_files = glob.glob(os.path.join(full_path, "*.fits"))
            tiff_files = glob.glob(os.path.join(full_path, "*.tiff"))
            image_file_paths.extend(fits_files + tiff_files)

    return image_file_paths
