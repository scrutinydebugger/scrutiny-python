#    test_graph_features.py
#        A test suite for common graph features
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

from PySide6.QtCore import QPointF
from test.gui.base_gui_test import ScrutinyBaseGuiTest

from scrutiny.gui.widgets.base_chart import ScrutinyLineSeries

class TestGraphFeatures(ScrutinyBaseGuiTest):
    def test_series_search_closest_point(self):
        series = ScrutinyLineSeries()
        for i in range(5):
            series.append(QPointF(i,i))

        self.assertEqual( series.search_closest_monotonic(-100), QPointF(0,0))
        self.assertEqual( series.search_closest_monotonic(-1), QPointF(0,0))
        self.assertEqual( series.search_closest_monotonic(0), QPointF(0,0))
        self.assertEqual( series.search_closest_monotonic(0.49), QPointF(0,0))
        self.assertEqual( series.search_closest_monotonic(0.51), QPointF(1,1))
        self.assertEqual( series.search_closest_monotonic(0.99), QPointF(1,1))
        self.assertEqual( series.search_closest_monotonic(1), QPointF(1,1))
        self.assertEqual( series.search_closest_monotonic(1.1), QPointF(1,1))
        self.assertEqual( series.search_closest_monotonic(1.49), QPointF(1,1))
        self.assertEqual( series.search_closest_monotonic(1.51), QPointF(2,2))
        self.assertEqual( series.search_closest_monotonic(1.99), QPointF(2,2))
        self.assertEqual( series.search_closest_monotonic(2), QPointF(2,2))
        self.assertEqual( series.search_closest_monotonic(2.01), QPointF(2,2))
        self.assertEqual( series.search_closest_monotonic(3.99), QPointF(4,4))
        self.assertEqual( series.search_closest_monotonic(4), QPointF(4,4))
        self.assertEqual( series.search_closest_monotonic(5), QPointF(4,4))
        self.assertEqual( series.search_closest_monotonic(100), QPointF(4,4))

        self.assertEqual( series.search_closest_monotonic(0, min_x=0.2, max_x=3.8), QPointF(1,1))
        self.assertEqual( series.search_closest_monotonic(0.3, min_x=0.2, max_x=3.8), QPointF(1,1))
        self.assertEqual( series.search_closest_monotonic(0.51, min_x=0.2, max_x=3.8), QPointF(1,1))
        self.assertEqual( series.search_closest_monotonic(1.49, min_x=0.2, max_x=3.8), QPointF(1,1))
        self.assertEqual( series.search_closest_monotonic(1.51, min_x=0.2, max_x=3.8), QPointF(2,2))
        self.assertEqual( series.search_closest_monotonic(2.49, min_x=0.2, max_x=3.8), QPointF(2,2))
        self.assertEqual( series.search_closest_monotonic(2.51, min_x=0.2, max_x=3.8), QPointF(3,3))
        self.assertEqual( series.search_closest_monotonic(3.49, min_x=0.2, max_x=3.8), QPointF(3,3))
        self.assertEqual( series.search_closest_monotonic(3.51, min_x=0.2, max_x=3.8), QPointF(3,3))
        self.assertEqual( series.search_closest_monotonic(10, min_x=0.2, max_x=3.8), QPointF(3,3))

        self.assertEqual( series.search_closest_monotonic(0.99, min_x=1, max_x=3), QPointF(1,1))
        self.assertEqual( series.search_closest_monotonic(1.49, min_x=1, max_x=3), QPointF(1,1))
        self.assertEqual( series.search_closest_monotonic(1.51, min_x=1, max_x=3), QPointF(2,2))
        self.assertEqual( series.search_closest_monotonic(2.49, min_x=1, max_x=3), QPointF(2,2))

        self.assertEqual( series.search_closest_monotonic(2.51, min_x=1, max_x=3), QPointF(3,3))
        self.assertEqual( series.search_closest_monotonic(3, min_x=1, max_x=3), QPointF(3,3))
        self.assertEqual( series.search_closest_monotonic(10, min_x=1, max_x=3), QPointF(3,3))

        self.assertEqual( series.search_closest_monotonic(1.4, min_x=1.5, max_x=2.5), QPointF(2,2))
        self.assertEqual( series.search_closest_monotonic(1.6, min_x=1.5, max_x=2.5), QPointF(2,2))
        self.assertEqual( series.search_closest_monotonic(1.99, min_x=1.5, max_x=2.5), QPointF(2,2))
        self.assertEqual( series.search_closest_monotonic(2.01, min_x=1.5, max_x=2.5), QPointF(2,2))
        self.assertEqual( series.search_closest_monotonic(2.4, min_x=1.5, max_x=2.5), QPointF(2,2))
        self.assertEqual( series.search_closest_monotonic(2.6, min_x=1.5, max_x=2.5), QPointF(2,2))

        self.assertIsNone( series.search_closest_monotonic(1, min_x=1.2, max_x=1.8))
        self.assertIsNone( series.search_closest_monotonic(1.2, min_x=1.2, max_x=1.8))
        self.assertIsNone( series.search_closest_monotonic(1.3, min_x=1.2, max_x=1.8))
        self.assertIsNone( series.search_closest_monotonic(1.7, min_x=1.2, max_x=1.8))
        self.assertIsNone( series.search_closest_monotonic(1.8, min_x=1.2, max_x=1.8))
        self.assertIsNone( series.search_closest_monotonic(1.9, min_x=1.2, max_x=1.8))


        series.replace([])
        self.assertIsNone( series.search_closest_monotonic(5))
