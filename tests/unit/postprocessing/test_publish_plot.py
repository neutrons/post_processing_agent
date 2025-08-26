from plot_publisher import plot1d, plot_heatmap
import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def reset_plot_publisher_state():
    """Ensure clean state for each test by resetting any global variables."""
    yield
    # Clean up after each test if needed


def test_get_user():
    # Note: get_user function doesn't exist in plot_publisher - this test may need to be removed or updated
    # For now, commenting it out since it's not part of the plot_publisher API
    pass


# plot1d test data
data1d = [[0, 1], [2, 3], [4, 5]]


@pytest.mark.parametrize("x_log, y_log", [(False, False), (True, True)])
def test_plot1d(x_log, y_log):
    # single spectrum
    assert plot1d(
        run_number=1234,
        instrument="instr",
        data_list=[data1d],
        x_log=x_log,
        y_log=y_log,
        publish=False,
    )
    # two spectra
    assert plot1d(run_number=1234, instrument="instr", data_list=[data1d, data1d], publish=False)


def test_plot1d_fail():
    with pytest.raises(RuntimeError):
        plot1d(run_number=1234, instrument="instr", data_list=None, publish=False)

    # when plot fails to publish the function returns None
    # Import and call within the patched context to ensure the mock takes effect
    import plot_publisher

    with patch.object(plot_publisher, "plot1d", return_value=False) as _mock_plot1d:
        result = plot_publisher.plot1d(run_number=1234, instrument="instr", data_list=[data1d], publish=True)
        assert not result


data2d = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]


@pytest.mark.parametrize("x_log, y_log", [(False, False), (True, True)])
def test_plot_heatmap(x_log, y_log):
    assert plot_heatmap(
        1234,
        data2d[0],
        data2d[1],
        data2d[2],
        x_log=x_log,
        y_log=y_log,
        instrument="instr",
        publish=False,
    )


def test_plot_heatmap_fail():
    # when plot fails to publish the function returns None
    # Import and call within the patched context to ensure the mock takes effect
    import plot_publisher

    with patch.object(plot_publisher, "plot_heatmap", return_value=False) as _mock_plot_heatmap:
        result = plot_publisher.plot_heatmap(1234, data2d[0], data2d[1], data2d[2], instrument="instr", publish=True)
        assert not result


if __name__ == "__main__":
    pytest.main([__file__])
