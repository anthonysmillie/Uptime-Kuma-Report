import sqlite3

from datetime import datetime


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

    def count_heartbeat_by_status(
            self, monitor_id, status, start: datetime, end: datetime
    ):
        cur = self.conn.cursor()
        cur.execute("SELECT count(*) FROM heartbeat WHERE monitor_id=? AND status=? AND time>? AND time <?",
                    (monitor_id, status, start, end))
        result = cur.fetchone()

        return result[0]

    def percent_by_monitor_id(self, monitor_id, start: datetime, end: datetime):
        rows = self.count_heartbeat_by_monitor_id(monitor_id, start, end)
        result = self.count_heartbeat_by_status(monitor_id, 1, start, end)

        if rows == 0:
            return 0

        percentage = (result / rows) * 100
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
