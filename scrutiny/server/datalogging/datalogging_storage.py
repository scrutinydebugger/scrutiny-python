#    datalogging_storage.py
#        A storage interface to save and fetch datalogging acquisition from the disk to keep
#        an history of them
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021-2023 Scrutiny Debugger

import os
import appdirs  # type: ignore
import tempfile
import logging
from scrutiny.server.datalogging.definitions.api import DataloggingAcquisition, DataSeries, AxisDefinition

import sqlite3
from datetime import datetime
from typing import Optional, Dict, List


class TempStorageWithAutoRestore:
    storage: "DataloggingStorageManager"

    def __init__(self, storage: "DataloggingStorageManager"):
        self.storage = storage

    def __enter__(self) -> "TempStorageWithAutoRestore":
        return self

    def __exit__(self, type, value, traceback):
        self.restore()

    def restore(self):
        self.storage.restore_storage()


class SQLiteSession:
    storage: "DataloggingStorageManager"
    conn: Optional[sqlite3.Connection]

    def __init__(self, storage: "DataloggingStorageManager"):
        self.storage = storage
        self.conn = None

    def __enter__(self) -> sqlite3.Connection:
        self.conn = sqlite3.connect(self.storage.get_db_filename())
        self.storage.init_db(self.conn)
        return self.conn

    def __exit__(self, type, value, traceback):
        if self.conn is not None:
            self.conn.close()


class DataloggingStorageManager:
    FILENAME = "scrutiny_datalog.sqlite"

    def __init__(self, folder):
        self.folder = folder
        self.temporary_dir = None
        self.logger = logging.getLogger(self.__class__.__name__)
        os.makedirs(self.folder, exist_ok=True)

    def use_temp_storage(self) -> TempStorageWithAutoRestore:
        """Require the storage manager to switch to a temporary directory. Used for unit testing"""
        self.temporary_dir = tempfile.TemporaryDirectory()
        return TempStorageWithAutoRestore(self)

    def restore_storage(self) -> None:
        """Require the storage manager to work on the real directory and not a temporary directory"""
        self.temporary_dir = None

    def get_storage_dir(self) -> str:
        """Ge the actual storage directory"""
        if self.temporary_dir is not None:
            return self.temporary_dir.name
        else:
            return self.folder

    def get_db_filename(self) -> str:
        return os.path.join(self.get_storage_dir(), self.FILENAME)

    def clear_all(self):
        filename = self.get_db_filename()
        if os.path.isfile(filename):
            os.remove(filename)

    def init_db(self, conn: sqlite3.Connection):
        cursor = conn.cursor()

        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS `acquisitions` (
            `id` INTEGER PRIMARY KEY AUTOINCREMENT,
            `reference_id` VARCHAR(32) UNIQUE NOT NULL,
            `name` VARCHAR(255) NULL DEFAULT NULL,
            `firmware_id` VARCHAR(32)  NOT NULL,
            `timestamp` TIMESTAMP NOT NULL DEFAULT 'NOW()',
            `x_axis` INTEGER NOT NULL
        ) 
        """)

        cursor.execute(""" 
            CREATE INDEX IF NOT EXISTS `firmware_id` 
            ON `acquisitions` (`firmware_id`)
        """)

        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS `dataseries` (
            `id` INTEGER PRIMARY KEY AUTOINCREMENT,
            `name` VARCHAR(255),
            `logged_element` TEXT,
            `axis_id` INTEGER NULL,
            `data` BLOB  NOT NULL
        ) 
        """)

        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS `axis` (
            `id` INTEGER PRIMARY KEY AUTOINCREMENT,
            `name` VARCHAR(255)
        ) 
        """)

        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS `acquisitions__dataseries` (
            `acquisition_id` INTEGER NOT NULL,
            `dataseries_id` INTEGER NOT NULL,
            PRIMARY KEY (`acquisition_id`, `dataseries_id`)
        ) 
        """)

        conn.commit()

    def get_session(self) -> SQLiteSession:
        return SQLiteSession(self)

    def save(self, acquisition: DataloggingAcquisition):
        self.logger.debug("Saving acquisition with reference_id=%s" % (str(acquisition.reference_id)))
        if acquisition.xdata is None:
            raise ValueError("Missing X-Axis data")

        with self.get_session() as conn:
            data_series_sql = """
                INSERT INTO `dataseries`
                    (`name`, `logged_element`, `axis_id`, `data`)
                VALUES (?,?,?, ?)
            """

            axis_sql = """
                INSERT INTO `axis`
                    (`name`)
                VALUES (?)
            """

            series2id_map: Dict[DataSeries, int] = {}
            cursor = conn.cursor()

            axis2id_map: Dict[AxisDefinition, int] = {}
            for axis in acquisition.get_unique_yaxis_list():
                cursor.execute(axis_sql, (axis.name,))
                assert cursor.lastrowid is not None
                axis2id_map[axis] = cursor.lastrowid

            for data in acquisition.get_data():

                cursor.execute(
                    data_series_sql,
                    (
                        data.serie.name,
                        data.serie.logged_element,
                        axis2id_map[data.axis],
                        data.serie.get_data_binary()
                    )
                )
                assert cursor.lastrowid is not None
                series2id_map[data.serie] = cursor.lastrowid

            cursor.execute(
                data_series_sql,
                (
                    acquisition.xdata.name,
                    acquisition.xdata.logged_element,
                    None,
                    acquisition.xdata.get_data_binary()
                )
            )
            assert cursor.lastrowid is not None
            xaxis_id = cursor.lastrowid
            series2id_map[acquisition.xdata] = xaxis_id

            ts: Optional[int] = None
            if acquisition.acq_time is not None:
                ts = int(acquisition.acq_time.timestamp())

            cursor.execute(
                """
                INSERT INTO `acquisitions` 
                    (`reference_id`, `name`, `firmware_id`, `timestamp`, `x_axis`)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    acquisition.reference_id,
                    acquisition.name,
                    acquisition.firmware_id,
                    ts,
                    xaxis_id
                )
            )

            acquisition_db_id = cursor.lastrowid

            for series_id in series2id_map.values():
                cursor.execute(
                    """
                    INSERT INTO `acquisitions__dataseries` 
                        (`acquisition_id`, `dataseries_id`)
                    VALUES (?, ?)
                    """,
                    (
                        acquisition_db_id,
                        series_id
                    )
                )

            conn.commit()

    def count(self, firmware_id: Optional[str] = None) -> int:
        with self.get_session() as conn:
            cursor = conn.cursor()
            nout = 0
            if firmware_id is None:
                sql = "SELECT COUNT(1) AS n FROM `acquisitions`"
                cursor.execute(sql)
                nout = cursor.fetchone()[0]
            else:
                sql = "SELECT COUNT(1) AS n FROM `acquisitions` WHERE `firmware_id`=?"
                cursor.execute(sql, (firmware_id,))
                nout = cursor.fetchone()[0]

        return nout

    def list(self, firmware_id: Optional[str] = None) -> List[str]:
        with self.get_session() as conn:
            cursor = conn.cursor()
            listout: List[str]
            if firmware_id is None:
                sql = "SELECT `reference_id` FROM `acquisitions`"
                cursor.execute(sql)
                listout = [row[0] for row in cursor.fetchall()]
            else:
                sql = "SELECT `reference_id` FROM `acquisitions` WHERE `firmware_id`=?"
                cursor.execute(sql, (firmware_id,))
                listout = [row[0] for row in cursor.fetchall()]

        return listout

    def read(self, reference_id: str) -> DataloggingAcquisition:
        with self.get_session() as conn:
            sql = """
                SELECT 
                    a.`reference_id` AS `reference_id`,
                    a.`firmware_id` AS `firmware_id`,
                    a.`timestamp` AS `timestamp`,
                    a.`name` AS `name`,
                    ds.`axis_id` AS `axis_id`,
                    ds.`name` AS `dataseries_name`,
                    ds.`logged_element` AS `logged_element`,
                    ds.`data` AS `data`,
                    CASE WHEN a.x_axis=ds.id THEN 1 ELSE 0 END AS `is_xdata`,
                    axis.`name` AS `axis_name`
                FROM `acquisitions` AS a
                LEFT JOIN `acquisitions__dataseries` AS `ad` ON `a`.`id`=`ad`.`acquisition_id`
                LEFT JOIN `dataseries` AS `ds` ON `ds`.`id`=`ad`.`dataseries_id`
                LEFT JOIN `axis` AS `axis` ON `axis`.`id`=`ds`.`axis_id`
                where a.`reference_id`=?
            """
            # SQLite doesn't let us index by name
            cols = [
                'reference_id',
                'firmware_id',
                'timestamp',
                'acquisition_name',
                'axis_id',
                'dataseries_name',
                'logged_element',
                'data',
                'is_xdata',
                'axis_name'
            ]
            colmap: Dict[str, int] = {}
            for i in range(len(cols)):
                colmap[cols[i]] = i

            cursor = conn.cursor()
            cursor.execute(sql, (reference_id,))

            rows = cursor.fetchall()
        if len(rows) == 0:
            raise LookupError('No acquisition identified by ID %s' % str(reference_id))

        acq = DataloggingAcquisition(
            reference_id=rows[0][colmap['reference_id']],
            firmware_id=rows[0][colmap['firmware_id']],
            acq_time=datetime.fromtimestamp(rows[0][colmap['timestamp']]),
            name=rows[0][colmap['acquisition_name']]
        )

        axis_id_to_def_map: Dict[int, AxisDefinition] = {}

        for row in rows:
            axis: Optional[AxisDefinition] = None
            if row[colmap['axis_id']] is not None:
                if row[colmap['axis_id']] in axis_id_to_def_map:
                    axis = axis_id_to_def_map[row[colmap['axis_id']]]
                else:
                    axis = AxisDefinition(name=row[colmap['axis_name']])
                    axis_id_to_def_map[row[colmap['axis_id']]] = axis

            if axis is None and not row[colmap['is_xdata']]:
                raise ValueError('No axis on data that is not the X-Axis')

            name = row[colmap['dataseries_name']]
            logged_element = row[colmap['logged_element']]
            data = row[colmap['data']]

            if name is None or logged_element is None or data is None:
                raise LookupError('Incomplete data in database')

            dataseries = DataSeries(name=name, logged_element=logged_element)
            dataseries.set_data_binary(data)
            if row[colmap['is_xdata']]:
                acq.set_xdata(dataseries)
            else:
                assert axis is not None
                acq.add_data(dataseries, axis)

        if acq.xdata is None:
            raise LookupError("No X-Axis in acquisition")

        return acq

    def delete(self, reference_id: str) -> None:
        with self.get_session() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM `axis` WHERE id IN (
                    SELECT DISTINCT ds.`axis_id` FROM `acquisitions` AS a
                    INNER JOIN `acquisitions__dataseries` AS ad ON a.id=ad.acquisition_id
                    INNER JOIN `dataseries` AS ds ON `ad`.`dataseries_id`=`ds`.`id`
                    WHERE a.reference_id=?
                )
                """, (reference_id,))

            cursor.execute("""
                DELETE FROM `dataseries` WHERE id IN (
                    SELECT ad.`dataseries_id` FROM `acquisitions` AS a
                    INNER JOIN `acquisitions__dataseries` AS ad ON a.id=ad.acquisition_id
                    WHERE a.reference_id=?
                )
                """, (reference_id,))

            cursor.execute("""
                DELETE FROM `acquisitions__dataseries` WHERE acquisition_id IN (
                    SELECT id FROM `acquisitions` AS a WHERE a.reference_id=?
                )
                """, (reference_id,))

            cursor.execute("DELETE FROM `acquisitions` WHERE reference_id=?", (reference_id,))
            if cursor.rowcount == 0:
                raise LookupError('No acquisition identified by ID %s' % str(reference_id))

            conn.commit()

    def update_name_by_reference_id(self, reference_id: str, name: str) -> None:
        with self.get_session() as conn:
            cursor = conn.cursor()

            cursor.execute("""
            UPDATE `acquisitions` set `name`=? where `reference_id`=?
            """, (name, reference_id))

            if cursor.rowcount == 0:
                raise LookupError('No acquisition identified by ID %s' % str(reference_id))

            conn.commit()


GLOBAL_STORAGE = appdirs.user_data_dir('datalog_storage', 'scrutiny')
DataloggingStorage = DataloggingStorageManager(GLOBAL_STORAGE)
