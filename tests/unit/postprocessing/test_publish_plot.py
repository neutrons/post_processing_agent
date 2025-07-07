from plot_publisher import plot1d, plot_heatmap
import pytest


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
    assert plot1d(
        run_number=1234, instrument="instr", data_list=[data1d, data1d], publish=False
    )


def test_plot1d_fail():
    with pytest.raises(RuntimeError):
        plot1d(run_number=1234, instrument="instr", data_list=None, publish=False)

    # when plot fails to publish the function returns None
    assert not plot1d(
        run_number=1234, instrument="instr", data_list=[data1d], publish=True
    )


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

    assert not plot_heatmap(
        1234, data2d[0], data2d[1], data2d[2], instrument="instr", publish=True
    )


if __name__ == "__main__":
    pytest.main([__file__])
