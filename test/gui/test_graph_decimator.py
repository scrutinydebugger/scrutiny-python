

from test import ScrutinyUnitTest
from scrutiny.gui.dashboard_components.continuous_graph.decimator import GraphYMinMaxDecimator
from PySide6.QtCore import QPointF
import random

from typing import List

class TestGraphDecimator(ScrutinyUnitTest):
    def test_y_minmax_decimator_base2(self) -> None:
        random.seed(0x12345678)
        decimator = GraphYMinMaxDecimator(base=2)
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
        decimator = GraphYMinMaxDecimator(base=2)
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
        
        
    def test_y_minmax_decimator_base3(self) -> None:
        random.seed(0x12345678)
        decimator = GraphYMinMaxDecimator(3)
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

        

if __name__ == '__main__':
    import unittest
    unittest.main()
