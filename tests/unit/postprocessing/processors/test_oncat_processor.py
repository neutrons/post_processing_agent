from unittest.mock import Mock, patch

from postprocessing.processors.oncat_processor import (
    ONCatProcessor,
    batches,
    related_files,
    image_files,
)


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


def test_image_files_no_metadata():
    """Test image_files when metadata path doesn't exist"""
    mock_datafile = Mock()
    mock_datafile.facility = "SNS"
    mock_datafile.instrument = "VENUS"
    mock_datafile.experiment = "IPTS-99999"
    mock_datafile.get.return_value = None  # No metadata found

    metadata_paths = ["metadata.entry.daslogs.bl10:exp:im:imagefilepath.value"]
    result = image_files(mock_datafile, metadata_paths)
    assert result == []


def test_image_files_metadata_not_a_directory():
    """Test image_files when metadata points to non-existent directory"""
    mock_datafile = Mock()
    mock_datafile.facility = "SNS"
    mock_datafile.instrument = "VENUS"
    mock_datafile.experiment = "IPTS-99999"
    mock_datafile.get.return_value = "images"

    with patch("os.path.isdir") as mock_isdir:
        mock_isdir.return_value = False

        metadata_paths = ["metadata.entry.daslogs.bl10:exp:im:imagefilepath.value"]
        result = image_files(mock_datafile, metadata_paths)
        assert result == []


def test_image_files_single_directory():
    """Test image_files with single directory containing FITS and TIFF files"""
    mock_datafile = Mock()
    mock_datafile.facility = "SNS"
    mock_datafile.instrument = "VENUS"
    mock_datafile.experiment = "IPTS-99999"
    mock_datafile.get.return_value = "images"

    with patch("os.path.isdir") as mock_isdir, patch("glob.glob") as mock_glob:
        mock_isdir.return_value = True

        def glob_side_effect(pattern):
            if pattern.endswith("*.fits"):
                return [
                    "/SNS/VENUS/IPTS-99999/images/image_001.fits",
                    "/SNS/VENUS/IPTS-99999/images/image_002.fits",
                ]
            elif pattern.endswith("*.tiff"):
                return ["/SNS/VENUS/IPTS-99999/images/image_003.tiff"]
            return []

        mock_glob.side_effect = glob_side_effect

        metadata_paths = ["metadata.entry.daslogs.bl10:exp:im:imagefilepath.value"]
        result = image_files(mock_datafile, metadata_paths)

        assert len(result) == 3
        assert "/SNS/VENUS/IPTS-99999/images/image_001.fits" in result
        assert "/SNS/VENUS/IPTS-99999/images/image_002.fits" in result
        assert "/SNS/VENUS/IPTS-99999/images/image_003.tiff" in result


def test_image_files_multiple_directories():
    """Test image_files with multiple directories (list of subdirectories)"""
    mock_datafile = Mock()
    mock_datafile.facility = "SNS"
    mock_datafile.instrument = "VENUS"
    mock_datafile.experiment = "IPTS-99999"
    mock_datafile.get.return_value = ["images/batch1", "images/batch2"]

    with patch("os.path.isdir") as mock_isdir, patch("glob.glob") as mock_glob:
        mock_isdir.return_value = True

        def glob_side_effect(pattern):
            if "batch1" in pattern and pattern.endswith("*.fits"):
                return ["/SNS/VENUS/IPTS-99999/images/batch1/image_001.fits"]
            elif "batch2" in pattern and pattern.endswith("*.tiff"):
                return ["/SNS/VENUS/IPTS-99999/images/batch2/image_002.tiff"]
            return []

        mock_glob.side_effect = glob_side_effect

        metadata_paths = ["metadata.entry.daslogs.bl10:exp:im:imagefilepath.value"]
        result = image_files(mock_datafile, metadata_paths)

        assert len(result) == 2
        assert "/SNS/VENUS/IPTS-99999/images/batch1/image_001.fits" in result
        assert "/SNS/VENUS/IPTS-99999/images/batch2/image_002.tiff" in result


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

    mock_send_function = Mock()

    with (
        patch("postprocessing.processors.base_processor.open", create=True),
        patch("postprocessing.processors.oncat_processor.pyoncat.ONCat") as mock_oncat_class,
        patch("postprocessing.processors.oncat_processor.related_files") as mock_related,
        patch("postprocessing.processors.oncat_processor.image_files") as mock_images,
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

    mock_send_function = Mock()

    # Create 125 image files (should be split into 3 batches: 50, 50, 25)
    many_images = [f"/SNS/VENUS/IPTS-99999/images/image_{i:04d}.fits" for i in range(125)]

    with (
        patch("postprocessing.processors.base_processor.open", create=True),
        patch("postprocessing.processors.oncat_processor.pyoncat.ONCat") as mock_oncat_class,
        patch("postprocessing.processors.oncat_processor.related_files") as mock_related,
        patch("postprocessing.processors.oncat_processor.image_files") as mock_images,
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
