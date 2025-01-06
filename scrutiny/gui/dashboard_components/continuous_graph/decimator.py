from PySide6.QtCore import QPointF
from scrutiny.core import validation
from bisect import bisect_left, bisect_right
import math
from dataclasses import dataclass

from typing import List, Dict, Tuple

class GraphYMinMaxDecimator:

    @dataclass(init=False)
    class Dataset:
        factor:int
        data:List[QPointF]

        def __init__(self, factor:int) -> None:
            self.factor=factor
            self.data=[]

    _datasets:List[Dataset]
    _base:int
    _window_width:int

    def __init__(self, base:int=2) -> None:
        validation.assert_int_range(base, 'base', minval=2)
        self._datasets = []
        self._base = base
        self._window_width = 2*self._base
        self.clear()

    def clear(self) -> None:
        self._datasets.clear()
        self._datasets.append(self.Dataset(1))
    
    def get_decimation_factor_equal_or_below(self, wanted_factor:int) -> int:
        factors = [ds.factor for ds in self._datasets]

        index = bisect_left(factors, wanted_factor)
        if index > len(factors)-1:
            return factors[-1]
        
        if factors[index] == wanted_factor:
            return factors[index]
        
        if index == 0:
            return factors[index]
        
        return factors[index-1]
        
    
    def create_decimated_dataset(self, factor:int) -> None:
        dataset_index = self._get_dataset_index_from_factor(factor)
        if len(self._datasets) > dataset_index:
            raise ValueError(f"Sub-dataset with decimation factor {factor} already exists")
        
        assert dataset_index > 0
      
        if len(self._datasets) < dataset_index-1:   # Parent
            self.create_decimated_dataset(factor)
        
        parent_dataset = self._datasets[dataset_index-1]
        new_dataset = self.Dataset(factor)
        self._datasets.append(new_dataset)
               
        nb_loop = len(parent_dataset.data) // self._window_width

        for i in range(nb_loop):
            subdata = parent_dataset.data[i:i+self._window_width]           
            new_dataset.data.extend(self._compute_decimated_values(subdata))

    def add_point(self, point:QPointF) -> None:
        self.add_points((point,))
    
    def add_points(self, points:List[QPointF]) -> None:
        self._datasets[0].data.extend(points)
        
        for i in range(1, len(self._datasets)):
            parent = self._datasets[i-1]
            child = self._datasets[i]
            while len(parent.data) >= (len(child.data)//2 + 1) * self._window_width:
                start_index = len(child.data)//2*self._window_width
                child.data.extend(self._compute_decimated_values(parent.data[start_index:start_index+self._window_width]))


    def get_dataset(self, factor:int) -> List[QPointF]:
        index = self._get_dataset_index_from_factor(factor)
        if index < 0 or index > len(self._datasets)-1:
            raise KeyError(f"No dataset computed for deciamtion factor {factor}")
        return self._datasets[index].data

    def _compute_decimated_values(self, subdata:List[QPointF]) -> Tuple[QPointF,QPointF]:
        lo = min(subdata, key=lambda p:p.y())
        hi = max(subdata, key=lambda p:p.y())

        if subdata.index(lo) < subdata.index(hi):
            return (lo, hi)
        else:
            return (hi, lo)
        
    def _get_dataset_index_from_factor(self, factor:int) -> int:
        validation.assert_int_range(factor, 'factor', minval=1)
        logval = math.log(factor, self._base)
        if (logval - math.floor(logval)) != 0:
            raise ValueError(f"Factor is not a power of {self._base}")
        
        return int(logval)
