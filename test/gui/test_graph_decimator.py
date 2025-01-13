#    test_graph_decimator.py
#        Test suite for the continuuos graph data decimator
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from test import ScrutinyUnitTest
from scrutiny.gui.dashboard_components.continuous_graph.decimator import GraphMonotonicNonUniformMinMaxDecimator
from PySide6.QtCore import QPointF

class TestGraphMonotonicNonUniformMinMaxDecimator(ScrutinyUnitTest):

    CONTAINER = list

    def test_window_0(self) -> None:
        data = self.CONTAINER()
        for i in range(5):
            data.append(QPointF(i,i*10))
        
        decimator = GraphMonotonicNonUniformMinMaxDecimator()
        self.assertEqual(decimator.get_x_resolution(), 0)

        self.assertEqual(len(decimator.get_input_dataset()), 0)
        self.assertEqual(len(decimator.get_decimated_dataset()), 0)
        for p in data:
            self.assertEqual(decimator.add_point(p), 1)
        self.assertEqual(decimator.get_input_dataset(), data)
        self.assertEqual(decimator.get_decimated_dataset(), data)

        decimator.clear()

        self.assertEqual(len(decimator.get_decimated_dataset()), 0)
        self.assertEqual(len(decimator.get_input_dataset()), 0)
        self.assertEqual(decimator.add_points(data), len(data))
        self.assertEqual(decimator.get_input_dataset(), data)
        self.assertEqual(decimator.get_decimated_dataset(), data)

    def test_window_non_zero(self):

        decimator = GraphMonotonicNonUniformMinMaxDecimator()
        decimator.set_x_resolution(1.0)
        
        self.assertEqual(decimator.add_point(QPointF(0,0)), 0)
        self.assertEqual(decimator.add_point(QPointF(0.1,10)), 0)
        self.assertEqual(decimator.add_point(QPointF(0.5,50)), 0)
        self.assertEqual(decimator.add_point(QPointF(0.6,40)), 0)
        self.assertEqual(decimator.add_point(QPointF(0.99,-10)), 0)
        self.assertEqual(decimator.add_point(QPointF(1.0,80)), 2)

        self.assertEqual(decimator.get_decimated_dataset(), self.CONTAINER([QPointF(0.5, 50), QPointF(0.99, -10)]))

        self.assertEqual(decimator.add_point(QPointF(5.0,10)), 1)

        self.assertEqual(len(decimator.get_decimated_dataset()), 3)
        self.assertEqual(decimator.get_decimated_dataset()[2], QPointF(1.0,80))

        self.assertEqual(decimator.add_point(QPointF(5.5,20)), 0)
        self.assertEqual(decimator.add_point(QPointF(6,30)), 2)

        self.assertEqual(len(decimator.get_decimated_dataset()), 5)
        self.assertEqual(decimator.get_decimated_dataset()[3:], self.CONTAINER([QPointF(5.0,10), QPointF(5.5,20)]))

        self.assertEqual(decimator.add_point(QPointF(6.1,20)), 0)
        self.assertEqual(decimator.add_point(QPointF(6.2,25)), 0)
        self.assertEqual(decimator.force_flush_pending(), 2)

        self.assertEqual(len(decimator.get_decimated_dataset()), 7)
        self.assertEqual(decimator.get_decimated_dataset()[5:], self.CONTAINER([QPointF(6.0,30), QPointF(6.1,20)]))
        
        fulldata = decimator.get_input_dataset()
        window_1sec_output_dataset = self.CONTAINER([
            QPointF(0.5, 50),
            QPointF(0.99, -10),
            QPointF(1.0,80),
            QPointF(5.0,10),
            QPointF(5.5,20),
            QPointF(6.0,30),
            QPointF(6.1,20)
        ])
        decimator.clear()
        self.assertEqual(len(decimator.get_input_dataset()), 0)
        self.assertEqual(len(decimator.get_decimated_dataset()), 0)
        
        decimator.add_points(fulldata)
        self.assertEqual(len(decimator.get_input_dataset()), len(fulldata))
        self.assertEqual(len(decimator.get_decimated_dataset()), 5)
        self.assertEqual(decimator.force_flush_pending(), 2)
        self.assertEqual(len(decimator.get_decimated_dataset()), 7)
        self.assertEqual(decimator.get_decimated_dataset(),window_1sec_output_dataset)


        decimator.set_x_resolution(10)
        decimator.force_flush_pending()
        self.assertEqual(decimator.get_input_dataset(), fulldata)
        self.assertEqual(decimator.get_decimated_dataset(), self.CONTAINER([QPointF(0.99, -10), QPointF(1.0,80)]))

        decimator.set_x_resolution(1)
        decimator.force_flush_pending()
        self.assertEqual(decimator.get_input_dataset(), fulldata)
        self.assertEqual(decimator.get_decimated_dataset(),window_1sec_output_dataset)

    def test_delete_data_window_0(self):
        decimator = GraphMonotonicNonUniformMinMaxDecimator()

        data = self.CONTAINER(QPointF(x,y) for x,y in zip([0,1,2,3,4,5], [0,10,20,30,40,50]))
        decimator.add_points(data)

        self.assertEqual(len(decimator.get_decimated_dataset()), len(data))
        self.assertEqual(len(decimator.get_input_dataset()), len(data))

        decimator.delete_data_up_to_x(0.9)
        self.assertEqual(len(decimator.get_decimated_dataset()), 5)
        self.assertEqual(len(decimator.get_input_dataset()), 5)

        decimator.delete_data_up_to_x(1)    # Value is expected to be excluded
        self.assertEqual(len(decimator.get_decimated_dataset()), 5)
        self.assertEqual(len(decimator.get_input_dataset()), 5)

        decimator.delete_data_up_to_x(1.01)
        self.assertEqual(len(decimator.get_decimated_dataset()), 4)
        self.assertEqual(len(decimator.get_input_dataset()), 4)

        decimator.delete_data_up_to_x(3.5)
        self.assertEqual(len(decimator.get_decimated_dataset()), 2)
        self.assertEqual(len(decimator.get_input_dataset()), 2)

        self.assertEqual(decimator.get_input_dataset(), self.CONTAINER([QPointF(4,40), QPointF(5,50)]))
        self.assertEqual(decimator.get_decimated_dataset(), self.CONTAINER([QPointF(4,40), QPointF(5,50)]))

        decimator.add_point(QPointF(6,60))

        self.assertEqual(decimator.get_input_dataset(), self.CONTAINER([QPointF(4,40), QPointF(5,50), QPointF(6,60)]))
        self.assertEqual(decimator.get_decimated_dataset(), self.CONTAINER([QPointF(4,40), QPointF(5,50), QPointF(6,60)]))


    def test_delete_data_window_non_zero(self):
        decimator = GraphMonotonicNonUniformMinMaxDecimator()
        decimator.set_x_resolution(2)

        data = self.CONTAINER([QPointF(x,y) for x,y in zip([0,1,2,3,4,5], [0,10,20,30,40,50])])
        decimator.add_points(data)

        self.assertEqual(len(decimator.get_input_dataset()), 6)
        self.assertEqual(len(decimator.get_decimated_dataset()), 4)

        decimator.delete_data_up_to_x(4.2)

        self.assertEqual(len(decimator.get_input_dataset()), 1)
        self.assertEqual(len(decimator.get_decimated_dataset()), 0)

        decimator.add_point(QPointF(6,60))
        self.assertEqual(len(decimator.get_input_dataset()), 2)
        self.assertEqual(len(decimator.get_decimated_dataset()), 0)
        
        decimator.add_point(QPointF(6.9,69))
        self.assertEqual(len(decimator.get_input_dataset()), 3)
        self.assertEqual(len(decimator.get_decimated_dataset()), 0)

        decimator.add_point(QPointF(7,70))  # Will dump [5-7[ to output. 7 is exluded
        self.assertEqual(len(decimator.get_input_dataset()), 4)
        self.assertEqual(len(decimator.get_decimated_dataset()), 2)

        self.assertEqual(decimator.get_decimated_dataset(), self.CONTAINER([QPointF(5,50), QPointF(6.9,69)]))

        decimator.force_flush_pending() # Add 7
        self.assertEqual(decimator.get_decimated_dataset(), self.CONTAINER([QPointF(5,50), QPointF(6.9,69), QPointF(7,70)]))

    def test_constant_value(self) -> None:
        decimator = GraphMonotonicNonUniformMinMaxDecimator()
        decimator.set_x_resolution(2)
        decimator.add_point(QPointF(0,0))
        decimator.add_point(QPointF(0.5,0))
        decimator.add_point(QPointF(1,0))
        decimator.add_point(QPointF(1.5,0))
        decimator.add_point(QPointF(2,0))
        self.assertEqual(len(decimator.get_decimated_dataset()), 2)
        decimator.add_point(QPointF(2.5,0))
        
if __name__ == '__main__':
    import unittest
    unittest.main()
