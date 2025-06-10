#    csv_file_listener.py
#        Listener that dumps the values of the watchables into either one or multiple CSV
#        files
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = ['CSVFileListener', 'CSVConfig']

from scrutiny.core.basic_types import *
from scrutiny.sdk.listeners import ValueUpdate, BaseListener
from scrutiny.sdk.listeners.csv_logger import CSVLogger, CSVConfig
from scrutiny.tools.typing import *


class CSVFileListener(BaseListener):
    csv_logger: CSVLogger

    def __init__(self,
                 folder: str,
                 filename: str,
                 lines_per_file: Optional[int] = None,
                 datetime_format: str = r'%Y-%m-%d %H:%M:%S.%f',
                 convert_bool_to_int: bool = True,
                 file_part_0pad: int = 4,
                 csv_config: Optional[CSVConfig] = None,
                 *args: Any, **kwargs: Any):
        """Listener that writes the watchable values into a CSV file as they are received

        Adding/removing subscriptions while running is **not** allowed since it affects the list of columns

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

        self.csv_logger = CSVLogger(
            folder=folder,
            filename=filename,
            datetime_format=datetime_format,
            lines_per_file=lines_per_file,
            convert_bool_to_int=convert_bool_to_int,
            file_part_0pad=file_part_0pad,
            csv_config=csv_config,
            logger=self._logger
        )

    def setup(self) -> None:
        handles = sorted(list(self.get_subscriptions()), key=lambda x: x.display_path)
        self.csv_logger.define_columns_from_handles(handles)
        self.csv_logger.start()

    def receive(self, updates: List[ValueUpdate]) -> None:
        self.csv_logger.write(updates)

    def teardown(self) -> None:
        self.csv_logger.stop()

    def allow_subscription_changes_while_running(self) -> bool:
        return False    # Do not allow because it affect the list of columns
