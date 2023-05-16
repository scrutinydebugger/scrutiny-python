import argparse
import logging

from .base_command import BaseCommand
from typing import Optional, List


class ExportDatalog(BaseCommand):
    _cmd_name_ = 'export-datalog'
    _brief_ = 'Export a datalogging acquisition to a file'
    _group_ = 'Datalogging'

    parser: argparse.ArgumentParser
    parsed_args: Optional[argparse.Namespace] = None

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('reference_id', help='The acquisition reference ID')
        self.parser.add_argument('--csv', help='Output to CSV file')

    def run(self) -> Optional[int]:
        from scrutiny.server.datalogging.datalogging_storage import DataloggingStorage
        from scrutiny.core.sfd_storage import SFDStorage

        self.parsed_args = self.parser.parse_args(self.args)
        DataloggingStorage.initialize()

        acquisition = DataloggingStorage.read(reference_id=self.parsed_args.reference_id)

        # Check if at least one of the supported is selected
        if not self.parsed_args.csv:
            raise ValueError("At least one  export method must be specified")

        if self.parsed_args.csv:
            import csv
            with open(self.parsed_args.csv, 'w', encoding='utf8', newline='') as f:
                writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                writer.writerow(['Acquisition Name', acquisition.name])
                writer.writerow(['Acquisition ID', acquisition.reference_id])
                writer.writerow(['Acquisition time', acquisition.acq_time.strftime(r"%Y-%m-%d %H:%M:%S")])
                writer.writerow(['Firmware ID', acquisition.firmware_id])
                firmware_name = 'N/A'
                if SFDStorage.is_installed(acquisition.firmware_id):
                    firmware_meta = SFDStorage.get_metadata(acquisition.firmware_id)
                    firmware_name = "%s V%s" % (firmware_meta['project_name'], firmware_meta['version'])
                writer.writerow(['Firmware Name', firmware_name])
                writer.writerow([])

                header_row = [acquisition.xdata.name] + [ydata.series.name for ydata in acquisition.ydata]
                writer.writerow(header_row)
                for ydata in acquisition.ydata:
                    if len(acquisition.xdata.data) != len(ydata.series.data):
                        logging.error("Data of series %s does not have the same length as the X-Axis" % ydata.series.name)

                for i in range(len(acquisition.xdata.data)):
                    writer.writerow([acquisition.xdata.data[i]] + [ydata.series.data[i] for ydata in acquisition.ydata])

        return 0
