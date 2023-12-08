# pylint: disable=too-many-arguments, too-many-locals, invalid-name
"""
    Utility functions to post plot data
"""

import sys
import logging
from postprocessing.Configuration import Configuration, CONFIG_FILE
import string
import requests
import urllib3

urllib3.disable_warnings()


def get_user(config_file=None):
    """
    Return username and password from config file
    """
    if config_file is None:
        config_file = CONFIG_FILE
    config = Configuration(config_file)
    return {
        "username": config.publisher_username,
        "password": config.publisher_password,
    }


def publish_plot(instrument, run_number, files, config_file=None):
    """
    Files should be a dict of file contents to publish e.g. files={'file': div}
    """
    if config_file is None:
        config_file = CONFIG_FILE
    config = Configuration(config_file)

    url_template = string.Template(config.publish_url)
    url = url_template.substitute(instrument=instrument, run_number=str(run_number))
    request = requests.post(
        url,
        data={
            "username": config.publisher_username,
            "password": config.publisher_password,
        },
        files=files,
        verify=False,
    )

    status_code = request.status_code
    if status_code != 200:
        raise RuntimeError(f"post returned {status_code}")
    return request


def plot1d(
    run_number,
    data_list,
    data_names=None,
    x_title="",
    y_title="",
    x_log=False,
    y_log=False,
    instrument="",
    show_dx=True,
    title="",
    publish=True,
):
    """
    Produce a 1D plot
    @param data_list: list of traces [ [x1, y1], [x2, y2], ...]
    @param data_names: name for each trace, for the legend
    """
    from plotly.offline import plot
    import plotly.graph_objs as go

    # Create traces
    if not isinstance(data_list, list):
        raise RuntimeError("plot1d: data_list parameter is expected to be a list")

    # Catch the case where the list is in the format [x y]
    data = []
    show_legend = False
    if len(data_list) == 2 and not isinstance(data_list[0], list):
        label = ""
        if isinstance(data_names, list) and len(data_names) == 1:
            label = data_names[0]
            show_legend = True
        data = [go.Scatter(name=label, x=data_list[0], y=data_list[1])]
    else:
        for i in range(len(data_list)):
            label = ""
            if isinstance(data_names, list) and len(data_names) == len(data_list):
                label = data_names[i]
                show_legend = True
            err_x = {}
            err_y = {}
            if len(data_list[i]) >= 3:
                err_y = dict(type="data", array=data_list[i][2], visible=True)
            if len(data_list[i]) >= 4:
                err_x = dict(type="data", array=data_list[i][3], visible=True)
                if show_dx is False:
                    err_x["thickness"] = 0
            data.append(
                go.Scatter(
                    name=label,
                    x=data_list[i][0],
                    y=data_list[i][1],
                    error_x=err_x,
                    error_y=err_y,
                )
            )

    x_layout = dict(
        title=x_title,
        zeroline=False,
        exponentformat="power",
        showexponent="all",
        showgrid=True,
        showline=True,
        mirror="all",
        ticks="inside",
    )
    if x_log:
        x_layout["type"] = "log"
    y_layout = dict(
        title=y_title,
        zeroline=False,
        exponentformat="power",
        showexponent="all",
        showgrid=True,
        showline=True,
        mirror="all",
        ticks="inside",
    )
    if y_log:
        y_layout["type"] = "log"

    layout = go.Layout(
        showlegend=show_legend,
        autosize=True,
        width=600,
        height=400,
        margin=dict(t=40, b=40, l=80, r=40),
        hovermode="closest",
        bargap=0,
        xaxis=x_layout,
        yaxis=y_layout,
        title=title,
    )

    fig = go.Figure(data=data, layout=layout)
    plot_div = plot(fig, output_type="div", include_plotlyjs=False, show_link=False)
    if publish:
        try:
            return publish_plot(instrument, run_number, files={"file": plot_div})
        except:  # noqa: E722
            logging.error("Publish plot failed: %s", sys.exc_info()[1])
            return None
    else:
        return plot_div


def plot_heatmap(
    run_number,
    x,
    y,
    z,
    x_title="",
    y_title="",
    surface=False,
    x_log=False,
    y_log=False,
    instrument="",
    title="",
    publish=True,
):
    """
    Produce a 2D plot
    """
    from plotly.offline import plot
    import plotly.graph_objs as go

    x_layout = dict(
        title=x_title,
        zeroline=False,
        exponentformat="power",
        showexponent="all",
        showgrid=True,
        showline=True,
        mirror="all",
        ticks="inside",
    )
    if x_log:
        x_layout["type"] = "log"

    y_layout = dict(
        title=y_title,
        zeroline=False,
        exponentformat="power",
        showexponent="all",
        showgrid=True,
        showline=True,
        mirror="all",
        ticks="inside",
    )
    if y_log:
        y_layout["type"] = "log"

    layout = go.Layout(
        showlegend=False,
        autosize=True,
        width=600,
        height=500,
        margin=dict(t=40, b=40, l=80, r=40),
        hovermode="closest",
        bargap=0,
        xaxis=x_layout,
        yaxis=y_layout,
        title=title,
    )

    colorscale = [
        [0, "rgb(0,0,131)"],
        [0.125, "rgb(0,60,170)"],
        [0.375, "rgb(5,255,255)"],
        [0.625, "rgb(255,255,0)"],
        [0.875, "rgb(250,0,0)"],
        [1, "rgb(128,0,0)"],
    ]
    trace = go.Heatmap(
        z=z,
        x=x,
        y=y,
        autocolorscale=False,  # type=plot_type,
        hoverinfo="none",
        colorscale=colorscale,
    )
    fig = go.Figure(data=[trace], layout=layout)
    plot_div = plot(fig, output_type="div", include_plotlyjs=False, show_link=False)

    # The following would remove the hover options, which are not accessible through python
    # https://github.com/plotly/plotly.js/blob/master/src/components/modebar/buttons.js
    # plot_div = plot_div.replace('modeBarButtonsToRemove:[]',
    #                            'modeBarButtonsToRemove:["hoverClosestCartesian",
    #                                                     "hoverCompareCartesian"]')

    if publish:
        try:
            return publish_plot(instrument, run_number, files={"file": plot_div})
        except:  # noqa: E722
            logging.error("Publish plot failed: %s", sys.exc_info()[1])
            return None
    else:
        return plot_div
