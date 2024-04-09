#    csv_file_listener.py
#        Listener that dumps the values of the watchables into either one or multiple CSV
#        files
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['CSVFileListener', 'CSVConfig']
from scrutiny.core import validation
from scrutiny.core.basic_types import *
from scrutiny.sdk.listeners import ValueUpdate
from scrutiny.sdk import exceptions as sdk_exceptions
from . import BaseListener
import os
import time
import re
import csv
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, TextIO, Union

@dataclass(frozen=True)
class CSVConfig:
    """CSV format options to be used by the CSVFileListener"""

    encoding:str='utf8'
    """File encoding"""
    newline:str='\n'
    """CSV new line specifier"""
    delimiter:str=','
    """CSV delimiter"""
    quotechar:str='"'
    """CSV quote char"""
    quoting:int=csv.QUOTE_NONNUMERIC
    """The quoting strategy. Refers to the python csv module. Default: ``csv.QUOTE_NONNUMERIC``"""



class CSVFileListener(BaseListener):
    EXTENSION='.csv'
 
    DATETIME_HEADER='datetime'
    RELTIME_HEADER='time (ms)'
    UPDATE_FLAG_HEADER='update flags'
    WATCHABLE_FIRST_COL=2

    _folder_abs:str
    _requested_basename:str
    _lines_per_file:Optional[int]
    _datetime_format:str
    _start_time:float
    _actual_file_basename:str
    _actual_file_handle:Optional[TextIO]
    _line_counter:int
    _csv_writer:Optional["csv.DictWriter[str]"]
    _val_dict:Dict[str, Union[str, int, float, bool]]
    _actual_index:int
    _fieldnames:List[str]
    _csv_config:CSVConfig
    _convert_bool_to_int:bool
    _file_part_0pad:int


    def __init__(self, 
                 folder:str,
                 filename:str,
                 lines_per_file:Optional[int]=None,
                 datetime_format:str=r'%Y-%m-%d %H:%M:%S.%f',
                 convert_bool_to_int:bool=True,
                 file_part_0pad:int=4,
                 csv_config:Optional[CSVConfig]=None,
                 *args:Any, **kwargs:Any):
        """Listener that writes the watchable values into a CSV file as they are received
        
        :param folder: Folder in which to save the CSV file
        :param filename: Name of the file to create
        :param lines_per_file: Maximum number of lines per file, no limits if ``None``.  When this value is set to a valid integer, the file naming
            pattern will be ``<filename>_XXXX.csv`` where ``XXXX`` is the the part number starting from 0. When no limit is specified, a single CSV file 
            will be created following with name ``<filename>.csv``
        :param datetime_format: Format string for the datetime printed in the CSV file
        :param convert_bool_to_int: When ``True``, boolean values will be printed as 0 and 1 instead of ``False`` and ``True``. Convenience for Excel
        :param file_part_0pad: When ``lines_per_file`` is set, this parameter is the number of leading 0 used to pad the filename part suffix. A value of 4 will result
            in files being named: my_file_0000.csv, my_file_0001.csv, and so forth
        :param csv_config: Configuration for the CSV format

        :param args: Passed to :class:`BaseListener<scrutiny.sdk.listeners.BaseListener>`
        :param kwargs: Passed to :class:`BaseListener<scrutiny.sdk.listeners.BaseListener>`
        
        """
        BaseListener.__init__(self, *args, **kwargs)

        if csv_config is None:
            csv_config = CSVConfig()
        
        validation.assert_type(folder, 'folder', str)
        validation.assert_type(filename, 'filename', str)
        validation.assert_int_range_if_not_none(lines_per_file, 'lines_per_file', minval=100)
        validation.assert_type(datetime_format, 'datetime_format', str)
        validation.assert_type(convert_bool_to_int, 'convert_bool_to_int', bool)
        validation.assert_int_range(file_part_0pad, 'file_part_0pad', minval=0, maxval=20)
        validation.assert_type(csv_config, 'csv_config', CSVConfig)


        folder = os.path.normpath(os.path.abspath(folder))
        if not os.path.isdir(folder):
            raise FileNotFoundError(f"Folder {folder} does not exist")
        
        parts = os.path.split(filename)
        if len(parts[0]) > 0:
            raise ValueError("Given filename must not contains directories. Just the filename")
        
        if filename.endswith(self.EXTENSION):
            filename = filename[:-len(self.EXTENSION)]

        if len(filename) == 0:
            raise ValueError("Empty filename")

        if lines_per_file is not None:
            regex_test=re.compile(f'{filename}_[0-9]+{self.EXTENSION}')
            for file in os.listdir(folder):
                if regex_test.match(file):
                    raise FileExistsError(f"File {os.path.join(folder, file)} exists and may conflict with this listener")

        self._folder_abs = folder
        self._requested_basename = filename
        self._lines_per_file = lines_per_file
        self._datetime_format = datetime_format
        self._start_time=0
        self._actual_file_basename = ''
        self._actual_file_handle = None
        self._line_counter=0
        self._csv_writer = None
        self._val_dict = {}
        self._actual_index=0
        self._fieldnames = []
        self._csv_config=csv_config
        self._convert_bool_to_int=convert_bool_to_int
        self._file_part_0pad=file_part_0pad

    def _make_file_basename(self, index:Optional[int]) -> str:
        if index is not None:
            format_str = r'%s_%0' + str(self._file_part_0pad) + r'd%s'
            return format_str % (self._requested_basename, index, self.EXTENSION)
        else :
            return f'{self._requested_basename}{self.EXTENSION}'
    
    def _open_file_by_basename(self, basename:str) -> TextIO:

        fullpath = os.path.join(self._folder_abs, basename)
        if os.path.exists(fullpath):
            raise FileExistsError(f"File {fullpath} already exists")
        return  open(fullpath, 'w', encoding= self._csv_config.encoding, newline= self._csv_config.newline)

    def _make_csv_writer(self) -> "csv.DictWriter[str]":
        assert len(self._fieldnames) > 0
        assert self._actual_file_handle is not None

        return csv.DictWriter(
            self._actual_file_handle, 
            self._fieldnames, 
            delimiter=self._csv_config.delimiter, 
            quotechar=self._csv_config.quotechar,
            quoting=self._csv_config.quoting
            )

    def _switch_to_next_file(self) -> None:
        if self._lines_per_file is None:
            raise RuntimeError("Cannot switch file when lines_per_file is None")
        
        if self._actual_file_handle is not None:
            self._csv_writer = None
            self._actual_file_handle.close()
            self._logger.debug(f"Closing {self._actual_file_basename}")
        
        self._actual_file_handle=None
        self._actual_index+=1 
        self._actual_file_basename = self._make_file_basename(self._actual_index)
        self._actual_file_handle = self._open_file_by_basename(self._actual_file_basename)
        self._line_counter=0
        self._logger.info(f"Switched logging to {self._actual_file_basename}")
        self._csv_writer = self._make_csv_writer()
        self._csv_writer.writeheader()

    
    def setup(self) -> None:
        first_file_index = 0 if self._lines_per_file is not None else None
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
            if i==0:
                # Safety check to make sure WATCHABLE_FIRST_COL is correct
                assert self.WATCHABLE_FIRST_COL == len(self._fieldnames)
            display_path = subscriptions[i].display_path
            try:
                self._val_dict[display_path] = subscriptions[i].value
                if self._convert_bool_to_int and subscriptions[i].datatype == EmbeddedDataType.boolean:
                    self._val_dict[display_path] = int(self._val_dict[display_path])
            except sdk_exceptions.InvalidValueError:
                self._val_dict[display_path] = ''
            self._fieldnames.append(display_path)
        
        self._val_dict[self.UPDATE_FLAG_HEADER]=''
        self._fieldnames.append(self.UPDATE_FLAG_HEADER)
        
        self._csv_writer = self._make_csv_writer()
        self._csv_writer.writeheader()


    def receive(self, updates: List[ValueUpdate]) -> None:
        assert self._csv_writer is not None
        self._val_dict[self.RELTIME_HEADER] = round((time.perf_counter() - self._start_time)*1e3, 3)
        self._val_dict[self.DATETIME_HEADER] = datetime.now().strftime(self._datetime_format)
        update_flags = [0]*len(self.get_subscriptions())
        for update in updates:
            self._val_dict[update.display_path] = update.value
            if self._convert_bool_to_int and update.datatype == EmbeddedDataType.boolean:
                    self._val_dict[update.display_path] = int(self._val_dict[update.display_path])
            
            field_index = self.WATCHABLE_FIRST_COL
            for i in range(len(self.get_subscriptions())):
                if update.display_path == self._fieldnames[field_index]:
                    update_flags[i]=1 
                field_index += 1
                
        self._val_dict[self.UPDATE_FLAG_HEADER] = ','.join([str(x) for x in update_flags])


        self._csv_writer.writerow(self._val_dict)
        self._line_counter+=1
        if self._lines_per_file is not None and self._line_counter >= self._lines_per_file:
            self._switch_to_next_file()
    
    def teardown(self) -> None:
        if self._actual_file_handle is not None:
            self._actual_file_handle.close()
