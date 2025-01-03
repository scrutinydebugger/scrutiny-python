#    base_chart.py
#        Some customized extensions of the QT Charts for the Scrutiny GUI
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = [
    'ScrutinyLineSeries',
    'ScrutinyValueAxis', 
    'ScrutinyChartCallout',
    'ScrutinyChartView'
]

import enum
from pathlib import Path
import os
import csv
from datetime import datetime

from PySide6.QtCharts import QLineSeries, QValueAxis, QChart, QChartView, QXYSeries
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget, QMenu, QFileDialog, QMessageBox
from PySide6.QtGui import QFont, QPainter, QFontMetrics, QColor, QContextMenuEvent
from PySide6.QtCore import QObject, QPointF, QRect, QRectF, Qt

import scrutiny
from scrutiny import tools
from scrutiny import sdk
from scrutiny.gui.core.preferences import gui_preferences
from scrutiny.gui.themes import get_theme_prop, ScrutinyThemeProperties
from scrutiny.gui import assets

from typing import Any, Optional, List, cast

class ScrutinyLineSeries(QLineSeries):
    def __init__(self, parent:QObject) -> None:
        super().__init__(parent)

    def emphasize(self) -> None:
        pen = self.pen()
        pen.setWidth(get_theme_prop(ScrutinyThemeProperties.CHART_EMPHASIZED_SERIES_WIDTH))
        self.setPen(pen)
    
    def deemphasize(self) -> None:
        pen = self.pen()
        pen.setWidth(get_theme_prop(ScrutinyThemeProperties.CHART_NORMAL_SERIES_WIDTH))
        self.setPen(pen)

class ScrutinyValueAxis(QValueAxis):

    def __init__(self, parent:QObject) -> None:
        super().__init__(parent)

    def emphasize(self) -> None:
        font = self.titleFont()
        font.setBold(True)
        self.setTitleFont(font)
    
    def deemphasize(self) -> None:
        font = self.titleFont()
        font.setBold(False)
        self.setTitleFont(font)


class ScrutinyChartCallout(QGraphicsItem):

    CALLOUT_RECT_DIST = 10  # Distance between point marker and 
    PADDING = 5             # padding between text and callout border

    class DisplaySide(enum.Enum):
        Above = enum.auto()
        Below = enum.auto()


    _chart:QChart
    _text:str
    _point_location_on_chart:QPointF
    _font:QFont
    _text_rect:QRectF
    _rect:QRectF
    _color:QColor
    _side:DisplaySide
    _marker_radius : int


    def __init__(self, chart:QChart) -> None:
        super().__init__(chart)
        self._chart = chart
        self._text = ''
        self._point_location_on_chart = QPointF()
        self._font  = QFont()
        self._text_rect = QRectF()
        self._callout_rect = QRectF()
        self._bounding_box = QRectF()
        self._color = QColor()
        self._updown_side = self.DisplaySide.Above
        self._marker_radius = 0
        self.hide()
        self.setZValue(11)

    def _compute_geometry(self) -> None:

        self.prepareGeometryChange()
        metrics = QFontMetrics(self._font)
        self._text_rect = QRectF(metrics.boundingRect(QRect(0, 0, 150, 150), Qt.AlignmentFlag.AlignLeft, self._text))
        self._text_rect.translate(self.PADDING, self.PADDING)
        self._callout_rect = QRectF(self._text_rect.adjusted(-self.PADDING, -self.PADDING, self.PADDING, self.PADDING))
        self._marker_radius = get_theme_prop(ScrutinyThemeProperties.CHART_CALLOUT_MARKER_RADIUS)

        chart_h = self._chart.size().height()
        chart_w = self._chart.size().width()
        if self._point_location_on_chart.y() <= chart_h/3:
            self._updown_side = self.DisplaySide.Below
        elif self._point_location_on_chart.y() >= chart_h*2/3:
            self._updown_side = self.DisplaySide.Above
        else:
            pass    # Keep last. Makes an hysteresis
        
        callout_rect_origin = QPointF(self._point_location_on_chart)
        bounding_box_vertical_offset = self._marker_radius + self.CALLOUT_RECT_DIST
        if self._updown_side == self.DisplaySide.Above:
            callout_rect_origin -= QPointF(0, self._callout_rect.height() + self.CALLOUT_RECT_DIST)
            self._bounding_box = self._callout_rect.adjusted(0,0,0,bounding_box_vertical_offset)
        elif self._updown_side == self.DisplaySide.Below:
            callout_rect_origin += QPointF(0, self.CALLOUT_RECT_DIST)
            self._bounding_box = self._callout_rect.adjusted(0,-bounding_box_vertical_offset,0,0)
        
        callout_rect_origin -= QPointF(self._callout_rect.width()/2,0)  # Handle left overflow
        if callout_rect_origin.x() < 0:
            callout_rect_origin += QPointF(abs(callout_rect_origin.x()), 0)
        
        rect_right_x = callout_rect_origin.x() + self._callout_rect.width() # Handle right overflow
        if rect_right_x > chart_w:
            callout_rect_origin -= QPointF(rect_right_x - chart_w, 0)


        self.setPos(callout_rect_origin)


    def set_content(self, pos:QPointF, text:str, color:QColor) -> None:
        self._point_location_on_chart = pos
        self._text = text
        self._color = color
        self._compute_geometry()
       

    def boundingRect(self) -> QRectF:
        # Inform QT about the size we need
        return self._bounding_box

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget]=None) -> None:
        painter.setBrush(self._color)   # Fill color
        painter.setPen(self._color)     # Border color
        painter.drawRoundedRect(self._callout_rect, 5, 5)
        anchor = QPointF(self.mapFromParent(self._point_location_on_chart))
        painter.setPen(QColor(0,0,0))     # Border color
        painter.drawEllipse(anchor, self._marker_radius, self._marker_radius)
        painter.setPen(QColor(0,0,0))
        painter.drawText(self._text_rect, self._text)




class ScrutinyChartView(QChartView):

    _allow_save_img:bool
    _allow_save_csv:bool

    _source_firmware_id:Optional[str]               # Used for CSV logging
    _source_firmware_sfd_metadata:Optional[sdk.SFDMetadata]     # USed for CSV logging

    @tools.copy_type(QChartView.__init__)
    def __init__(self, *args:Any, **kwargs:Any) -> None:
        super().__init__(*args, **kwargs)
        self._allow_save_img = False
        self._allow_save_csv = False
        self._source_firmware_id = None
        self._source_firmware_sfd_metadata = None

    def allow_save_img(self, val:bool) -> None:
        self._allow_save_img=val

    def allow_save_csv(self, val:bool) -> None:
        self._allow_save_csv=val

    def set_source_firmware(self, firmware_id:str, sfd_metadata:Optional[sdk.SFDMetadata] = None) -> None:
        self._source_firmware_id = firmware_id
        self._source_firmware_sfd_metadata = sfd_metadata

    def clear_source_firmware(self) -> None:
        self._source_firmware_id = None
        self._source_firmware_sfd_metadata = None

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        context_menu = QMenu(self)

        save_img_action = context_menu.addAction(assets.load_icon(assets.Icons.Picture), "Save as image")
        save_img_action.triggered.connect(self.save_image_slot)
        save_img_action.setEnabled(self._allow_save_img)

        save_csv_action = context_menu.addAction(assets.load_icon(assets.Icons.CSV), "Save as CSV")
        save_csv_action.triggered.connect(self.save_csv_slot)
        save_csv_action.setEnabled(self._allow_save_img)
        context_menu.popup(self.mapToGlobal(event.pos()))

    def save_image_slot(self) -> None:
        if not self._allow_save_img:
            return 
        
        try:
            pix = self.grab()
            save_dir = gui_preferences.default().get_last_save_dir_or_workdir()
            filename, _ = QFileDialog.getSaveFileName(self, "Save", str(save_dir), "*.png")
            gui_preferences.default().set_last_save_dir(Path(os.path.dirname(filename)))
            if not filename.lower().endswith('.png'):
                filename += ".png"
            
            pix.save(filename, "png", 100)
        except Exception as e:
            msgbox = QMessageBox(self)
            msgbox.setStandardButtons(QMessageBox.StandardButton.Close)
            msgbox.setWindowTitle("Failed to save")
            msgbox.setText(f"Failed to save the graph.\n {e.__class__.__name__}:{e}")
            msgbox.show()

    def save_csv_slot(self) -> None:
        if not self._allow_save_csv:
            return 
        try:
            chart = self.chart()
            for series in chart.series():
                if not isinstance(series, QXYSeries):    # QLineSeries is a QXYSeries
                    raise NotImplementedError(f"Export to CSV of data series of type {series.__class__.__name__} is not supported.")
            
            series_list = cast(List[QXYSeries], chart.series())
            
            save_dir = gui_preferences.default().get_last_save_dir_or_workdir()
            filename, _ = QFileDialog.getSaveFileName(self, "Save", str(save_dir), "*.png")
            gui_preferences.default().set_last_save_dir(Path(os.path.dirname(filename)))
            if not filename.lower().endswith('.csv'):
                filename += ".csv"

            now_str = datetime.now().strftime(gui_preferences.default().long_datetime_format())
            firmware_id = "N/A"
            project_name = "N/A"

            if self._source_firmware_id is not None:
                firmware_id = self._source_firmware_id

            if self._source_firmware_sfd_metadata is not None:
                if self._source_firmware_sfd_metadata.project_name is not None:
                    project_name = self._source_firmware_sfd_metadata.project_name
                    if self._source_firmware_sfd_metadata.version is not None:
                        project_name += " V" + self._source_firmware_sfd_metadata.version

            with open(filename, 'w', encoding='utf8', newline='\n') as f:
                writer = csv.writer(f, delimiter=',', quotechar='"', escapechar='\\')
                writer.writerow(['Created on', now_str])
                writer.writerow(['Created with', f"Scrutiny V{scrutiny.__version__}"])
                writer.writerow(['Firmware ID', firmware_id])
                writer.writerow(['Project name', project_name])

                writer.writerow([])

                chart = self.chart()
                
                done = False

                series_index = [0 for i in range(len(series_list))]
                series_points = [series.points() for series in series_list]
                
                # TODO : Add full signal name
                # TODO : Add real time
                headers = ["Time (s)"] + [series.name() for series in series_list]
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
                        series = series_list[i]
                        val = None
                        if series_index[i] < len(series_points[i]):
                            point = series_points[i][series_index[i]]
                            if point.x() == x:
                                val = point.y()
                                series_index[i]+=1
                        
                        row.append(val)

                    writer.writerow(row)


                    


        except Exception as e:
            msgbox = QMessageBox(self)
            msgbox.setStandardButtons(QMessageBox.StandardButton.Close)
            msgbox.setWindowTitle("Failed to save")
            msgbox.setText(f"Failed to save the graph.\n {e.__class__.__name__}:{e}")
            msgbox.show()
