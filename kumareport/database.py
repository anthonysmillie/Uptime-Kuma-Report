import sqlite3

from datetime import datetime
from tokenize import Double
from urllib import request
from winreg import DeleteValue


class Database:
    db = None

    def __init__(self, database):
        Database.db = self
        self.conn = self.create_connection(database)

    def cursor(self):
        return self.conn.cursor()

    def create_connection(self, kumadb):
        """ create a database connection to the SQLite database
            specified by the db_file
        :param db_file: database file
        :return: Connection object or None
        """
        conn = None
        try:
            conn = sqlite3.connect(kumadb)
        except Error as e:
            print(e)

        return conn

    def get_monitor_interval(self, monitor_id):
        cur = self.conn.cursor()
        cur.execute("SELECT interval FROM monitor WHERE id=?", (monitor_id,))
        result = cur.fetchone()

        return result

    def number_of_requests(self, start: datetime, end: datetime):
        delta = (end - start)*24*60*60

        return delta.days

    def count_heartbeat_by_status(
            self, monitor_id, status, start: datetime, end: datetime
    ):
        cur = self.conn.cursor()
        cur.execute("SELECT count(*) FROM heartbeat WHERE monitor_id=? AND status=? AND time>=? AND time<?",
                    (monitor_id, status, start, end))
        result = cur.fetchone()

        return result[0]

    def percent_by_monitor_id_1(self, monitor_id, start: datetime, end: datetime):
        rows = self.count_heartbeat_by_monitor_id(monitor_id, start, end)
        result = self.count_heartbeat_by_status(monitor_id, 1, start, end)

        if rows == 0:
            return 0

        percentage = (result / rows) * 100
        return percentage

    def percent_by_monitor_id_2(self, monitor_id, start: datetime, end: datetime):
        rows = self.get_monitor_interval(monitor_id,)
        result = self.count_heartbeat_by_status(monitor_id, 1, start, end)
        
        if rows == 0:
            return 0

        percentage = (
            result / (self.number_of_requests(start , end) / int(rows[0]))) * 100
        return percentage

    def count_heartbeat_by_monitor_id(
        self, monitor_id, start: datetime, end: datetime
    ):
        """
        Query tasks by priority
        :param conn: the Connection object
        :param priority:
        :return:
        """
        cur = self.conn.cursor()
        cur.execute(
            "SELECT count(*) FROM heartbeat WHERE monitor_id=? AND time>? AND time <?",
            (monitor_id, start, end)
        )

        rows = cur.fetchone()

        return rows[0]
