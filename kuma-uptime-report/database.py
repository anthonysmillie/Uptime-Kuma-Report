import sqlite3
from datetime import datetime


def create_connection(database_path: str):
    """Establish a database connection."""
    try:
        conn = sqlite3.connect(database_path)
        return conn
    except sqlite3.Error as e:
        raise RuntimeError(f"Failed to connect to database: {e}")


class Database:
    db = None

    def __init__(self, database_path: str):
        Database.db = self  # Singleton pattern
        self.conn = create_connection(database_path)

    def cursor(self):
        if not self.conn:
            raise RuntimeError("Database connection not initialized.")
        return self.conn.cursor()

    def count_successful_heartbeats(self, monitor_id: int, start: datetime, end: datetime) -> int:
        """
        Count the number of successful heartbeats for a specific monitor,
        based on the `down` column (down = 0 means successful).
        """
        cur = self.cursor()
        cur.execute(
            """
            SELECT COUNT(*) 
            FROM heartbeat 
            WHERE monitor_id=? 
            AND down_count=0 
            AND time>=? 
            AND time<? 
            AND ((down_count = 0) OR (down_count > 1 AND status = 1))
            """,
            (monitor_id, start, end)
        )
        result = cur.fetchone()
        return result[0] if result else 0

    def count_total_heartbeats(self, monitor_id: int, start: datetime, end: datetime) -> int:
        """
        Count the total number of heartbeats for a specific monitor.
        """
        cur = self.cursor()
        cur.execute(
            """
            SELECT COUNT(*) 
            FROM heartbeat 
            WHERE monitor_id=? AND time>=? AND time<?
            """,
            (monitor_id, start, end)
        )
        result = cur.fetchone()
        return result[0] if result else 0

    def percent_by_monitor_id(self, monitor_id: int, start: datetime, end: datetime) -> float:
        """
        Calculate the percentage uptime (successful heartbeats) for a monitor.
        """
        total_count = self.count_total_heartbeats(monitor_id, start, end)
        successful_count = self.count_successful_heartbeats(monitor_id, start, end)

        if total_count == 0:
            return 0.0  # Avoid division by zero if there are no heartbeats
        return (successful_count / total_count) * 100