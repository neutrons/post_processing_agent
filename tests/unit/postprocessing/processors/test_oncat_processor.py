from unittest.mock import Mock, patch

import pytest

from postprocessing.processors.oncat_processor import (
    ONCatProcessor,
    batches,
    related_files,
    image_files,
    matches_run_number,
)

METADATA_PATHS = ["metadata.entry.daslogs.bl10:exp:im:imagefilepath.value"]


def make_datafile(tmp_path, metadata_value):
    """A datafile whose /facility/instrument/experiment root is under tmp_path.

    This lets the image file tests run against real files on disk, so the
    globbing and the run number filtering are exercised for real.
    """
    datafile = Mock()
    datafile.facility = str(tmp_path).lstrip("/")
    datafile.instrument = "VENUS"
    datafile.experiment = "IPTS-99999"
    datafile.get.return_value = metadata_value
    return datafile


def make_image_dir(tmp_path, subdir, file_names):
    """Create image files under the datafile root and return the directory"""
    image_dir = tmp_path / "VENUS" / "IPTS-99999" / subdir
    image_dir.mkdir(parents=True, exist_ok=True)
    for file_name in file_names:
        (image_dir / file_name).touch()
    return image_dir


def test_batches_empty_list():
    """Test batches function with empty list"""
    result = list(batches([], 50))
    assert result == []


def test_batches_single_batch():
    """Test batches function with items that fit in one batch"""
    items = list(range(10))
    result = list(batches(items, 50))
    assert len(result) == 1
    assert result[0] == items


def test_batches_multiple_batches():
    """Test batches function with items that require multiple batches"""
    items = list(range(125))
    result = list(batches(items, 50))
    assert len(result) == 3
    assert result[0] == list(range(0, 50))
    assert result[1] == list(range(50, 100))
    assert result[2] == list(range(100, 125))


def test_batches_exact_multiple():
    """Test batches function when items are exact multiple of batch size"""
    items = list(range(100))
    result = list(batches(items, 50))
    assert len(result) == 2
    assert result[0] == list(range(0, 50))
    assert result[1] == list(range(50, 100))


def test_related_files_no_run_number():
    """Test related_files when datafile has no run_number"""
    mock_datafile = Mock()
    mock_datafile.get.return_value = None

    result = related_files(mock_datafile)
    assert result == []


def test_related_files_with_run_number():
    """Test related_files finds matching files"""
    mock_datafile = Mock()
    mock_datafile.location = "/SNS/CORELLI/IPTS-15526/nexus/CORELLI_29666.nxs.h5"
    mock_datafile.facility = "SNS"
    mock_datafile.instrument = "CORELLI"
    mock_datafile.experiment = "IPTS-15526"
    mock_datafile.get.return_value = "29666"

    with patch("glob.glob") as mock_glob:
        mock_glob.return_value = [
            "/SNS/CORELLI/IPTS-15526/images/det_main/CORELLI_29666_det_main_000001.tiff",
            "/SNS/CORELLI/IPTS-15526/nexus/CORELLI_29666.nxs.h5",  # This should be excluded
        ]

        result = related_files(mock_datafile)

        assert len(result) == 1
        assert "/SNS/CORELLI/IPTS-15526/images/det_main/CORELLI_29666_det_main_000001.tiff" in result
        assert mock_datafile.location not in result


@pytest.mark.parametrize(
    "file_name, expected",
    [
        # The three naming schemes seen in production, all of which carry a
        # Run_<run_number> token but not in the same position
        ("20260713_Run_24828_long_acq_test_10_000s_0_700AngsMin_0_282.tiff", True),  # QHY, Andor, TPX1
        ("20250428_20260713_Run_24828_HDPErpi_Gd_0__0000_6311657.tiff", True),  # TPX3, two date prefixes
        ("Run_24828_20250516_May16_2025_OB_5C_0005_3137132_00826.fits", True),  # TPX1 raw/ob, run first
        # Images of the other runs sharing the directory
        ("20260713_Run_24827_long_acq_test_10_000s_0_700AngsMin_0_281.tiff", False),
        ("20260713_Run_24829_long_acq_test_10_000s_0_700AngsMin_1_283.tiff", False),
        # A run number that merely starts with, or extends, the one we want
        ("20260713_Run_2482_long_acq_test.tiff", False),
        ("20260713_Run_248280_long_acq_test.tiff", False),
        # The observed file names all continue with an underscore, but any
        # non-digit is deliberately accepted: a separator we have not seen should
        # over-catalog rather than silently catalog nothing for the run
        ("20260713_Run_24828.tiff", True),
        ("20260713_Run_24828-long-acq-test.tiff", True),
        # Names carrying no run number, or the number without the Run_ token
        ("image_001.tiff", False),
        ("20260713_24828_no_run_marker.tiff", False),
        ("Image004_00027.fits", False),
        # The token must start the name or follow an underscore
        ("Rerun_24828_not_a_run_token.tiff", False),
    ],
)
def test_matches_run_number(file_name, expected):
    """Only files named for this run match, wherever the Run_<run> token sits in
    the name, and the run number may not be a prefix of a longer run number"""
    assert matches_run_number("/SNS/VENUS/IPTS-25778/images/qhy411/" + file_name, "24828") is expected


def test_matches_run_number_excludes_previous_run_directory_contents():
    """A stale image file path can point at the previous run's directory, whose
    files name that run and must not be cataloged under this one"""
    previous_run_images = [
        "/SNS/VENUS/IPTS-35790/images/tpx3/raw/Run_7352_DSet0/20250317_Run_7352_ai_loop_0000_2039884.tiff",
        "/SNS/VENUS/IPTS-37446/images/tpx1/ob/20260305_Run_15289_Chop_Tune_ob_0/"
        "20260305_Run_15289_Chop_Tune_ob_0_046_01693.fits",
    ]
    assert not any(matches_run_number(path, "7353") for path in previous_run_images)
    assert not any(matches_run_number(path, "15291") for path in previous_run_images)


def test_matches_run_number_accepts_non_string_and_padded_run_numbers():
    """The run number comes from the message, so do not depend on its formatting"""
    file_name = "/SNS/VENUS/IPTS-25778/images/qhy411/20260713_Run_24828_long_acq_test.tiff"
    assert matches_run_number(file_name, 24828) is True
    assert matches_run_number(file_name, "024828") is True
    assert matches_run_number(file_name, " 24828 ") is True


def test_image_files_no_metadata():
    """Test image_files when metadata path doesn't exist"""
    mock_datafile = Mock()
    mock_datafile.facility = "SNS"
    mock_datafile.instrument = "VENUS"
    mock_datafile.experiment = "IPTS-99999"
    mock_datafile.get.return_value = None  # No metadata found

    result = image_files(mock_datafile, METADATA_PATHS, "12345")
    assert result == []


def test_image_files_metadata_neither_file_nor_directory(tmp_path):
    """Test image_files when metadata points to a location that does not exist"""
    mock_datafile = make_datafile(tmp_path, "images/does_not_exist")

    result = image_files(mock_datafile, METADATA_PATHS, "12345")
    assert result == []


def test_image_files_single_directory(tmp_path):
    """Only this run's FITS and TIFF files in the directory are cataloged"""
    image_dir = make_image_dir(
        tmp_path,
        "images",
        [
            "20260713_Run_12345_series_0001.fits",
            "20260713_Run_12345_series_0002.fits",
            "20260713_Run_12345_series_0003.tiff",
        ],
    )
    mock_datafile = make_datafile(tmp_path, "images")

    result = image_files(mock_datafile, METADATA_PATHS, "12345")

    assert result == [
        str(image_dir / "20260713_Run_12345_series_0001.fits"),
        str(image_dir / "20260713_Run_12345_series_0002.fits"),
        str(image_dir / "20260713_Run_12345_series_0003.tiff"),
    ]


def test_image_files_filters_out_other_runs(tmp_path):
    """A series directory is shared by consecutive runs: catalog only our own
    images, otherwise every run re-catalogs the images of the runs before it"""
    image_dir = make_image_dir(
        tmp_path,
        "images/qhy411/raw/radiography/20260713_long_acq_test",
        [
            "20260713_Run_12344_long_acq_test_0_281.tiff",
            "20260713_Run_12345_long_acq_test_1_282.tiff",
            "20260713_Run_12346_long_acq_test_2_283.tiff",
            "20260713_Run_123450_long_acq_test_3_284.tiff",
            "20260713_Run_1234_long_acq_test_4_285.tiff",
        ],
    )
    mock_datafile = make_datafile(tmp_path, "images/qhy411/raw/radiography/20260713_long_acq_test")

    result = image_files(mock_datafile, METADATA_PATHS, "12345")

    assert result == [str(image_dir / "20260713_Run_12345_long_acq_test_1_282.tiff")]


def test_image_files_single_file_location(tmp_path):
    """The metadata can point straight at an image file, which is filtered by
    run number just like the contents of a directory"""
    image_dir = make_image_dir(tmp_path, "images", ["20260713_Run_12345_series_0001.tiff"])
    mock_datafile = make_datafile(tmp_path, "images/20260713_Run_12345_series_0001.tiff")

    result = image_files(mock_datafile, METADATA_PATHS, "12345")

    assert result == [str(image_dir / "20260713_Run_12345_series_0001.tiff")]


def test_image_files_single_file_location_of_another_run(tmp_path):
    """A file naming a different run is not cataloged under this run"""
    make_image_dir(tmp_path, "images", ["20260713_Run_12344_series_0001.tiff"])
    mock_datafile = make_datafile(tmp_path, "images/20260713_Run_12344_series_0001.tiff")

    result = image_files(mock_datafile, METADATA_PATHS, "12345")

    assert result == []


def test_image_files_multiple_directories(tmp_path):
    """Test image_files with multiple locations (list of subdirectories).

    MCP TPX1 runs report two locations, the second being the directory of the
    previous run, whose images must not be cataloged again under this run.
    """
    previous_run_dir = make_image_dir(
        tmp_path,
        "images/tpx1/raw/20260611_LF99D/20260611_Run_12344_LF99D_24",
        ["20260611_Run_12344_LF99D_24_360_00000.fits"],
    )
    this_run_dir = make_image_dir(
        tmp_path,
        "images/tpx1/raw/20260611_LF99D/20260611_Run_12345_LF99D_25",
        ["20260611_Run_12345_LF99D_25_360_00000.fits"],
    )
    mock_datafile = make_datafile(
        tmp_path,
        [
            "images/tpx1/raw/20260611_LF99D/20260611_Run_12344_LF99D_24",
            "images/tpx1/raw/20260611_LF99D/20260611_Run_12345_LF99D_25",
        ],
    )

    result = image_files(mock_datafile, METADATA_PATHS, "12345")

    assert result == [str(this_run_dir / "20260611_Run_12345_LF99D_25_360_00000.fits")]
    assert not any(str(previous_run_dir) in path for path in result)


def test_image_files_ingests_each_file_once(tmp_path):
    """The same location can be reported more than once"""
    image_dir = make_image_dir(tmp_path, "images", ["20260713_Run_12345_series_0001.fits"])
    mock_datafile = make_datafile(tmp_path, ["images", "images"])

    result = image_files(mock_datafile, METADATA_PATHS + ["another.metadata.path"], "12345")

    assert result == [str(image_dir / "20260713_Run_12345_series_0001.fits")]


def test_oncat_processor_ingest_with_images():
    """Test ONCatProcessor.ingest method catalogs images using batch API"""
    test_message = {
        "run_number": "12345",
        "instrument": "VENUS",
        "ipts": "IPTS-99999",
        "facility": "SNS",
        "data_file": "/SNS/VENUS/IPTS-99999/nexus/VENUS_12345.nxs.h5",
    }

    mock_conf = Mock()
    mock_conf.oncat_url = "http://oncat:8000"
    mock_conf.oncat_api_token = "test-token"
    mock_conf.image_filepath_metadata_paths = ["metadata.entry.daslogs.bl10:exp:im:imagefilepath.value"]
    mock_conf.dev_instrument_shared = ""

    mock_send_function = Mock()

    with (
        patch("postprocessing.processors.base_processor.open", create=True),
        patch("postprocessing.processors.oncat_processor.pyoncat.ONCat") as mock_oncat_class,
        patch("postprocessing.processors.oncat_processor.related_files") as mock_related,
        patch("postprocessing.processors.oncat_processor.image_files") as mock_images,
        # Image cataloging is enabled for VENUS: the catalog_VENUS.py script is present
        patch("postprocessing.processors.oncat_processor.os.path.isfile", return_value=True),
    ):
        # Setup mocks
        mock_oncat = Mock()
        mock_oncat_class.return_value = mock_oncat

        mock_datafile = Mock()
        mock_oncat.Datafile.ingest.return_value = mock_datafile

        mock_related.return_value = []
        mock_images.return_value = [
            "/SNS/VENUS/IPTS-99999/images/image_001.fits",
            "/SNS/VENUS/IPTS-99999/images/image_002.fits",
            "/SNS/VENUS/IPTS-99999/images/image_003.tiff",
        ]

        # Create processor and call ingest
        processor = ONCatProcessor(test_message, mock_conf, mock_send_function)
        processor.ingest(test_message["data_file"])

        # Verify ONCat was initialized correctly
        mock_oncat_class.assert_called_once_with(
            "http://oncat:8000",
            api_token="test-token",
        )

        # Verify the main file was ingested
        mock_oncat.Datafile.ingest.assert_called_once()

        # Verify the images were looked up for the run being cataloged
        mock_images.assert_called_once_with(
            mock_datafile,
            mock_conf.image_filepath_metadata_paths,
            "12345",
        )

        # Verify batch was called with the image files
        mock_oncat.Datafile.batch.assert_called_once_with(
            [
                "/SNS/VENUS/IPTS-99999/images/image_001.fits",
                "/SNS/VENUS/IPTS-99999/images/image_002.fits",
                "/SNS/VENUS/IPTS-99999/images/image_003.tiff",
            ]
        )


def test_oncat_processor_ingest_with_many_images():
    """Test ONCatProcessor.ingest batches large number of images correctly"""
    test_message = {
        "run_number": "12345",
        "instrument": "VENUS",
        "ipts": "IPTS-99999",
        "facility": "SNS",
        "data_file": "/SNS/VENUS/IPTS-99999/nexus/VENUS_12345.nxs.h5",
    }

    mock_conf = Mock()
    mock_conf.oncat_url = "http://oncat:8000"
    mock_conf.oncat_api_token = "test-token"
    mock_conf.image_filepath_metadata_paths = ["metadata.entry.daslogs.bl10:exp:im:imagefilepath.value"]
    mock_conf.dev_instrument_shared = ""

    mock_send_function = Mock()

    # Create 125 image files (should be split into 3 batches: 50, 50, 25)
    many_images = [f"/SNS/VENUS/IPTS-99999/images/image_{i:04d}.fits" for i in range(125)]

    with (
        patch("postprocessing.processors.base_processor.open", create=True),
        patch("postprocessing.processors.oncat_processor.pyoncat.ONCat") as mock_oncat_class,
        patch("postprocessing.processors.oncat_processor.related_files") as mock_related,
        patch("postprocessing.processors.oncat_processor.image_files") as mock_images,
        # Image cataloging is enabled for VENUS: the catalog_VENUS.py script is present
        patch("postprocessing.processors.oncat_processor.os.path.isfile", return_value=True),
    ):
        # Setup mocks
        mock_oncat = Mock()
        mock_oncat_class.return_value = mock_oncat

        mock_datafile = Mock()
        mock_oncat.Datafile.ingest.return_value = mock_datafile

        mock_related.return_value = []
        mock_images.return_value = many_images

        # Create processor and call ingest
        processor = ONCatProcessor(test_message, mock_conf, mock_send_function)
        processor.ingest(test_message["data_file"])

        # Verify batch was called 3 times
        assert mock_oncat.Datafile.batch.call_count == 3

        # Verify batch sizes
        calls = mock_oncat.Datafile.batch.call_args_list
        assert len(calls[0][0][0]) == 50
        assert len(calls[1][0][0]) == 50
        assert len(calls[2][0][0]) == 25


def test_oncat_processor_image_cataloging_disabled():
    """When catalog_<INSTRUMENT>.py is absent, image cataloging is skipped but the
    main file and related files are still cataloged."""
    test_message = {
        "run_number": "12345",
        "instrument": "VENUS",
        "ipts": "IPTS-99999",
        "facility": "SNS",
        "data_file": "/SNS/VENUS/IPTS-99999/nexus/VENUS_12345.nxs.h5",
    }

    mock_conf = Mock()
    mock_conf.oncat_url = "http://oncat:8000"
    mock_conf.oncat_api_token = "test-token"
    mock_conf.image_filepath_metadata_paths = ["metadata.entry.daslogs.bl10:exp:im:imagefilepath.value"]
    mock_conf.dev_instrument_shared = ""

    mock_send_function = Mock()

    with (
        patch("postprocessing.processors.base_processor.open", create=True),
        patch("postprocessing.processors.oncat_processor.pyoncat.ONCat") as mock_oncat_class,
        patch("postprocessing.processors.oncat_processor.related_files") as mock_related,
        patch("postprocessing.processors.oncat_processor.image_files") as mock_images,
        # Image cataloging is disabled: the catalog_VENUS.py script is absent
        patch("postprocessing.processors.oncat_processor.os.path.isfile", return_value=False),
    ):
        mock_oncat = Mock()
        mock_oncat_class.return_value = mock_oncat
        mock_oncat.Datafile.ingest.return_value = Mock()
        mock_related.return_value = ["/SNS/VENUS/IPTS-99999/images/det_1/VENUS_12345_det_1.tiff"]

        processor = ONCatProcessor(test_message, mock_conf, mock_send_function)
        processor.ingest(test_message["data_file"])

        # Main file (1) + related file (1) are still ingested
        assert mock_oncat.Datafile.ingest.call_count == 2
        # But the image batch API is never called, and we don't even scan for images
        mock_oncat.Datafile.batch.assert_not_called()
        mock_images.assert_not_called()


def test_catalog_images_uses_instrument_shared_path():
    """The gate looks for catalog_<INSTRUMENT>.py under the instrument shared dir."""
    test_message = {
        "run_number": "12345",
        "instrument": "VENUS",
        "ipts": "IPTS-99999",
        "facility": "SNS",
        "data_file": "/SNS/VENUS/IPTS-99999/nexus/VENUS_12345.nxs.h5",
    }

    mock_conf = Mock()
    mock_conf.image_filepath_metadata_paths = []
    mock_conf.dev_instrument_shared = ""

    with (
        patch("postprocessing.processors.base_processor.open", create=True),
        patch("postprocessing.processors.oncat_processor.os.path.isfile", return_value=False) as mock_isfile,
    ):
        processor = ONCatProcessor(test_message, mock_conf, Mock())
        processor.catalog_images(Mock(), Mock())

        mock_isfile.assert_called_once_with("/SNS/VENUS/shared/autoreduce/catalog_VENUS.py")


def test_catalog_images_honors_dev_instrument_shared():
    """A configured dev_instrument_shared overrides the standard shared path,
    so the toggle can be exercised locally and in integration tests."""
    test_message = {
        "run_number": "12345",
        "instrument": "VENUS",
        "ipts": "IPTS-99999",
        "facility": "SNS",
        "data_file": "/SNS/VENUS/IPTS-99999/nexus/VENUS_12345.nxs.h5",
    }

    mock_conf = Mock()
    mock_conf.image_filepath_metadata_paths = []
    mock_conf.dev_instrument_shared = "/tmp/dev_shared"

    with (
        patch("postprocessing.processors.base_processor.open", create=True),
        patch("postprocessing.processors.oncat_processor.os.path.isfile", return_value=False) as mock_isfile,
    ):
        processor = ONCatProcessor(test_message, mock_conf, Mock())
        processor.catalog_images(Mock(), Mock())

        mock_isfile.assert_called_once_with("/tmp/dev_shared/catalog_VENUS.py")
