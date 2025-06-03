#    manual_test_chart.py
#        A test application to check the visual rendring of a chart
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

if __name__ != '__main__':
    raise RuntimeError("This script is expected to run from the command line")

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from manual_test_base import make_manual_test_app
app = make_manual_test_app()

import logging
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QSplitter, QLabel
from PySide6.QtCore import Qt, QPointF, QRectF
from scrutiny.gui.dialogs.device_config_dialog import DeviceConfigDialog
from scrutiny import sdk
from scrutiny.gui.widgets.base_chart import *
from scrutiny.gui.widgets.graph_signal_tree import GraphSignalTree, ChartSeriesWatchableStandardItem
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from test.gui.fake_server_manager import FakeServerManager, ServerConfig
from scrutiny.core.basic_types import WatchableType
from scrutiny.tools.typing import *
import random


def config_applied(dialog: DeviceConfigDialog):
    link_type, config = dialog.get_type_and_config()
    logging.info(f"Config applied: Link: {link_type}. Config : {config}")


window = QMainWindow()
window.setGeometry(0, 0, 1200, 800)
registry = WatchableRegistry()
xlabel = QLabel()
xlabel.setText("N/A")


def x_val_write(val: float, enabled: bool):
    if enabled:
        xlabel.setText(str(val))
    else:
        xlabel.setText("N/A")


server_manager = FakeServerManager(registry)

signal_tree = GraphSignalTree(window, registry, has_value_col=True)
right_side = QWidget()
right_vlayout = QVBoxLayout(right_side)
right_vlayout.setContentsMargins(0, 0, 0, 0)
right_vlayout.addWidget(xlabel)
right_vlayout.addWidget(signal_tree)

chart = ScrutinyChart()
chartview = ScrutinyChartView(chart, window)
chart_toolbar = ScrutinyChartToolBar(chartview)

chartview.configure_chart_cursor(signal_tree, x_val_write)
signal_tree.model().removeRows(0, signal_tree.model().rowCount())

item1 = ChartSeriesWatchableStandardItem(WatchableType.RuntimePublishedValue, 'AAAA', '/rpv/rpv.b/rpv.b.b')
item2 = ChartSeriesWatchableStandardItem(WatchableType.Alias, 'BBBB', '/alias/alias.a/alias.a.b')
item3 = ChartSeriesWatchableStandardItem(WatchableType.Variable, 'CCCC', '/var/var.a/var.a.c')
item4 = ChartSeriesWatchableStandardItem(WatchableType.Variable, 'DDDD', '/var/var.b/var.b.b')

axis1 = signal_tree.model().add_axis("Axis 1")
axis1.appendRow(signal_tree.model().make_watchable_item_row(item1))
axis1.appendRow(signal_tree.model().make_watchable_item_row(item2))
axis2 = signal_tree.model().add_axis("Axis 2")
axis2.appendRow(signal_tree.model().make_watchable_item_row(item3))
axis2.appendRow(signal_tree.model().make_watchable_item_row(item4))

splitter = QSplitter(Qt.Orientation.Horizontal, window)
splitter.addWidget(chartview)
splitter.addWidget(right_side)
splitter.setSizes([1000, 200])
window.setCentralWidget(splitter)


# Fill the registry with dummy data by enabling a simulated device
server_manager.start(ServerConfig("...", 0))
server_manager.simulate_server_connect()
server_manager.simulate_device_ready()
server_manager.simulate_sfd_loaded()

xaxis = ScrutinyValueAxisWithMinMax()
xaxis.setTitleText("Test graph")
xaxis.setTitleVisible(True)
chart.setAxisX(xaxis)
yaxes: List[ScrutinyValueAxisWithMinMax] = []


def set_zoombox_slot(zoombox: QRectF):
    xaxis.apply_zoombox_x(zoombox)
    selected_axis_items = signal_tree.get_selected_axes(include_if_signal_is_selected=True)
    selected_axis_ids = [id(item.axis()) for item in selected_axis_items]
    for yaxis in yaxes:
        if id(yaxis) in selected_axis_ids or len(selected_axis_ids) == 0:
            # Y-axis is not bound by the value. we leave the freedom to the user to unzoom like crazy
            # We rely on the capacity to reset the zoom to come back to something reasonable if the user gets lost
            yaxis.apply_zoombox_y(zoombox)
    chartview.update()


chartview.allow_zoom(True)
chartview.allow_drag(True)
chartview.signals.zoombox_selected.connect(set_zoombox_slot)
chartview.signals.graph_dragged.connect(chart.apply_drag)


def build_chart():

    chart.removeAllSeries()
    for yaxis in yaxes:
        chart.removeAxis(yaxis)
    yaxes.clear()

    chart_toolbar.show()

    signals = signal_tree.get_signals()
    xdata = list(range(20))
    for axis_content in signals:
        yaxis = ScrutinyValueAxisWithMinMax()
        yaxis.setTitleText(axis_content.axis_name)
        yaxis.set_minval(-1)
        yaxis.set_maxval(1)
        yaxis.autoset_range(0.2)
        yaxes.append(yaxis)
        axis_content.axis_item.attach_axis(yaxis)
        chart.addAxis(yaxis, Qt.AlignmentFlag.AlignRight)
        for item in axis_content.signal_items:
            series = ScrutinyLineSeries(chart)
            chart.addSeries(series)

            item.attach_series(series)

            series.setName(item.text())
            series.attachAxis(xaxis)
            series.attachAxis(yaxis)

            data = [QPointF(x, random.random() * 2 - 1) for x in xdata]

            series.replace(data)

        xaxis.set_minval(min(xdata))
        xaxis.set_maxval(max(xdata))
        xaxis.autoset_range()
        chart_toolbar.disable_chart_cursor()


window.show()
build_chart()

sys.exit(app.exec())
