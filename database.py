"""database.py - SQLite connection, schema creation and small SQL helpers.

The database file (makerspace.db) is created automatically on first run.
"""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS members (
    member_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    phone       TEXT,
    joined_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS equipment (
    equipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    category     TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'available'
                 CHECK (status IN ('available', 'borrowed', 'maintenance'))
);

CREATE TABLE IF NOT EXISTS loans (
    loan_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id    INTEGER NOT NULL,
    equipment_id INTEGER NOT NULL,
    loan_date    TEXT NOT NULL,
    due_date     TEXT NOT NULL,
    return_date  TEXT,                      -- NULL means still on loan
    FOREIGN KEY (member_id)    REFERENCES members(member_id),
    FOREIGN KEY (equipment_id) REFERENCES equipment(equipment_id)
);
"""


class Database:
    """Wraps one SQLite connection and offers simple helper methods."""

    def __init__(self, path="makerspace.db"):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row          # access columns by name
        self.conn.execute("PRAGMA foreign_keys = ON")  # enforce foreign keys
        self.create_tables()

    def create_tables(self):
        self.conn.executescript(SCHEMA)

    def run(self, sql, params=()):
        """Run one INSERT/UPDATE/DELETE and commit. Returns the cursor."""
        with self.conn:  # commits on success, rolls back on error
            return self.conn.execute(sql, params)

    def run_transaction(self, statements):
        """Run several (sql, params) statements as ONE transaction.

        Either all succeed or none do (e.g. creating a loan AND marking the
        equipment as borrowed). Returns the lastrowid of the first statement.
        """
        first_id = None
        with self.conn:
            for index, (sql, params) in enumerate(statements):
                cursor = self.conn.execute(sql, params)
                if index == 0:
                    first_id = cursor.lastrowid
        return first_id

    def fetch_all(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def fetch_one(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()

    def close(self):
        self.conn.close()
