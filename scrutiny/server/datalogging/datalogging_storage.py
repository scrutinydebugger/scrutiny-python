#    datalogging_storage.py
#        A storage interface to save and fetch datalogging acquisition from the disk to keep
#        an history of them
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

import os
import appdirs  # type: ignore
import tempfile
import logging
import traceback
from pathlib import Path
from datetime import datetime
import sqlite3
import hashlib
import types

from scrutiny.core.datalogging import DataloggingAcquisition, DataSeries, AxisDefinition
from typing import List, Dict, Optional, Tuple, Type, Literal, Any


class BadVersionError(Exception):
    hash: str

    def __init__(self, hash: str, *args: Any, **kwargs: Any) -> None:
        self.hash = hash
        super().__init__(*args, **kwargs)


class TempStorageWithAutoRestore:
    storage: "DataloggingStorageManager"

    def __init__(self, storage: "DataloggingStorageManager") -> None:
        self.storage = storage

    def __enter__(self) -> "TempStorageWithAutoRestore":
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[types.TracebackType]) -> Literal[False]:
        self.restore()
        return False

    def restore(self) -> None:
        self.storage.restore_storage()


class SQLiteSession:
    storage: "DataloggingStorageManager"
    conn: Optional[sqlite3.Connection]

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.conn = None

    def __enter__(self) -> sqlite3.Connection:
        self.conn = sqlite3.connect(self.filename)
        return self.conn

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[types.TracebackType]) -> Literal[False]:
        if self.conn is not None:
            self.conn.close()
        return False


class DataloggingStorageManager:
    """Provides an interface to the filesystem to store and read back datalogging acquisitions. Uses SQLite3 as storage engine"""
    FILENAME = "scrutiny_datalog.sqlite"

    folder: str  # Working folder
    temporary_dir: Optional["tempfile.TemporaryDirectory[str]"]    # A temporary work folder mainly used for unit tests
    logger: logging.Logger  # The logger
    unavailable: bool       # Flags indicating that the storage can or cannot be used
    init_count: int
    actual_hash: Optional[str]

    def __init__(self, folder: str) -> None:
        self.folder = folder
        self.temporary_dir = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self.unavailable = True
        self.init_count = 0
        self.actual_hash = None
        os.makedirs(self.folder, exist_ok=True)

    def use_temp_storage(self) -> TempStorageWithAutoRestore:
        """Require the storage manager to switch to a temporary directory. Used for unit testing"""
        self.temporary_dir = tempfile.TemporaryDirectory()  # Directory is deleted when this object is destroyed. Need to keep a reference.
        self.initialize()
        return TempStorageWithAutoRestore(self)

    def restore_storage(self) -> None:
        """Require the storage manager to work on the real directory and not a temporary directory"""
        self.temporary_dir = None

    def get_storage_dir(self) -> str:
        """Get the actual storage directory"""
        if self.temporary_dir is not None:
            return self.temporary_dir.name
        else:
            return self.folder

    def get_db_filename(self) -> str:
        """Returns the filename of the database"""
        return os.path.join(self.get_storage_dir(), self.FILENAME)

    def clear_all(self) -> None:
        """Deletes the database content"""
        # This method should work without prior initialization.
        # It's a fallback solution to restore a corrupted storage
        filename = self.get_db_filename()
        if os.path.isfile(filename):
            os.remove(filename)
            self.initialize()

    def initialize(self) -> None:
        """Initialize the storage. Make sure the database is accessible and valid. Rebuild it if something is broken"""
        self.logger.debug('Initializing datalogging storage. DB file at %s' % self.get_db_filename())
        self.unavailable = True
        err: Optional[Exception] = None

        try:
            if not os.path.isfile(self.get_db_filename()):
                with SQLiteSession(self.get_db_filename()) as conn:
                    self.create_db_if_not_exists(conn)

            try:
                with SQLiteSession(self.get_db_filename()) as conn:
                    self.actual_hash = self.check_structure_version(conn)
            except BadVersionError as e:
                self.actual_hash = None
                self.backup_db(e.hash)

            with SQLiteSession(self.get_db_filename()) as conn:
                self.create_db_if_not_exists(conn)
                if self.actual_hash is None:
                    self.actual_hash = self.read_hash(conn)
            self.unavailable = False
            self.init_count += 1
            self.logger.debug('Datalogging storage ready')
        except Exception as e:
            self.actual_hash = None
            self.logger.error('Failed to initialize datalogging storage. Resetting storage at %s. %s' % (self.get_db_filename(), str(e)))
            self.logger.debug(traceback.format_exc())
            err = e

        if err:
            try:
                self.clear_all()
                self.logger.debug('Datalogging storage cleared')
            except Exception as e:
                self.logger.error("Failed to reset storage. Datalogging storage will not be accessible. %s" % str(e))
                self.logger.debug(traceback.format_exc())
                return

            try:
                with SQLiteSession(self.get_db_filename()) as conn:
                    self.create_db_if_not_exists(conn)
                    self.actual_hash = self.read_hash(conn)
                self.unavailable = False
                self.logger.debug('Datalogging storage ready')
            except Exception as e:
                self.logger.error('Failed to initialize datalogging storage a 2nd time. Datalogging storage will not be accessible. %s' % str(e))
                self.logger.debug(traceback.format_exc())

    def read_hash(self, conn: sqlite3.Connection) -> str:
        """Reads the version of the storage from the database. Used for future-proofing"""
        cursor = conn.cursor()
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name")
        rows = cursor.fetchall()
        if len(rows) == 0:
            raise RuntimeError('No database structure available')

        sha1 = hashlib.sha1()
        for row in rows:
            sha1.update(str(row[0]).encode('utf8'))
            sha1.update(str(row[1]).encode('utf8'))

        return sha1.hexdigest()

    def check_structure_version(self, conn: sqlite3.Connection) -> str:
        """Check that the version of the storage is the one handled by the code. Future-proofing"""
        read_hash = self.read_hash(conn)
        with tempfile.TemporaryDirectory() as dirname:
            with SQLiteSession(os.path.join(dirname, 'temp.sqlite')) as conn2:
                self.create_db_if_not_exists(conn2)
                expected_hash = self.read_hash(conn2)

        if read_hash != expected_hash:
            self.logger.warning('Storage version mismatch.')
            raise BadVersionError(read_hash, "Read structure hash was %s. Expected %s" % (read_hash, expected_hash))

        return read_hash

    def backup_db(self, previous_hash: str) -> None:
        """Makes a backup of the database and identify the file with the given version number"""
        storage_file_path = Path(self.get_db_filename())
        date = datetime.now().strftime(r"%Y%m%d_%H%M%S")
        backup_file = os.path.join(storage_file_path.parent, '%s_datalogging_storage_%s_backup%s' %
                                   (date, previous_hash, storage_file_path.suffix))
        if os.path.isfile(str(storage_file_path)):
            try:
                os.rename(str(storage_file_path), backup_file)
                self.logger.info("Datalogging storage structure has changed and will now be upgraded. Old file backed up here: %s" %
                                 (backup_file))
            except Exception as e:
                self.logger.error("Failed to backup old storage. %s" % str(e))

    def get_init_count(self) -> int:
        return self.init_count

    def get_db_hash(self) -> Optional[str]:
        return self.actual_hash

    def create_db_if_not_exists(self, conn: sqlite3.Connection) -> None:
        """Creates the database into the file using CREATE TABLE IF NOT EXISTS"""
        cursor = conn.cursor()

        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS `acquisitions` (
            `id` INTEGER PRIMARY KEY AUTOINCREMENT,
            `reference_id` VARCHAR(32) UNIQUE NOT NULL,
            `name` VARCHAR(255) NULL DEFAULT NULL,
            `firmware_id` VARCHAR(32)  NOT NULL,
            `firmware_name` VARCHAR(255)  NULL,
            `timestamp` TIMESTAMP NOT NULL DEFAULT 'NOW()',
            `trigger_index` INTEGER NULL
        ) 
        """)

        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS `axis` (
            `id` INTEGER PRIMARY KEY AUTOINCREMENT,
            `acquisition_id` INTEGER NOT NULL,
            `axis_id` INTEGER NOT NULL,
            `is_xaxis` INTEGER NOT NULL,
            `name` VARCHAR(255)
        ) 
        """)

        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS `dataseries` (
            `id` INTEGER PRIMARY KEY AUTOINCREMENT,
            `name` VARCHAR(255),
            `logged_element` TEXT,
            `axis_id` INTEGER NULL,
            `position` INTEGER NOT NULL,
            `data` BLOB  NOT NULL
        ) 
        """)

        cursor.execute(""" 
            CREATE INDEX IF NOT EXISTS `idx_axis_acquisition_id` 
            ON `axis` (`acquisition_id`)
        """)

        cursor.execute(""" 
            CREATE INDEX IF NOT EXISTS `idx_axis_ref_axis_id` 
            ON `axis` (`acquisition_id`, `axis_id`)
        """)

        cursor.execute(""" 
            CREATE INDEX IF NOT EXISTS `idx_axis_acquisition_id` 
            ON `axis` (`acquisition_id`)
        """)

        cursor.execute(""" 
            CREATE INDEX IF NOT EXISTS `idx_dataseries_axis_id` 
            ON `dataseries` (`axis_id`)
        """)

        conn.commit()

    def get_session(self) -> SQLiteSession:
        """Open a connection to the active database file if possible"""
        if self.unavailable:
            raise RuntimeError('Datalogging Storage is not accessible.')
        return SQLiteSession(self.get_db_filename())

    def save(self, acquisition: DataloggingAcquisition) -> None:
        """Writes an acquisition to the storage"""
        self.logger.debug("Saving acquisition with reference_id=%s" % (str(acquisition.reference_id)))
        if acquisition.xdata is None:
            raise ValueError("Missing X-Axis data")

        with self.get_session() as conn:
            cursor = conn.cursor()
            ts: Optional[int] = None
            if acquisition.acq_time is not None:
                ts = int(acquisition.acq_time.timestamp())

            cursor.execute(
                """
                INSERT INTO `acquisitions` 
                    (`reference_id`, `name`, `firmware_id`, `firmware_name`, `timestamp`, `trigger_index`)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    acquisition.reference_id,
                    acquisition.name,
                    acquisition.firmware_id,
                    acquisition.firmware_name,
                    ts,
                    acquisition.trigger_index
                )
            )

            if cursor.lastrowid is None:
                raise RuntimeError('Failed to insert Acquisition in DB')
            acquisition_db_id = cursor.lastrowid

            axis_sql = """
                INSERT INTO `axis`
                    (`acquisition_id`, `axis_id`, `name`, 'is_xaxis' )
                VALUES (?,?,?,?)
                """
            axis_to_id_map: Dict[AxisDefinition, int] = {}
            all_axis = acquisition.get_unique_yaxis_list()
            for axis in all_axis:
                if axis.axis_id == -1:
                    raise ValueError("Axis External ID cannot be -1, reserved value.")
                cursor.execute(axis_sql, (acquisition_db_id, axis.axis_id, axis.name, 0))
                if cursor.lastrowid is None:
                    raise RuntimeError('Failed to insert axis %s in DB', str(axis.name))
                axis_to_id_map[axis] = cursor.lastrowid

            cursor.execute(axis_sql, (acquisition_db_id, -1, 'X-Axis', 1))
            x_axis_db_id = cursor.lastrowid
            if x_axis_db_id is None:
                raise RuntimeError('Failed to insert X-Axis in DB')

            data_series_sql = """
                INSERT INTO `dataseries`
                    (`name`, `logged_element`, `axis_id`, `data`, `position`)
                VALUES (?,?,?,?, ?)
            """
            position = 0
            for data in acquisition.get_data():
                cursor.execute(data_series_sql, (
                    data.series.name,
                    data.series.logged_element,
                    axis_to_id_map[data.axis],
                    data.series.get_data_binary(),
                    position)
                )
                position += 1

            cursor.execute(data_series_sql, (
                acquisition.xdata.name,
                acquisition.xdata.logged_element,
                x_axis_db_id,
                acquisition.xdata.get_data_binary(),
                position)
            )

            conn.commit()

    def count(self, firmware_id: Optional[str] = None) -> int:
        """Returns the number of acquisition saved in the storage"""
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
        """Return the list of acquisitions available in the storage"""
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
        """Reads a datalogging acquisition form the storage"""
        with self.get_session() as conn:
            sql = """
                SELECT 
                    `acq`.`reference_id` AS `reference_id`,
                    `acq`.`firmware_id` AS `firmware_id`,
                    `acq`.`firmware_name` AS `firmware_name`,
                    `acq`.`timestamp` AS `timestamp`,
                    `acq`.`name` AS `name`,
                    `acq`.`trigger_index` as `trigger_index`,
                    `axis`.`name` AS `axis_name`,
                    `axis`.`axis_id` AS `axis_axis_id`,
                    `axis`.`is_xaxis` AS `is_xaxis`,
                    `ds`.`axis_id` AS `axis_id`,
                    `ds`.`name` AS `dataseries_name`,
                    `ds`.`logged_element` AS `logged_element`,
                    `ds`.`data` AS `data`
                FROM `acquisitions` AS `acq`
                LEFT JOIN `axis` AS `axis` ON `axis`.`acquisition_id`=`acq`.`id`
                INNER JOIN `dataseries` AS `ds` ON `ds`.`axis_id`=`axis`.`id`
                WHERE `acq`.`reference_id`=?
                ORDER BY `ds`.`position`
            """
            # SQLite doesn't let us index by name
            cols = [
                'reference_id',
                'firmware_id',
                'firmware_name',
                'timestamp',
                'acquisition_name',
                'trigger_index',
                'axis_name',
                'axis_axis_id',
                'is_xaxis',
                'axis_id',
                'dataseries_name',
                'logged_element',
                'data'
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
            name=rows[0][colmap['acquisition_name']],
            firmware_name=rows[0][colmap['firmware_name']],
        )

        # Needs to maps AxisDefinition instances to the DB id to avoid duplicates
        yaxis_id_to_def_map: Dict[int, AxisDefinition] = {}

        for row in rows:
            name = row[colmap['dataseries_name']]
            logged_element = row[colmap['logged_element']]
            data = row[colmap['data']]

            if name is None or logged_element is None or data is None:
                raise LookupError('Incomplete data in database')

            dataseries = DataSeries(name=name, logged_element=logged_element)
            dataseries.set_data_binary(data)

            if row[colmap['axis_id']] is not None:
                if not row[colmap['is_xaxis']]:  # Y-Axis
                    axis: AxisDefinition
                    if row[colmap['axis_id']] in yaxis_id_to_def_map:
                        axis = yaxis_id_to_def_map[row[colmap['axis_id']]]
                    else:
                        axis = AxisDefinition(name=row[colmap['axis_name']], axis_id=row[colmap['axis_axis_id']])
                        yaxis_id_to_def_map[row[colmap['axis_id']]] = axis
                    acq.add_data(dataseries, axis)
                else:
                    acq.set_xdata(dataseries)

        if acq.xdata is None:
            raise LookupError("No X-Axis in acquisition")

        acq.set_trigger_index(rows[0][colmap['trigger_index']])

        return acq

    def delete(self, reference_id: str) -> None:
        """Delete a datalogging acquisition from the storage"""
        with self.get_session() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM `dataseries` WHERE axis_id IN (
                    SELECT `axis`.`id` FROM `axis`
                    INNER JOIN `acquisitions` as `acq` on `acq`.`id`=`axis`.`acquisition_id`
                    WHERE `acq`.`reference_id`=?
                )
                """, (reference_id,))

            cursor.execute("""
                DELETE FROM `axis` WHERE `acquisition_id` IN (
                    SELECT `id` FROM `acquisitions` WHERE `reference_id`=?
                )
                """, (reference_id,))

            cursor.execute("DELETE FROM `acquisitions` WHERE reference_id=?", (reference_id,))
            if cursor.rowcount == 0:
                raise LookupError('No acquisition identified by ID %s' % str(reference_id))

            conn.commit()

    def update_acquisition_name(self, reference_id: str, name: str) -> None:
        """Change the name of an acquisition"""
        with self.get_session() as conn:
            cursor = conn.cursor()

            cursor.execute("""
            UPDATE `acquisitions` set `name`=? where `reference_id`=?
            """, (name, reference_id))

            if cursor.rowcount == 0:
                raise LookupError('No acquisition identified by ID %s' % str(reference_id))

            conn.commit()

    def update_axis_name(self, reference_id: str, axis_id: int, new_name: str) -> None:
        """Change the name of an axis associated with an acquisition"""
        with self.get_session() as conn:
            cursor = conn.cursor()

            cursor.execute("""
            UPDATE `axis` SET `name`=? WHERE `id` IN (
                SELECT `axis`.`id` FROM `axis` 
                INNER JOIN `acquisitions` AS `acq` ON `acq`.`id`=`axis`.`acquisition_id`
                WHERE `acq`.`reference_id`=? AND `axis`.`axis_id`=?
            )
            """, (new_name, reference_id, axis_id))

            if cursor.rowcount == 0:
                raise LookupError('No acquisition identified by ID %s' % str(reference_id))

            conn.commit()

    def get_size(self) -> int:
        return os.path.getsize(self.get_db_filename())

    def get_timerange(self) -> Optional[Tuple[datetime, datetime]]:
        with self.get_session() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT 
                    MAX(`timestamp`) as newest,
                    MIN(`timestamp`) as oldest
                FROM `acquisitions`
            """)

            rows = cursor.fetchall()
            if len(rows) == 0:
                return None

            if len(rows) != 1:
                raise RuntimeError("Got more than 1 row, this is not supposed to happen")

            if rows[0][0] is None or rows[0][1] is None:
                return None

            newest = datetime.fromtimestamp(rows[0][0])
            oldest = datetime.fromtimestamp(rows[0][1])
            return oldest, newest


GLOBAL_STORAGE = appdirs.user_data_dir('scrutiny')
DataloggingStorage = DataloggingStorageManager(GLOBAL_STORAGE)
