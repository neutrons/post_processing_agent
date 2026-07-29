"""
Processor for ONCat cataloging

@copyright: 2017 Oak Ridge National Laboratory
"""

import os
import logging
import json
import glob
import re
from .base_processor import BaseProcessor
import pyoncat


# Batch size for image ingestion (must be less than max of 100)
IMAGE_BATCH_SIZE = 50

# Glob patterns for the image files to catalog
IMAGE_FILE_PATTERNS = ("*.fits", "*.tiff")


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

        # Catalog image files (a VENUS-specific substep), if enabled for this instrument
        self.catalog_images(oncat, datafile)

    def catalog_images(self, oncat, datafile):
        """Catalog image files using the batch API, if enabled for this instrument.

        Image cataloging is a special substep currently used only by VENUS. It can be
        dynamically enabled or disabled per instrument by adding or removing the script
        ``catalog_<INSTRUMENT>.py`` in the instrument's shared autoreduce directory. This
        mirrors the ``reduce_<INSTRUMENT>.py`` convention used to toggle autoreduction, so
        an instrument scientist can turn image cataloging off (e.g. to relieve a backlog)
        by moving that file, with no code change or service restart.

        @param oncat: an authenticated pyoncat.ONCat client
        @param datafile: the ONCat datafile object returned by ingesting the main file
        """
        instrument_shared_dir = os.path.join("/", self.facility, self.instrument, "shared", "autoreduce")
        if len(self.configuration.dev_instrument_shared) > 0:
            instrument_shared_dir = self.configuration.dev_instrument_shared

        catalog_script = os.path.join(instrument_shared_dir, f"catalog_{self.instrument}.py")
        if not os.path.isfile(catalog_script):
            logging.info(
                "Image cataloging disabled for %s (no %s)",
                self.instrument,
                catalog_script,
            )
            return

        logging.info("Image cataloging enabled for %s (found %s)", self.instrument, catalog_script)
        images = image_files(datafile, self.configuration.image_filepath_metadata_paths, self.run_number)
        logging.info("Cataloging %d image file(s) for run %s", len(images), self.run_number)
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


def matches_run_number(image_file_path, run_number):
    """Whether an image file belongs to the given run.

    The VENUS DAQ writes every image file with a name that begins with
    ``YYYYMMDD_Run_<run_number>_``, no matter which detector produced it (this
    has been confirmed for QHY, Andor, TPX1 and MCP TPX1 data). Matching on that
    prefix is therefore how we tell the images of the run being cataloged apart
    from the images of the other runs sharing the same directory.

    The run number must be followed by a non-digit, otherwise run 2482 would
    also claim the images of runs 24820-24829.

    Args:
        image_file_path: Path to a candidate image file
        run_number: Run number being cataloged

    Returns:
        True if the file name identifies it as an image of that run
    """
    run_number = str(run_number).strip()
    # The DAQ writes the run number without zero padding
    if run_number.isdigit():
        run_number = str(int(run_number))

    file_name = os.path.basename(image_file_path)
    return re.match(r"\d{8}_Run_" + re.escape(run_number) + r"(?![0-9])", file_name) is not None


def image_files(datafile, metadata_paths, run_number):
    """Find the image files belonging to a run.

    Iterates through the configured metadata paths and, for each location found
    in the datafile metadata, collects the image files that belong to the run
    being cataloged. See ``_image_files_at`` for how a single location is
    resolved and ``matches_run_number`` for how the files are filtered.

    Args:
        datafile: ONCat datafile object with metadata
        metadata_paths: List of metadata paths to check for image file locations
        run_number: Run number being cataloged

    Returns:
        List of absolute paths to this run's image files (FITS and TIFF)
    """
    facility = datafile.facility
    instrument = datafile.instrument
    experiment = datafile.experiment
    image_file_paths = []

    for metadata_path in metadata_paths:
        value = datafile.get(metadata_path)
        if value is None:
            continue

        # A single metadata path can report more than one location, for instance
        # MCP TPX1 runs report both this run's directory and the previous run's
        locations = value if isinstance(value, list) else [value]

        for location in locations:
            full_path = os.path.join("/", facility, instrument, experiment, location)
            image_file_paths.extend(_image_files_at(full_path, run_number))

    # Locations can be reported more than once, so ingest each file only once
    return list(dict.fromkeys(image_file_paths))


def _image_files_at(location, run_number):
    """Return the image files at a single location that belong to a run.

    The image file path recorded by the DAQ is meant to point at an image file,
    but for several detectors it points at the directory holding a whole series
    of images instead, and consecutive runs of a series share that directory.
    Both forms are filtered by run number, so that a run only ever catalogs its
    own images: cataloging the whole directory was making a run re-catalog every
    image written by the runs before it, which is slow enough to back up the
    autoreducers.

    Args:
        location: Absolute path reported by the image file path metadata
        run_number: Run number being cataloged

    Returns:
        List of absolute paths to this run's image files at that location
    """
    if os.path.isdir(location):
        candidates = []
        for pattern in IMAGE_FILE_PATTERNS:
            candidates.extend(glob.glob(os.path.join(location, pattern)))
        # Glob order is arbitrary; keep the batches in a predictable order
        candidates.sort()
    elif os.path.isfile(location):
        candidates = [location]
    else:
        logging.warning("Image file location %s is neither a file nor a directory", location)
        return []

    matching_files = [path for path in candidates if matches_run_number(path, run_number)]

    skipped = len(candidates) - len(matching_files)
    if skipped > 0:
        logging.info(
            "Skipping %d image file(s) in %s belonging to other runs",
            skipped,
            location,
        )
    if not matching_files:
        logging.warning("Found no image files for run %s in %s", run_number, location)

    return matching_files
