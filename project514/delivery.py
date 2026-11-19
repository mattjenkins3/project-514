"""Manual clock entry point and mock-only outbox dispatch."""
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from threading import Lock
from typing import Protocol

from .engine import prescribe
from .models import DENVER, Athlete, Cycle, Prescription
from .render import Message, Narrator, message, weekly
from .store import Store, stamp

MAX_ATTEMPTS = 3


class EmailProvider(Protocol):
    def deliver(self, key: str, content: Message) -> str: ...


class Scheduler(Protocol):
    def due(self, athlete: Athlete, cycle: Cycle, now: datetime) -> date | None: ...


class LocalMorning:
    """Pure due-date selector. No timer, registrations or background jobs."""

    def due(self, athlete: Athlete, cycle: Cycle, now: datetime) -> date | None:
        stamp(now)
        local = now.astimezone(DENVER)
        target = morning(athlete, local.date())
        if cycle.start <= local.date() <= cycle.end and target <= now < target + timedelta(minutes=30):
            return local.date()
        return None


class MockEmail:
    def __init__(self, fail_first: int = 0):
        self.fail_first = fail_first
        self.delivered: dict[str, Message] = {}
        self.calls = 0
        self.lock = Lock()

    def deliver(self, key: str, content: Message) -> str:
        with self.lock:
            if key not in self.delivered:
                self.calls += 1
                if self.calls <= self.fail_first:
                    raise TimeoutError("Synthetic timeout")
                self.delivered[key] = content
        return f"mock-{key}"


def morning(athlete: Athlete, when: date) -> datetime:
    return datetime.combine(when, athlete.email_time, DENVER).astimezone(UTC)


class Coach:
    def __init__(self, store: Store, athlete: Athlete, cycle: Cycle,
                 link: Callable[[date, datetime], str], narrator: Narrator | None = None):
        self.store, self.athlete, self.cycle, self.link = store, athlete, cycle, link
        self.narrator = narrator
        self.store.init_cycle(cycle)

    def prepare(self, when: date, at: datetime) -> Prescription:
        stamp(at)
        if at.astimezone(DENVER).date() != when:
            raise ValueError("Prepare against the intended local program day.")
        with self.store.transaction() as db:
            plans = self.store.plans(db, self.cycle.cycle_id)
            existing = next((p for p in plans if p.local_date == when), None)
            if existing:
                return existing
            if plans and plans[-1].local_date > when:
                raise ValueError("Prepare days chronologically. Use a fresh database for a replay.")
            history = self.store.history(db, self.cycle.cycle_id)
            status = self.store.latest_control(db, self.cycle.cycle_id, ("pause", "resume"), at)
            review = self.store.latest_control(db, self.cycle.cycle_id, ("review",), at)
            cycle = self.cycle
            if status and cycle.status in {"pilot", "active", "paused"}:
                cycle = cycle.model_copy(update={"status": "paused" if status["action"] == "pause" else "pilot"})
            resumed = datetime.fromisoformat(status["at"]) if status and status["action"] == "resume" else None
            reviewed = datetime.fromisoformat(review["at"]) if review else None
            plan = prescribe(self.athlete, cycle, when, at, history, plans, reviewed, resumed)
            summary = weekly(
                when, [*plans, plan], [c for c in history if c.local_date < when and c.submitted_at <= at]
            ) if when.weekday() == 6 else ""
            content = message(plan, self.link(when, at), summary, self.narrator)
            db.execute("INSERT INTO prescriptions VALUES (?,?,?,?)",
                       (plan.prescription_id, cycle.cycle_id, when.isoformat(), plan.model_dump_json()))
            db.execute("""INSERT INTO outbox(key,subject,plain,html,due_at,status) VALUES (?,?,?,?,?,?)""",
                       (plan.prescription_id, content.subject, content.plain, content.html,
                        stamp(morning(self.athlete, when)),
                        "suppressed" if "cycle_inactive" in plan.decision.reason_codes else "prepared"))
            return plan

    def tick(self, now: datetime, provider: EmailProvider, scheduler: Scheduler | None = None) -> str:
        when = (scheduler or LocalMorning()).due(self.athlete, self.cycle, now)
        if when is None:
            return "outside_window"
        plan = self.prepare(when, now)
        return self.dispatch(plan, now, provider)

    def dispatch(self, plan: Prescription, at: datetime, provider: EmailProvider) -> str:
        # Production provider implementations are intentionally unavailable.
        if type(provider) is not MockEmail:
            raise ValueError("Only the built-in mock email provider can dispatch in the MVP.")
        key = plan.prescription_id
        with self.store.transaction() as db:
            row = db.execute(
                """SELECT o.* FROM outbox o JOIN prescriptions p ON p.id=o.key
                   WHERE o.key=? AND p.cycle=?""", (key, self.cycle.cycle_id),
            ).fetchone()
            if row is None:
                raise ValueError("Unknown delivery.")
            if row["status"] not in {"prepared", "retry"}:
                return row["status"]
            control = self.store.latest_control(db, self.cycle.cycle_id, ("pause", "resume"), at)
            if control and control["action"] == "pause":
                db.execute("UPDATE outbox SET status='suppressed' WHERE key=?", (key,))
                return "suppressed"
            now = stamp(at)
            if row["due_at"] > now or (row["retry_at"] and row["retry_at"] > now):
                return "waiting"
            if at >= datetime.fromisoformat(row["due_at"]) + timedelta(minutes=30):
                db.execute("UPDATE outbox SET status='suppressed' WHERE key=?", (key,))
                return "suppressed"
            attempts = row["attempts"] + 1
            db.execute("UPDATE outbox SET status='sending', attempts=?, attempted_at=? WHERE key=?",
                       (attempts, stamp(at), key))
        try:
            provider_id = provider.deliver(key, Message(row["subject"], row["plain"], row["html"]))
        except TimeoutError:
            status = "retry" if attempts < MAX_ATTEMPTS else "failed"
            retry_at = stamp(at + timedelta(minutes=2**(attempts-1))) if status == "retry" else None
            with self.store.transaction() as db:
                db.execute("UPDATE outbox SET status=?, retry_at=?, error='provider_timeout' WHERE key=?",
                           (status, retry_at, key))
        else:
            status = "test"
            with self.store.transaction() as db:
                db.execute("""UPDATE outbox SET status=?, provider_id=?, retry_at=NULL, error=NULL
                              WHERE key=?""", (status, provider_id, key))
        return status
