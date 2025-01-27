#    csv_logger.py
#        Logger that dumps the values of the watchables into either one or multiple CSV files
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['CSVConfig', 'CSVLogger']

import os
import csv
import _csv  # Weirdness of python type hints
import re
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path

from scrutiny.tools import validation
from scrutiny.core.basic_types import EmbeddedDataType
from scrutiny.sdk.listeners import ValueUpdate
from scrutiny.sdk.watchable_handle import WatchableHandle
from scrutiny.tools.typing import *
from typing import TextIO

PossibleVal = Optional[Union[str, float, int, bool]]
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

class CSVLogger:

    @dataclass
    class ColumnDescriptor:
        server_id:str
        name:str
        fullpath:Optional[str]

    EXTENSION='.csv'
 
    DATETIME_HEADER='Datetime'
    RELTIME_HEADER='Time (s)'
    UPDATE_FLAG_HEADER='update flags'
    WATCHABLE_FIRST_COL=2

    _folder_abs:str
    _requested_basename:str
    _lines_per_file:Optional[int]
    _datetime_format:str
    _first_val_dt:Optional[datetime]
    _actual_file_basename:str
    _actual_file_handle:Optional[TextIO]
    _csv_writer:Optional["_csv._writer"]
    _actual_file_number:int
    _csv_config:CSVConfig
    _convert_bool_to_int:bool
    _file_part_0pad:int
    _logger:logging.Logger
    _column_descriptors:List[ColumnDescriptor]
    _column_map:Dict[str, int]
    _started:bool
    _file_headers:List[List[str]]
    _datetime_zero_sec:datetime
    _line_counter:int
    _actual_vals:List[PossibleVal]
    _actual_x:float
    _new_val_flags:List[bool]
    
    def __init__(self, 
                 folder:str,
                 filename:str,
                 datetime_zero_sec:Optional[datetime]=None,
                 lines_per_file:Optional[int]=None,
                 datetime_format:str=r'%Y-%m-%d %H:%M:%S.%f',
                 convert_bool_to_int:bool=True,
                 file_part_0pad:int=4,
                 csv_config:Optional[CSVConfig]=None,
                 logger:Optional[logging.Logger]=None,
                 file_headers:List[List[str]] = []
                 ) -> None:
        
        """Logger that writes the watchable values into a CSV file as they are received
        
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
        :param logger: An optional python logger to log progress and write debug information
        
        """
        if csv_config is None:
            csv_config = CSVConfig()
        
        validation.assert_type(folder, 'folder', str)
        validation.assert_type(filename, 'filename', str)
        validation.assert_int_range_if_not_none(lines_per_file, 'lines_per_file', minval=100)
        validation.assert_type(datetime_format, 'datetime_format', str)
        validation.assert_type(convert_bool_to_int, 'convert_bool_to_int', bool)
        validation.assert_int_range(file_part_0pad, 'file_part_0pad', minval=0, maxval=20)
        validation.assert_type(csv_config, 'csv_config', CSVConfig)
        validation.assert_type_or_none(datetime_zero_sec, 'datetime_zero_sec', datetime)
        
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
            for file in self.get_conflicting_files(Path(folder), filename):
                raise FileExistsError(f"File {os.path.join(folder, file)} exists and may conflict with the CSV output")

        validation.assert_type_or_none(logger, 'logger', logging.Logger)
        if logger is None:
            logger = logging.getLogger(self.__class__.__name__)


        self._folder_abs = folder
        self._requested_basename = filename
        self._lines_per_file = lines_per_file
        self._datetime_format = datetime_format
        self._first_val_dt=None
        self._actual_file_basename = ''
        self._actual_file_handle = None
        self._csv_writer = None
        self._actual_file_number=0
        self._csv_config=csv_config
        self._convert_bool_to_int=convert_bool_to_int
        self._file_part_0pad=file_part_0pad
        self._logger = logger
        self._started = False
        self._datetime_zero_sec = datetime_zero_sec if datetime_zero_sec is not None else datetime.now()
        self._column_descriptors=[]
        self._line_counter = 0
        self._actual_vals = []
        self._actual_x = 0
        self._column_map = {}
        self._new_val_flags = []

        self.set_file_headers(file_headers)

    def get_folder(self) -> Path:
        return Path(self._folder_abs)
    
    @classmethod
    def get_conflicting_files(cls, folder:Path, filename:str) -> Generator[Path, None, None]:
        """Makes the inventory of all the files that already exist with a name pattern that may collide with the given folder and filename
        
        :param folder: The output folder
        :param filename: The file basename where all files are named <basename>_nnnn.csv 
        
        """
        regex_test = re.compile(f'{re.escape(filename)}_[0-9]+{cls.EXTENSION}')
        for file in os.listdir(folder):
            if regex_test.match(file):
                yield folder / file

    def set_file_headers(self, file_headers:List[List[str]]) -> None:
        """Configure the list of headers to add at the top of the file before writing the value table"""
        if self._started:
            raise RuntimeError("Cannot set the file headers when started")
        validation.assert_type(file_headers, 'file_headers', list)

        for row in file_headers:
            validation.assert_type(row, 'file_headers[n]', list)
            for cell in row:
                validation.assert_type(cell, 'file_headers[n][m]', str)

        self._file_headers = file_headers

    def get_actual_filename(self) -> Optional[Path]:
        """Return the name of the file actually being written"""
        if not self._started:
            return None
        return Path(os.path.join(self._folder_abs, self._actual_file_basename))

    def define_columns_from_handles(self, watchable_handles:Iterable[WatchableHandle]) -> None:
        """Define the CSV columns from a list of Watchable handles. Columns are in the same order as the provided sequence"""
        descriptors = [self.ColumnDescriptor(server_id=h.server_id, name=h.name, fullpath=h.display_path) for h in watchable_handles]
        self.define_columns(descriptors)

    def define_columns(self, columns:Iterable[ColumnDescriptor]) -> None:
        """Define the CSV columns. Columns are in the same order as the provided sequence"""
        if self._started:
            raise RuntimeError("Cannot redefine the watchable list when started")
        
        validation.assert_is_iterable(columns, 'columns')
        for handle in columns:
            validation.assert_type(handle, 'columns[n]', self.ColumnDescriptor)

        self._column_descriptors = list(columns).copy()
        self._actual_vals = [None] * len(self._column_descriptors)
        self._column_map = {}
        for i in range(len(self._column_descriptors)):
            self._column_map[self._column_descriptors[i].server_id] = i

    def start(self) -> None: 
        """Start the CSV logger. Open the first file and initialize the internal states"""      
        if len(self._column_descriptors) == 0:
            raise ValueError("No watchable defined for logging")

        self._started = True
        self._actual_file_number = 0
        self._new_val_flags = [False] * len(self._column_descriptors)

        self._open_and_prepare_file()

    def stop(self) -> None:
        """Stops the CSV logger. Close the actually opened file and prevent any further logging"""
        if self._started:
            self._flush_row()
        self._csv_writer = None
        if self._actual_file_handle is not None:
            self._actual_file_handle.close()
        self._started = False

    def started(self) -> bool:
        """Return ``True`` if the CSV logger is started"""
        return  self._started

    def write(self, updates: List[ValueUpdate]) -> None:
        """Write a sequence of :class:`ValueUpdate<scrutiny.sdk.listeners.ValueUpdate> to the CSV output. """

        assert self._csv_writer is not None
        if len(updates) == 0:
            return
        
        if self._first_val_dt is None:
            self._first_val_dt = updates[0].update_timestamp
        tstart = self._first_val_dt

        def get_reltime(val:ValueUpdate) -> float:    # A getter to get the relative timestamp
            return  (val.update_timestamp-tstart).total_seconds()

        for update in updates:
            col_index = self._column_map[update.watchable.server_id]
            x = get_reltime(update)
            if x > self._actual_x:
                self._flush_row()
                self._line_counter+=1
                self._actual_x = x
                if self._lines_per_file is not None and self._line_counter >= self._lines_per_file:
                    self._switch_to_next_file()

            self._actual_vals[col_index] = update.value
            if update.watchable.datatype == EmbeddedDataType.boolean and self._convert_bool_to_int:
                self._actual_vals[col_index] = int(update.value)
            self._new_val_flags[col_index] = True

    def _flush_row(self) -> None:
        assert self._csv_writer is not None
        new_dt = self._datetime_zero_sec + timedelta(seconds=self._actual_x)
        dt_str = new_dt.strftime(self._datetime_format)
        row:List[PossibleVal] = cast(List[PossibleVal], [dt_str, self._actual_x]) + self._actual_vals

        update_str = ','.join(['1' if x else '0' for x in self._new_val_flags])
        row.append(update_str)
        self._csv_writer.writerow(row)
        self._new_val_flags = [False] * len(self._column_descriptors)   # Reset
 
    def _make_file_basename(self, number:Optional[int]) -> str:
        if number is not None:
            format_str = r'%s_%0' + str(self._file_part_0pad) + r'd%s'
            return format_str % (self._requested_basename, number, self.EXTENSION)
        else :
            return f'{self._requested_basename}{self.EXTENSION}'
    
    def _open_file_by_basename(self, basename:str) -> TextIO:

        fullpath = os.path.join(self._folder_abs, basename)
        if os.path.exists(fullpath):
            raise FileExistsError(f"File {fullpath} already exists")
        return  open(fullpath, 'w', encoding= self._csv_config.encoding, newline= self._csv_config.newline)

    def _make_csv_writer(self) -> "_csv._writer":
        assert self._actual_file_handle is not None

        return csv.writer(
            self._actual_file_handle, 
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
        self._actual_file_number+=1 
        self._open_and_prepare_file()
       
    def _open_and_prepare_file(self)-> None:
        self._line_counter = 0
        file_index:Optional[int] = self._actual_file_number
        if self._lines_per_file is None:
            file_index = None
        self._actual_file_basename = self._make_file_basename(file_index)
        self._actual_file_handle = self._open_file_by_basename(self._actual_file_basename)
        self._logger.info(f"Switched logging to {self._actual_file_basename}")
        self._csv_writer = self._make_csv_writer()
        
        for header_row in self._file_headers:
            self._csv_writer.writerow(header_row)
        if len(self._file_headers) > 0:
            self._csv_writer.writerow([])

        all_fullpaths = [d.fullpath for d in self._column_descriptors]
        has_at_least_one_fullpath = any([x is not None for x in all_fullpaths])
        if has_at_least_one_fullpath:
            self._csv_writer.writerow(["", ""] + all_fullpaths)
        table_headers:List[str] = [self.DATETIME_HEADER, self.RELTIME_HEADER] + [col.name for col in self._column_descriptors] + [self.UPDATE_FLAG_HEADER]
        self._csv_writer.writerow(table_headers)
