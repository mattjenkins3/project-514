"""Transactional SQLite state. Each operation owns its connection."""
import sqlite3
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Iterator
from hashlib import sha256

from .models import CLIMBING, Checkin, CheckinData, Cycle, Kind, Prescription

SCHEMA = """
CREATE TABLE IF NOT EXISTS cycles (
    id TEXT PRIMARY KEY, body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prescriptions (
    id TEXT PRIMARY KEY, cycle TEXT NOT NULL REFERENCES cycles(id),
    day TEXT NOT NULL, body TEXT NOT NULL, UNIQUE(cycle, day)
);
CREATE TABLE IF NOT EXISTS checkins (
    id TEXT PRIMARY KEY, prescription TEXT NOT NULL REFERENCES prescriptions(id),
    revision INTEGER NOT NULL, body TEXT NOT NULL, UNIQUE(prescription, revision)
);
CREATE TABLE IF NOT EXISTS controls (
    id INTEGER PRIMARY KEY, cycle TEXT NOT NULL REFERENCES cycles(id),
    at TEXT NOT NULL, action TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outbox (
    key TEXT PRIMARY KEY REFERENCES prescriptions(id), kind TEXT NOT NULL DEFAULT 'morning',
    subject TEXT NOT NULL, plain TEXT NOT NULL, html TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'prepared', attempts INTEGER NOT NULL DEFAULT 0,
    attempted_at TEXT, due_at TEXT NOT NULL, retry_at TEXT, provider_id TEXT, error TEXT
);
PRAGMA user_version = 1;
"""


def stamp(when: datetime) -> str:
    if when.tzinfo is None:
        raise ValueError("Use timezone-aware timestamps.")
    return when.astimezone(UTC).isoformat(timespec="microseconds")


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.touch(mode=0o600, exist_ok=True)
        with self.transaction() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError("Unsupported SQLite schema version.")
            db.executescript(SCHEMA)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def init_cycle(self, cycle: Cycle) -> None:
        with self.transaction() as db:
            db.execute("INSERT OR IGNORE INTO cycles VALUES (?,?)", (cycle.cycle_id, cycle.model_dump_json()))
            if self.cycle(db, cycle.cycle_id) != cycle:
                raise ValueError("This cycle ID already has a different definition.")

    @staticmethod
    def cycle(db: sqlite3.Connection, cycle_id: str) -> Cycle:
        row = db.execute("SELECT body FROM cycles WHERE id=?", (cycle_id,)).fetchone()
        if not row:
            raise ValueError("Unknown cycle.")
        return Cycle.model_validate_json(row["body"])

    @staticmethod
    def plans(db: sqlite3.Connection, cycle_id: str) -> list[Prescription]:
        return [Prescription.model_validate_json(row["body"]) for row in db.execute(
            "SELECT body FROM prescriptions WHERE cycle=? ORDER BY day", (cycle_id,),
        )]

    @staticmethod
    def history(db: sqlite3.Connection, cycle_id: str) -> list[Checkin]:
        return [Checkin.model_validate_json(row["body"]) for row in db.execute(
            """SELECT c.body FROM checkins c JOIN prescriptions p ON p.id=c.prescription
               WHERE p.cycle=? ORDER BY p.day, c.revision""", (cycle_id,),
        )]

    def control(self, cycle_id: str, action: str, at: datetime) -> None:
        if action not in {"pause", "resume", "review"}:
            raise ValueError("Unknown control.")
        with self.transaction() as db:
            self.cycle(db, cycle_id)
            db.execute("INSERT INTO controls(cycle, at, action) VALUES (?,?,?)",
                       (cycle_id, stamp(at), action))

    @staticmethod
    def latest_control(db: sqlite3.Connection, cycle_id: str, actions: tuple[str, ...],
                       at: datetime) -> sqlite3.Row | None:
        placeholders = ",".join("?" for _ in actions)
        return db.execute(
            f"""SELECT action, at FROM controls WHERE cycle=? AND at<=? AND action IN ({placeholders})
                ORDER BY at DESC, id DESC LIMIT 1""",
            (cycle_id, stamp(at), *actions),
        ).fetchone()

    def submit(self, plan: Prescription, data: CheckinData, at: datetime, expected_revision: int) -> Checkin:
        if at.tzinfo is None or at < plan.created_at:
            raise ValueError("Submission precedes the prescription.")
        with self.transaction() as db:
            exists = db.execute("SELECT body FROM prescriptions WHERE id=?", (plan.prescription_id,)).fetchone()
            if not exists or Prescription.model_validate_json(exists["body"]) != plan:
                raise ValueError("Unknown prescription.")
            if data.completion == "rest_done" and plan.session.kind != Kind.REST:
                raise ValueError("Use missed if you rested instead of a planned session.")
            if data.pump is not None or data.late_technique is not None:
                if plan.session.kind not in CLIMBING:
                    raise ValueError("Forearm pump and route technique are for climbing sessions.")
            latest = db.execute(
                "SELECT revision, body FROM checkins WHERE prescription=? ORDER BY revision DESC LIMIT 1",
                (plan.prescription_id,),
            ).fetchone()
            revision = latest["revision"] if latest else 0
            if revision != expected_revision:
                raise ValueError("This form was already submitted or corrected. Reload before editing.")
            if latest and at < Checkin.model_validate_json(latest["body"]).submitted_at:
                raise ValueError("Correction precedes an earlier submission.")
            item = Checkin(checkin_id=sha256(f"{plan.prescription_id}:{revision+1}".encode()).hexdigest()[:24], prescription_id=plan.prescription_id,
                           local_date=plan.local_date, submitted_at=at, revision=revision+1, data=data)
            db.execute("INSERT INTO checkins VALUES (?,?,?,?)",
                       (item.checkin_id, plan.prescription_id, item.revision, item.model_dump_json()))
        return item


def latest_checkins(history: list[Checkin]) -> dict[date, Checkin]:
    return {c.local_date: c for c in sorted(history, key=lambda entry: entry.revision)}
