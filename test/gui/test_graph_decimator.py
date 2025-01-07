

from test import ScrutinyUnitTest
from scrutiny.gui.dashboard_components.continuous_graph.decimator import GraphUniformMinMaxDecimator, GraphMonotonicNonUniformMinMaxDecimator
from PySide6.QtCore import QPointF
import random

from typing import List

class TestGraphUniformMinMaxDecimator(ScrutinyUnitTest):
    def test_base2(self) -> None:
        random.seed(0x12345678)
        decimator = GraphUniformMinMaxDecimator(base=2)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(0), 1)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(1), 1)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(2), 1)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(1000), 1)

        self.assertEqual(decimator.get_dataset(1), [])

        for v in [0,2,3,4]:
            with self.assertRaises(Exception):
                decimator.get_dataset(v)
        
        for v in [3,5,6,7,9]:
            with self.assertRaises(Exception):
                decimator.create_decimated_dataset(v)

        decimator.create_decimated_dataset(2)
        self.assertEqual(decimator.get_dataset(2), [])
        
        points = [QPointF(x,y) for x,y in zip([0,1,2,3], [20,40,10,30])]
        decimator.add_point(points[0])
        self.assertEqual(decimator.get_dataset(1), points[0:1])
        self.assertEqual(decimator.get_dataset(2), [])
        
        decimator.add_point(points[1])
        self.assertEqual(decimator.get_dataset(1), points[0:2])
        self.assertEqual(decimator.get_dataset(2), [])

        decimator.add_point(points[2])
        self.assertEqual(decimator.get_dataset(1), points[0:3])
        self.assertEqual(decimator.get_dataset(2), [])

        decimator.add_point(points[3])
        self.assertEqual(decimator.get_dataset(1), points[0:4])
        self.assertEqual(decimator.get_dataset(2), [points[1], points[2]])

        test_data_y = [round(random.random()*100) for i in range(21)] # Will yields 25 values
        test_data = [QPointF(x,y) for x,y in zip(range(5,5+len(test_data_y)), test_data_y)]

        decimator.add_points(test_data)

        self.assertEqual(len(decimator.get_dataset(1)), 25)
        self.assertEqual(len(decimator.get_dataset(2)), 12)
        decimator.create_decimated_dataset(4)
        decimator.create_decimated_dataset(8)
        self.assertEqual(len(decimator.get_dataset(4)), 6)
        self.assertEqual(len(decimator.get_dataset(8)), 2)

        data = decimator.get_dataset(1)
        decimator = GraphUniformMinMaxDecimator(base=2)
        for factor in [2,4,8]:
            decimator.create_decimated_dataset(factor)
        
        for p in data:
            decimator.add_point(p)
        
        def get_minmax(data:List[QPointF]):
            lo = min(data, key=lambda p:p.y())
            hi = max(data, key=lambda p:p.y())

            return sorted([lo, hi], key=lambda p:p.x())

        self.assertEqual(len(decimator.get_dataset(1)), 25)
        self.assertEqual(len(decimator.get_dataset(2)), 12)
        self.assertEqual(len(decimator.get_dataset(4)), 6)
        self.assertEqual(len(decimator.get_dataset(8)), 2)
        decimator.create_decimated_dataset(16)
        self.assertEqual(decimator.get_dataset(16), [])

        self.assertEqual(decimator.get_dataset(1), data)

        self.assertEqual(decimator.get_dataset(2)[0:2], get_minmax(data[0:4]))
        self.assertEqual(decimator.get_dataset(2)[2:4], get_minmax(data[4:8]))
        self.assertEqual(decimator.get_dataset(2)[4:6], get_minmax(data[8:12]))
        self.assertEqual(decimator.get_dataset(2)[6:8], get_minmax(data[12:16]))
        self.assertEqual(decimator.get_dataset(2)[8:10], get_minmax(data[16:20]))
        self.assertEqual(decimator.get_dataset(2)[10:12], get_minmax(data[20:24]))

        self.assertEqual(decimator.get_dataset(4)[0:2], get_minmax(data[0:8]))
        self.assertEqual(decimator.get_dataset(4)[2:4], get_minmax(data[8:16]))
        self.assertEqual(decimator.get_dataset(4)[4:6], get_minmax(data[16:24]))

        self.assertEqual(decimator.get_dataset(8)[0:2], get_minmax(data[0:16]))

        
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(0), 1)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(1), 1)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(2), 2)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(3), 2)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(4), 4)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(5), 4)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(6), 4)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(7), 4)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(8), 8)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(15), 8)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(16), 16)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(17), 16)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(31), 16)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(32), 16)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(33), 16)

        decimator.clear()
        self.assertEqual(decimator.get_dataset(1), [])
        
        with self.assertRaises(Exception):
            decimator.get_dataset(2) 
        
    def test_base3(self) -> None:
        random.seed(0x12345678)
        decimator = GraphUniformMinMaxDecimator(3)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(0), 1)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(1), 1)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(2), 1)
        self.assertEqual(decimator.get_decimation_factor_equal_or_below(1000), 1)

        self.assertEqual(decimator.get_dataset(1), [])

        for v in [0,2,3,4]:
            with self.assertRaises(Exception):
                decimator.get_dataset(v)
        
        for v in [2,4,5,6,7,8,10]:
            with self.assertRaises(Exception):
                decimator.create_decimated_dataset(v)

        decimator.create_decimated_dataset(3)
        self.assertEqual(decimator.get_dataset(3), [])
        
        points = [QPointF(x,y) for x,y in zip([0,1,2,3,4,5,6], [20,40,10,30, 5, 35, ])]
        decimator.add_point(points[0])
        self.assertEqual(decimator.get_dataset(1), points[0:1])
        self.assertEqual(decimator.get_dataset(3), [])
        
        decimator.add_point(points[1])
        self.assertEqual(decimator.get_dataset(1), points[0:2])
        self.assertEqual(decimator.get_dataset(3), [])

        decimator.add_point(points[2])
        self.assertEqual(decimator.get_dataset(1), points[0:3])
        self.assertEqual(decimator.get_dataset(3), [])

        decimator.add_point(points[3])
        self.assertEqual(decimator.get_dataset(1), points[0:4])
        self.assertEqual(decimator.get_dataset(3), [])

        decimator.add_point(points[4])
        self.assertEqual(decimator.get_dataset(1), points[0:5])
        self.assertEqual(decimator.get_dataset(3), [])

        decimator.add_point(points[5])
        self.assertEqual(decimator.get_dataset(1), points[0:6])
        self.assertEqual(decimator.get_dataset(3), [points[1], points[4]])

        test_data_y = [round(random.random()*100) for i in range(83)] # Will yields 85 values
        test_data = [QPointF(x,y) for x,y in zip(range(5,5+len(test_data_y)), test_data_y)]

        decimator.add_points(test_data)

        self.assertEqual(len(decimator.get_dataset(1)), 89)
        self.assertEqual(len(decimator.get_dataset(3)), 28) # 89//3*3 = 87.   87/3 = 29.  first even value equal or below = 28
        decimator.create_decimated_dataset(9)
        decimator.create_decimated_dataset(27)
        self.assertEqual(len(decimator.get_dataset(9)), 8)  # 28//3*3 = 27.   27/3 = 9.  first even value equal or below = 8
        self.assertEqual(len(decimator.get_dataset(27)), 2) # 8//3*3 = 6.   6/3 = 2.  first even value equal or below = 2


class TestGraphMonotonicNonUniformMinMaxDecimator(ScrutinyUnitTest):
    def test_window_0(self) -> None:
        data = []
        for i in range(5):
            data.append(QPointF(i,i*10))
        
        decimator = GraphMonotonicNonUniformMinMaxDecimator()
        self.assertEqual(decimator.get_x_resolution(), 0)

        self.assertEqual(decimator.get_input_dataset(), [])
        self.assertEqual(decimator.get_decimated_dataset(), [])
        for p in data:
            self.assertEqual(decimator.add_point(p), 1)
        self.assertEqual(decimator.get_input_dataset(), data)
        self.assertEqual(decimator.get_decimated_dataset(), data)

        decimator.clear()

        self.assertEqual(decimator.get_input_dataset(), [])
        self.assertEqual(decimator.get_decimated_dataset(), [])
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

        self.assertEqual(decimator.get_decimated_dataset(), [QPointF(0.5, 50), QPointF(0.99, -10)])

        self.assertEqual(decimator.add_point(QPointF(5.0,10)), 1)

        self.assertEqual(len(decimator.get_decimated_dataset()), 3)
        self.assertEqual(decimator.get_decimated_dataset()[-1], QPointF(1.0,80))

        self.assertEqual(decimator.add_point(QPointF(5.5,20)), 0)
        self.assertEqual(decimator.add_point(QPointF(6,30)), 2)

        self.assertEqual(len(decimator.get_decimated_dataset()), 5)
        self.assertEqual(decimator.get_decimated_dataset()[-2:], [QPointF(5.0,10), QPointF(5.5,20)])

        self.assertEqual(decimator.add_point(QPointF(6.1,20)), 0)
        self.assertEqual(decimator.add_point(QPointF(6.2,25)), 0)
        self.assertEqual(decimator.force_flush_pending(), 2)

        self.assertEqual(len(decimator.get_decimated_dataset()), 7)
        self.assertEqual(decimator.get_decimated_dataset()[-2:], [QPointF(6.0,30), QPointF(6.1,20)])
        
        fulldata = decimator.get_input_dataset()
        window_1sec_output_dataset = [
            QPointF(0.5, 50),
            QPointF(0.99, -10),
            QPointF(1.0,80),
            QPointF(5.0,10),
            QPointF(5.5,20),
            QPointF(6.0,30),
            QPointF(6.1,20)
        ]
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
        self.assertEqual(decimator.get_decimated_dataset(), [QPointF(0.99, -10), QPointF(1.0,80)])

        decimator.set_x_resolution(1)
        decimator.force_flush_pending()
        self.assertEqual(decimator.get_input_dataset(), fulldata)
        self.assertEqual(decimator.get_decimated_dataset(),window_1sec_output_dataset)


    def test_delete_data_window_0(self):
        decimator = GraphMonotonicNonUniformMinMaxDecimator()

        data = [QPointF(x,y) for x,y in zip([0,1,2,3,4,5], [0,10,20,30,40,50])]
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

        self.assertEqual(decimator.get_input_dataset(), [QPointF(4,40), QPointF(5,50)])
        self.assertEqual(decimator.get_decimated_dataset(), [QPointF(4,40), QPointF(5,50)])

        decimator.add_point(QPointF(6,60))

        self.assertEqual(decimator.get_input_dataset(), [QPointF(4,40), QPointF(5,50), QPointF(6,60)])
        self.assertEqual(decimator.get_decimated_dataset(), [QPointF(4,40), QPointF(5,50), QPointF(6,60)])


    def test_delete_data_window_non_zero(self):
        decimator = GraphMonotonicNonUniformMinMaxDecimator()
        decimator.set_x_resolution(2)

        data = [QPointF(x,y) for x,y in zip([0,1,2,3,4,5], [0,10,20,30,40,50])]
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

        self.assertEqual(decimator.get_decimated_dataset(), [QPointF(5,50), QPointF(6.9,69)])

        decimator.force_flush_pending() # Add 7
        self.assertEqual(decimator.get_decimated_dataset(), [QPointF(5,50), QPointF(6.9,69), QPointF(7,70)])

if __name__ == '__main__':
    import unittest
    unittest.main()
