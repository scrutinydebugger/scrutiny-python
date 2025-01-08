from datetime import datetime
import csv


from PySide6.QtWidgets import QMessageBox
from PySide6.QtCharts import QLineSeries

import scrutiny
from scrutiny import sdk
from scrutiny.gui.dashboard_components.common.graph_signal_tree import AxisContent
from scrutiny.gui.core.preferences import gui_preferences

from typing import Optional, List, cast

def export_chart_csv(
        filename:str, 
        signals:List[AxisContent], 
        firmware_id:Optional[str] = None,
        sfd_metadata:Optional[sdk.SFDMetadata] = None) -> None:
    
    series_fqn:List[str] = []
    series_list:List[QLineSeries] = []

    for axis in signals:
        series_fqn.extend([item.fqn for item in axis.signal_items])
        series_list.extend([item.series() for item in axis.signal_items])
    
    now_str = datetime.now().strftime(gui_preferences.default().long_datetime_format())
    if firmware_id is None:
        firmware_id = "N/A"
    project_name = "N/A"

    if sfd_metadata is not None:
        if sfd_metadata.project_name is not None:
            project_name = sfd_metadata.project_name
            if sfd_metadata.version is not None:
                project_name += " V" + sfd_metadata.version

    with open(filename, 'w', encoding='utf8', newline='\n') as f:
        writer = csv.writer(f, delimiter=',', quotechar='"', escapechar='\\')
        writer.writerow(['Created on', now_str])
        writer.writerow(['Created with', f"Scrutiny V{scrutiny.__version__}"])
        writer.writerow(['Firmware ID', firmware_id])
        writer.writerow(['Project name', project_name])

        writer.writerow([])            
        done = False

        series_index = [0 for i in range(len(series_list))]
        series_points = [series.points() for series in series_list]
        
        # TODO : Add real time
        fqns = [""] + [fqn for fqn in series_fqn]
        headers = ["Time (s)"] + [series.name() for series in series_list]
        writer.writerow(fqns)
        writer.writerow(headers)

        # TODO : Save in background thread
        while True:
            x:Optional[float] = None 
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

            row:List[Optional[float]] = [x]
            for i in range(len(series_list)):
                val = None
                if series_index[i] < len(series_points[i]):
                    point = series_points[i][series_index[i]]
                    if point.x() == x:
                        val = point.y()
                        series_index[i]+=1
                
                row.append(val)

            writer.writerow(row)
