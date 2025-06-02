#    decimator.py
#        A data decimator meant to handle real-time data stream (monotonic time axis)
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['GraphMonotonicNonUniformMinMaxDecimator']

from PySide6.QtCore import QPointF
from scrutiny.tools import validation

from scrutiny.tools.typing import *


class GraphMonotonicNonUniformMinMaxDecimator:
    """A decimator that reduces the number of points for a x-y data series where X is non-uniform but monotonic (time).
    Makes a min/max of cluster of points so it can be shown on a graph without missing peaks
    """
    _x_window_size: float
    """The size of the window for x clustering. Size in X-Value"""
    _actual_window_start_index: int
    """The index of the start of the window on the x-axis"""
    _input_dataset: List[QPointF]
    """Non decimated data"""
    _output_dataset: List[QPointF]
    """Decimated data"""

    def __init__(self) -> None:
        self._x_window_size = float(0)
        self.clear()

    def clear(self) -> None:
        self._input_dataset = []
        self._output_dataset = []
        self._actual_window_start_index = 0

    def add_point(self, p: QPointF) -> int:
        self._input_dataset.append(p)
        if self._x_window_size == 0:
            self._output_dataset.append(p)
            return 1

        return self._update_output_data_from_start_index()

    def add_points(self, points: List[QPointF]) -> int:
        self._input_dataset.extend(points)
        if self._x_window_size == 0:
            self._output_dataset.extend(points)
            return len(points)

        return self._update_output_data_from_start_index()

    def set_x_resolution(self, resolution: float) -> bool:
        validation.assert_float_range(resolution, 'resolution', minval=0)
        if resolution != self._x_window_size:
            self._x_window_size = resolution
            self._recompute_output_dataset()
            return True
        return False

    def get_x_resolution(self) -> float:
        return self._x_window_size

    def _recompute_output_dataset(self) -> None:
        self._actual_window_start_index = 0
        self._output_dataset.clear()

        if len(self._input_dataset) == 0:
            return

        if self._x_window_size == 0:
            self._output_dataset = self._input_dataset.copy()
            return

        self._update_output_data_from_start_index()

    def force_flush_pending(self) -> int:
        point_added_count = self._update_output_data_from_start_index()
        subdata = self._input_dataset[self._actual_window_start_index:]
        if len(subdata) > 0:
            new_output_data = self._compute_decimated_values(subdata)
            self._output_dataset.extend(new_output_data)
            point_added_count += len(new_output_data)
            self._actual_window_start_index = len(self._input_dataset)
        return point_added_count

    def _update_output_data_from_start_index(self) -> int:
        if len(self._input_dataset) == 0:
            return 0
        point_added_count = 0
        done = False
        while not done:
            pstart = self._input_dataset[self._actual_window_start_index]
            window_end_x = pstart.x() + self._x_window_size
            done = True
            if len(self._input_dataset) - self._actual_window_start_index > 0:  # At least 1 points after the start index
                for next_p_index in range(self._actual_window_start_index + 1, len(self._input_dataset)):
                    pnext = self._input_dataset[next_p_index]
                    if pnext.x() >= window_end_x:
                        subdata = self._input_dataset[self._actual_window_start_index:next_p_index]
                        new_output_data = self._compute_decimated_values(subdata)
                        self._output_dataset.extend(new_output_data)
                        point_added_count += len(new_output_data)
                        self._actual_window_start_index = next_p_index
                        done = False
                        break
        return point_added_count

    def _compute_decimated_values(self, subdata: List[QPointF]) -> Sequence[QPointF]:
        if len(subdata) <= 1:
            return subdata

        lo = min(subdata, key=lambda p: p.y())
        hi = max(subdata, key=lambda p: p.y())

        if lo.x() <= hi.x():
            return (lo, hi)
        else:
            return (hi, lo)

    def decimation_factor(self) -> float:
        if len(self._output_dataset) == 0:
            return 1
        return len(self._input_dataset) / len(self._output_dataset)

    def get_input_buffer(self) -> List[QPointF]:
        return self._input_dataset

    def get_decimated_buffer(self) -> List[QPointF]:
        return self._output_dataset

    def get_unprocessed_input(self) -> List[QPointF]:
        return self._input_dataset[self._actual_window_start_index:]

    def get_input_dataset(self) -> List[QPointF]:
        return self._input_dataset.copy()

    def get_decimated_dataset(self) -> List[QPointF]:
        return self._output_dataset.copy()

    def delete_data_up_to_x(self, xval: float) -> tuple[int, int]:
        input_delete_count = 0
        output_delete_count = 0

        input_data_count = len(self._input_dataset)
        output_data_count = len(self._output_dataset)

        found = False
        for i in range(input_data_count):
            if self._input_dataset[i].x() >= xval:
                # Stop deletion
                input_delete_count = i
                found = True
                break

        if not found:
            input_delete_count = input_data_count

        found = False
        for i in range(output_data_count):
            if self._output_dataset[i].x() >= xval:
                # Stop deletion
                output_delete_count = i
                found = True
                break

        if not found:
            output_delete_count = output_data_count

        if input_delete_count > 0:
            self._actual_window_start_index = max(self._actual_window_start_index - input_delete_count, 0)
            del self._input_dataset[0:input_delete_count]
            del self._output_dataset[0:output_delete_count]

        return (input_delete_count, output_delete_count)
