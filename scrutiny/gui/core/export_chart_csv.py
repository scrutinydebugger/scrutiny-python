#    export_chart_csv.py
#        Tools to export graphs to CSV format
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = [
    'make_csv_headers',
    'export_chart_csv_threaded'
]

from datetime import datetime, timedelta
import csv
from pathlib import Path

from PySide6.QtCharts import QLineSeries

import scrutiny
from scrutiny import sdk
from scrutiny import tools
from scrutiny.gui.widgets.graph_signal_tree import AxisContent
from scrutiny.gui.core.persistent_data import gui_persistent_data

from scrutiny.tools.typing import *


def make_csv_headers(
        device: Optional[sdk.DeviceInfo] = None,
        sfd: Optional[sdk.SFDInfo] = None,
        datetime_format: Optional[str] = None
) -> List[List[str]]:
    """Helper to make a graph export CSV file header. Contains metadata about the acquisition
    :param device: Info about the device connected when the graph was acquired
    :param sfd: The Scrutiny Firmware Description loaded when the graph was acquired
    :param datetime_format: The datetime string format to use
    """
    if datetime_format is None:
        datetime_format = gui_persistent_data.global_namespace().long_datetime_format()
    now_str = datetime.now().strftime(datetime_format)
    device_id = "N/A"
    firmware_id = "N/A"
    project_name = "N/A"

    if device is not None:
        device_id = device.device_id

    if sfd is not None:
        firmware_id = sfd.firmware_id
        if sfd.metadata is not None:
            if sfd.metadata.project_name:
                project_name = sfd.metadata.project_name
                if sfd.metadata.version is not None:
                    project_name += " V" + sfd.metadata.version
    return [
        ['Created on', now_str],
        ['Created with', f"Scrutiny V{scrutiny.__version__}"],
        ['Device ID', device_id],       # ID hardcoded in the device firmware
        ['Firmware ID', firmware_id],   # ID inside the SFD. Will normally match the device ID unless the user forced the server to use a different firmware
        ['Project name', project_name]
    ]


def export_chart_csv_threaded(
        filename: Union[str, Path],
        signals: List[AxisContent],
        finished_callback: Callable[[Optional[Exception]], None],
        device: Optional[sdk.DeviceInfo] = None,
        sfd: Optional[sdk.SFDInfo] = None,
        x_axis_name: str = 'Time [s]',
        datetime_zero_sec: Optional[datetime] = None
) -> None:
    """Helper function that export a Scrutiny graph content to a CSV file.
    The function works in a different thread and calls a callback when finished

    :param filename: Name of the output file
    :param signals: The list of signal handles to use for data fetching. Provided by :meth:`GraphSignalTree.get_signals<scrutiny.gui.components.dashboard.common.graph_signal_tree.GraphSignalTree.get_signals>`
    :param finished_callback: A callback to be called when the job is finished or an error occured
    :param device: Info about the device connected when the graph was acquired. Will be added to the CSV header
    :param sfd: The Scrutiny Firmware Description loaded when the graph was acquired. Will be added to the CSV header
    :param x_axis_name: Name of the X axis
    :param datetime_zero_sec: The datetime associated with time 0. When provided, adds an absolute time column shown as datetime.
    """

    DATETIME_HEADER = 'Datetime'

    series_fqn: List[str] = []
    series_list: List[QLineSeries] = []

    for axis in signals:
        series_fqn.extend([item.fqn for item in axis.signal_items])
        series_list.extend([item.series() for item in axis.signal_items])

    file_headers = make_csv_headers(device, sfd)
    series_index = [0 for i in range(len(series_list))]
    series_points = [series.points() for series in series_list]
    actual_vals: List[Optional[float]] = [None] * len(series_list)
    datetime_format = gui_persistent_data.global_namespace().long_datetime_format()

    def save_method() -> None:
        error: Optional[Exception] = None
        try:
            with open(filename, 'w', encoding='utf8', newline='\n') as f:
                writer = csv.writer(f, delimiter=',', quotechar='"', escapechar='\\', quoting=csv.QUOTE_NONNUMERIC)
                # Handle file headers : i.e. metadata about the acquisition
                for file_header in file_headers:
                    writer.writerow(file_header)

                if len(file_headers) > 0:
                    writer.writerow([])
                done = False
                headers: List[str] = []
                watchable_paths: List[str] = []

                # Make the table headers
                if datetime_zero_sec is not None:
                    headers.append(DATETIME_HEADER)
                    watchable_paths.append("")
                headers.extend([x_axis_name] + [series.name() for series in series_list] + ["New Values"])
                watchable_paths.extend([""] + series_fqn + [""])

                writer.writerow(watchable_paths)    # Full path to the watchable
                writer.writerow(headers)            # Nice name for the watchable
                while True:  # Will break when all series are dumped. they might not have the same number of points
                    x: Optional[float] = None
                    done = True
                    for i in range(len(series_list)):
                        if series_index[i] < len(series_points[i]):
                            done = False
                            point = series_points[i][series_index[i]]
                            if x is None:
                                x = point.x()
                            x = min(x, point.x())
                    if done:
                        break
                    assert x is not None

                    new_points_indicator: List[str] = []
                    row: List[Optional[Union[float, str]]] = []
                    if datetime_zero_sec is not None:
                        abs_time = datetime_zero_sec + timedelta(seconds=x)
                        row.append(abs_time.strftime(datetime_format))
                    row.append(x)
                    for i in range(len(series_list)):
                        val = None
                        if series_index[i] < len(series_points[i]):
                            point = series_points[i][series_index[i]]
                            if point.x() == x:
                                val = point.y()
                                series_index[i] += 1
                        if val is None:
                            val = actual_vals[i]
                            new_points_indicator.append('0')
                        else:
                            actual_vals[i] = val
                            new_points_indicator.append('1')
                        row.append(val)

                    row.append(','.join(new_points_indicator))

                    writer.writerow(row)
        except Exception as e:
            error = e
        finally:
            if finished_callback is not None:
                finished_callback(error)

    tools.run_in_thread(save_method)
