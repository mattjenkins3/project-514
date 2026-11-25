"""Date-keyed records. Each mutation and its dependent changes share a transaction."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import psycopg


class Records:
    def __init__(self, connection, postgres):
        self.connection = connection
        self.marker = "%s" if postgres else "?"

    def execute(self, sql, args=()):
        return self.connection.execute(sql.replace("?", self.marker), args)

    def get(self, kind, day=""):
        row = self.execute("SELECT payload FROM entry WHERE kind=? AND day=?", (kind, day)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, kind, day, data):
        self.execute(
            "INSERT INTO entry(kind,day,payload) VALUES(?,?,?) ON CONFLICT(kind,day) "
            "DO UPDATE SET payload=excluded.payload",
            (kind, day, json.dumps(data)),
        )

    def remove(self, kind, day=""):
        self.execute("DELETE FROM entry WHERE kind=? AND day=?", (kind, day))

    def recent(self, kind, end, limit, start=""):
        rows = self.execute(
            "SELECT day,payload FROM entry WHERE kind=? AND day>=? AND day<=? ORDER BY day DESC LIMIT ?",
            (kind, start, end, limit),
        )
        return {day: json.loads(payload) for day, payload in rows}


@contextmanager
def transaction(settings, write=False):
    dsn = settings.get("DATABASE_URL")
    if dsn:
        conn = psycopg.connect(dsn, connect_timeout=8, sslmode="require")
    else:
        # A hosted app must never silently start again with an empty local database.
        path = settings.get("LOCAL_SQLITE_PATH")
        if not path:
            raise ValueError("Configure a durable database.")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=10)
    try:
        if dsn:
            conn.execute("SET LOCAL search_path TO project514, pg_catalog")
            if write:
                conn.execute("SELECT pg_advisory_xact_lock(5140514)")
        else:
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS entry(kind TEXT, day TEXT, payload TEXT NOT NULL, PRIMARY KEY(kind, day))"
            )
        yield Records(conn, bool(dsn))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
