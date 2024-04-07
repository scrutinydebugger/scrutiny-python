__all__ = ['CSVFileListener']
from scrutiny.core import validation
from scrutiny.sdk.listeners import ValueUpdate
from scrutiny.sdk import exceptions as sdk_exceptions
from . import BaseListener
import os
import time
import re
import csv
from datetime import datetime
from typing import List, Dict, Any, Optional, TextIO, Union

class CSVFileListener(BaseListener):
    EXTENSION='.csv'
    ENCODING='utf8'
    NEWLINE='\n'
    DELIMITER=','
    QUOTECHAR='"'

    DATETIME_HEADER='datetime'
    RELTIME_HEADER='time (ms)'

    _folder_abs:str
    _requested_basename:str
    _line_per_files:Optional[int]
    _datetime_format:str
    _start_time:float
    _actual_file_basename:str
    _actual_file_handle:Optional[TextIO]
    _line_counter:int
    _csv_writer:Optional[csv.DictWriter]
    _val_dict:Dict[str, Union[str, int, float, bool]]
    _actual_index:int
    _fieldnames:List[str]


    def __init__(self, 
                 folder:str,
                 filename:str,
                 line_per_files:Optional[int]=10000,
                 datetime_format:str=r'%Y-%m-%d %H:%M:%S.%f',
                 *args:Any, **kwargs:Any):
        BaseListener.__init__(self, *args, **kwargs)

        validation.assert_type(folder, 'folder', str)
        validation.assert_type(filename, 'filename', str)
        validation.assert_int_range_if_not_none(line_per_files, 'line_per_files', minval=100)
        validation.assert_type(datetime_format, 'datetime_format', str)

        folder = os.path.normpath(os.path.abspath(folder))
        if os.path.isdir(folder):
            raise FileNotFoundError("Folder {folder} does not exist")
        
        parts = os.path.split(filename)
        if len(parts[0]) > 0:
            raise ValueError("Given filename must not contains directories. Just the filename")
        
        if filename.endswith(self.EXTENSION):
            filename = filename[:-len(self.EXTENSION)]

        if len(filename) == 0:
            raise ValueError("Empty filename")

        if line_per_files is not None:
            regex_test=re.compile(f'{filename}_[0-9]+{self.EXTENSION}')
            for file in os.listdir(folder):
                if regex_test.match(file):
                    raise FileExistsError(f"File {os.path.join(folder, file)} exists and may conflict with this listener")

        self._folder_abs = folder
        self._requested_basename = filename
        self._line_per_files = line_per_files
        self._datetime_format = datetime_format
        self._start_time=0
        self._actual_file_basename = ''
        self._actual_file_handle = None
        self._line_counter=0
        self._csv_writer = None
        self._val_dict = {}
        self._actual_index=0
        self._fieldnames = []

    def _make_file_basename(self, index:Optional[int]) -> str:
        if index is not None:
            return f'{self._requested_basename}_{index:04d}{self.EXTENSION}'
        else :
            return f'{self._requested_basename}{self.EXTENSION}'
    
    def _open_file_by_basename(self, basename) -> TextIO:
        fullpath = os.path.join(self._folder_abs, basename)
        if os.path.exists(fullpath):
            raise FileExistsError(f"File {fullpath} already exists")
        return  open(fullpath, 'w', encoding=self.ENCODING, newline=self.NEWLINE)

    def _make_csv_writer(self) -> csv.DictWriter:
        assert len(self._fieldnames) > 0
        assert self._actual_file_handle is not None

        return csv.DictWriter(self._actual_file_handle, self._fieldnames, delimiter=self.DELIMITER, quotechar=self.QUOTECHAR)

    def _switch_to_next_file(self) -> None:
        if self._line_per_files is None:
            raise RuntimeError("Cannot switch file when lines_per_file is None")
        
        if self._actual_file_handle is not None:
            self._csv_writer = None
            self._actual_file_handle.close()
            self._logger.debug(f"Closing {self._actual_file_basename}")
        
        self._actual_file_handle=None
        self._actual_index+=1 
        self._actual_file_basename = self._make_file_basename(self._actual_index)
        self._actual_file_handle = self._open_file_by_basename(self._actual_file_basename)
        self._csv_writer = csv.DictWriter(self._actual_file_handle, self._fieldnames)
        self._line_counter=0
        self._logger.info(f"Switched logging to {self._actual_file_basename}")

    
    def setup(self) -> None:
        first_file_index = 0 if self._line_per_files is not None else None
        self._start_time = time.perf_counter()
        self._actual_file_basename = self._make_file_basename(first_file_index)
        self._actual_file_handle = self._open_file_by_basename(self._actual_file_basename)
        self._actual_index = 0

        self._line_counter = 0
        self._val_dict = {}

        subscriptions = list(self.get_subscriptions())
        subscriptions.sort(key=lambda x: x.name)
        self._fieldnames = [self.DATETIME_HEADER, self.RELTIME_HEADER]
        self._val_dict[self.DATETIME_HEADER] = datetime.now().strftime(self._datetime_format)
        self._val_dict[self.RELTIME_HEADER] = 0
        
        for i in range(len(subscriptions)):
            display_path = subscriptions[i].display_path
            try:
                self._val_dict[display_path] = subscriptions[i].value
            except sdk_exceptions.InvalidValueError:
                self._val_dict[display_path] = ''
            self._fieldnames.append(display_path)
        
        self._csv_writer = self._make_csv_writer()
        self._csv_writer.writeheader()


    def receive(self, updates: List[ValueUpdate]) -> None:
        assert self._csv_writer is not None
        self._val_dict[self.RELTIME_HEADER] = (time.perf_counter() - self._start_time)*1e3
        self._val_dict[self.DATETIME_HEADER] = datetime.now().strftime(self._datetime_format)

        for update in updates:
            self._val_dict[update.display_path] = update.value

        self._csv_writer.writerow(self._val_dict)
        self._line_counter+=1
        if self._line_per_files is not None and self._line_counter >= self._line_per_files:
            self._switch_to_next_file()
    
    def teardown(self) -> None:
        if self._actual_file_handle is not None:
            self._actual_file_handle.close()
