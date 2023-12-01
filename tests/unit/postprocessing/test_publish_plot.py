from postprocessing import publish_plot
import pytest
from tests.conftest import getDevConfigurationFile


def test_get_user():
    info = publish_plot.get_user(getDevConfigurationFile())
    assert info
    # these aren't sepecified so just make sure the keys are present
    assert "username" in info
    assert "password" in info


# plot1d test data
data1d = [[0, 1], [2, 3], [4, 5]]


@pytest.mark.parametrize("x_log, y_log", [(False, False), (True, True)])
def test_plot1d(x_log, y_log):
    # single spectrum
    assert publish_plot.plot1d(
        run_number=1234,
        instrument="instr",
        data_list=[data1d],
        x_log=x_log,
        y_log=y_log,
        publish=False,
    )
    # two spectra
    assert publish_plot.plot1d(
        run_number=1234, instrument="instr", data_list=[data1d, data1d], publish=False
    )


def test_plot1d_fail():
    with pytest.raises(RuntimeError):
        publish_plot.plot1d(
            run_number=1234, instrument="instr", data_list=None, publish=False
        )

    # when plot fails to publish the function returns None
    assert not publish_plot.plot1d(
        run_number=1234, instrument="instr", data_list=[data1d], publish=True
    )


data2d = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]


@pytest.mark.parametrize("x_log, y_log", [(False, False), (True, True)])
def test_plot_heatmap(x_log, y_log):
    assert publish_plot.plot_heatmap(
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

    assert not publish_plot.plot_heatmap(
        1234, data2d[0], data2d[1], data2d[2], instrument="instr", publish=True
    )


if __name__ == "__main__":
    pytest.main([__file__])
