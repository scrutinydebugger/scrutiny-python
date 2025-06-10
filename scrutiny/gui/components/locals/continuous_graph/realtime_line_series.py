#    realtime_line_series.py
#        A extension of the QLineSeries meant for real-time graph. It includes a decimator
#        and some inline stats computation
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['RealTimeScrutinyLineSeries']

from PySide6.QtCore import QPointF

from scrutiny.gui.tools.min_max import MinMax
from scrutiny.gui.widgets.base_chart import ScrutinyLineSeries
from scrutiny.gui.components.locals.continuous_graph.decimator import GraphMonotonicNonUniformMinMaxDecimator

from scrutiny.tools.typing import *


class RealTimeScrutinyLineSeries(ScrutinyLineSeries):
    """Extension of a LineSeries that is meant to display data in real time.
    It has support for decimation and some fancy tricks to kep tracks of min/max
    value with minimal CPU computation"""

    _decimator: GraphMonotonicNonUniformMinMaxDecimator
    """The decimator that keeps the whole dataset and also provides a decimated version of it"""
    _x_minmax: MinMax
    """Min/Max trackerfor the X values"""
    _y_minmax: MinMax
    """Min/Max trackerfor the Y values"""
    _dirty: bool
    """Flag indicating that the output of the decimator has new data ready to be flushed to the chart"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._decimator = GraphMonotonicNonUniformMinMaxDecimator()
        self._x_minmax = MinMax()
        self._y_minmax = MinMax()
        self._dirty = False

    def set_x_resolution(self, resolution: float) -> bool:
        """Set the X width used by the decimator. All the points within a moving window of this size will be clustered together"""
        changed = self._decimator.set_x_resolution(resolution)
        if changed:
            self._dirty = True
        return changed

    def decimation_factor(self) -> float:
        """Provides an estimation of the decimation factor"""
        return self._decimator.decimation_factor()

    def count_decimated_points(self) -> int:
        """Count the number of points at the output of the decimator"""
        return len(self._decimator.get_decimated_buffer())

    def count_all_points(self) -> int:
        """Count the number of points at the input of the decimator (full dataset)"""
        return len(self._decimator.get_input_buffer())

    def add_point(self, point: QPointF) -> int:
        """Adds a point to the decimator input. New output points may or may not be available after

        :param point: The point to add
        :return: The number of new points available at the output. May be bigger than 1
        """
        n = self._decimator.add_point(point)    # Can have 2 points out for a single in (min/max)
        if n > 0:
            # New data available at the output. update the min/max in real time for axis autorange
            start_index = len(self._decimator.get_decimated_buffer()) - n     # Avoid negative slice. Not all container supports it
            for p in self._decimator.get_decimated_buffer()[start_index:]:
                self._y_minmax.update(p.y())
                self._x_minmax.update_max(p.x())
            self._dirty = True
        return n

    def delete_up_to_x_without_flushing(self, x: float) -> None:
        """Delete both input and output data up to a value of X specified. Assumes a monotonic X axis

        :param x: The minimum X value allowed. Any points with a X value smaller than this will get deleted

        """
        in_deleted, out_deleted = self._decimator.delete_data_up_to_x(x)
        if out_deleted > 0:  # That affects the visible graph
            self._dirty = True

    def get_last_x(self) -> Optional[float]:
        """Return the most recent point from the input buffer"""
        buffer = self._decimator.get_input_buffer()
        if len(buffer) == 0:
            return None
        return buffer[-1].x()

    def get_first_x(self) -> Optional[float]:
        """Return the oldest point from the input buffer"""
        buffer = self._decimator.get_input_buffer()
        if len(buffer) == 0:
            return None
        return buffer[0].x()

    def get_last_decimated_x(self) -> Optional[float]:
        """Return the most recent point fromthe output buffer (decimated buffer)"""
        buffer = self._decimator.get_decimated_buffer()
        if len(buffer) == 0:
            return None
        return buffer[-1].x()

    def get_first_decimated_x(self) -> Optional[float]:
        """Return the oldest point fromthe output buffer (decimated buffer)"""
        buffer = self._decimator.get_decimated_buffer()
        if len(buffer) == 0:
            return None
        return buffer[0].x()

    def flush_decimated(self) -> None:
        """Copy the decimator output buffer (decimated) into the chart buffer for display"""
        self.replace(self._decimator.get_decimated_buffer())
        self._dirty = False

    def flush_full_dataset(self) -> None:
        """Copy the decimator input buffer (full dataset) into the chart buffer for display"""
        self.replace(self._decimator.get_input_buffer())

    def is_dirty(self) -> bool:
        return self._dirty

    def stop_decimator(self) -> None:
        """Stops the decimator, Any input pointed being held for decimation will be moved to the output"""
        self._decimator.force_flush_pending()

    def recompute_minmax(self) -> None:
        """Recompute the min/max values of the whole dataset"""

        # Since the decimator always keeps the min/max of a cluster, we can safely use the decimated buffer to
        # accurately compute the min/max of the whole dataset. We need to take in account the few points at the
        # end of the input buffer not yet moved to the output
        decimated_buffer = self._decimator.get_decimated_buffer()       # The output buffer
        unprocessed_inputs = self._decimator.get_unprocessed_input()    # The few most recent points at the input buffer

        self._x_minmax.clear()
        self._y_minmax.clear()

        # Tests have shown that it is ~2x faster to iterate twice (1 to extract the right value, second to run the min/max function) than
        # iterate once with a key specifier
        self._x_minmax.update_from_many([p.x() for p in decimated_buffer])
        self._y_minmax.update_from_many([p.y() for p in decimated_buffer])

        self._x_minmax.update_from_many([p.x() for p in unprocessed_inputs])
        self._y_minmax.update_from_many([p.y() for p in unprocessed_inputs])

    def x_min(self) -> Optional[float]:
        """The smallest X value in the whole dataset"""
        return self._x_minmax.min()

    def x_max(self) -> Optional[float]:
        """The largest X value in the whole dataset"""
        return self._x_minmax.max()

    def y_min(self) -> Optional[float]:
        """The smallest Y value in the whole dataset"""
        return self._y_minmax.min()

    def y_max(self) -> Optional[float]:
        """The largest Y value in the whole dataset"""
        return self._y_minmax.max()
