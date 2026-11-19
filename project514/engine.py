"""Pure periodization and decision rules. Inputs are as-of snapshots."""
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Literal

from pydantic import Field

from .models import (
    CLIMBING, DENVER, HARD_FINGER, Athlete, Checkin, Cycle, Decision, Kind, Prescription,
    Record, Session,
)
from .nutrition import target


class Week(Record):
    phase: Literal["reentry", "base", "deload", "build", "specific", "taper"]
    climb_minutes: tuple[int, int, int]
    run_miles: tuple[float, float, float]
    boulder_attempts: int
    aerobic_minutes: int
    saturday: Kind
    saturday_attempts: int
    interval_minutes: Literal[0, 1, 2, 3]
    strength_sets: Literal[0, 2, 3]
    lesson: str


class Program(Record):
    version: Literal["1.0.0"]
    weeks: tuple[Week, ...] = Field(min_length=12, max_length=12)


PROGRAM = Program.model_validate_json(
    (Path(__file__).parent / "data" / "program-v1.json").read_text()
)
HIGH_RPE = 9
HIGH_PUMP = 8
RECOVERY_DAYS = 7
VOLUME_FACTOR = 0.7
REENTRY_RUN_CAP = 2.0
REENTRY_CLIMB_CAP = 50


def baseline(week: int, weekday: int) -> Session:
    if not (1 <= week <= 12 and 0 <= weekday <= 6):
        raise ValueError("Invalid program week or weekday.")
    row = PROGRAM.weeks[week - 1]
    mon, wed, sat = row.climb_minutes
    tue, thu, sun = row.run_miles
    monday = Kind.TECHNIQUE if row.phase in {"reentry", "deload", "taper"} else Kind.BOULDER
    return (
        Session(kind=monday, minutes=mon, attempts=row.boulder_attempts if monday == Kind.BOULDER else 0,
                continuous_minutes=row.aerobic_minutes if monday == Kind.TECHNIQUE else 0),
        Session(kind=Kind.EASY_RUN, miles=tue, minutes=round(12*tue), strength_sets=row.strength_sets),
        Session(kind=Kind.TECHNIQUE, minutes=wed, continuous_minutes=row.aerobic_minutes),
        Session(kind=Kind.INTERVALS if row.interval_minutes else Kind.EASY_RUN,
                miles=thu, minutes=max(35, round(12*thu)) if row.interval_minutes else round(12*thu),
                effort_minutes=row.interval_minutes),
        Session(kind=Kind.REST, minutes=0),
        Session(kind=row.saturday, minutes=sat, attempts=row.saturday_attempts,
                continuous_minutes=row.aerobic_minutes if row.saturday == Kind.TECHNIQUE else 0),
        Session(kind=Kind.EASY_RUN, miles=sun, minutes=round(12*sun)),
    )[weekday]


def _reduced(plan: Session, discomfort: bool = False, hold: Session | None = None) -> Session:
    if plan.kind == Kind.REST or (discomfort and plan.kind in CLIMBING):
        return Session(kind=Kind.REST, minutes=0)
    minutes = int(plan.minutes * VOLUME_FACTOR)
    if plan.kind in CLIMBING:
        limit = hold.minutes if hold and hold.kind in CLIMBING else REENTRY_CLIMB_CAP
        return Session(kind=Kind.TECHNIQUE, minutes=min(minutes, limit), continuous_minutes=5)
    limit = hold.miles if hold and hold.miles else REENTRY_RUN_CAP
    time_limit = hold.minutes if hold and hold.miles else round(12 * REENTRY_RUN_CAP)
    return Session(kind=Kind.EASY_RUN, minutes=min(minutes, time_limit),
                   miles=min(int(plan.miles * VOLUME_FACTOR * 10) / 10, limit))


def prescribe(athlete: Athlete, cycle: Cycle, when: date, at: datetime,
              history: Sequence[Checkin] = (), previous: Sequence[Prescription] = (),
              reviewed_at: datetime | None = None, resumed_at: datetime | None = None) -> Prescription:
    if at.tzinfo is None or athlete.athlete_id != cycle.athlete_id:
        raise ValueError("An aware cutoff and matching athlete are required.")
    if reviewed_at is not None and reviewed_at > at:
        reviewed_at = None
    day = cycle.day(when)
    week = (day - 1) // 7 + 1
    row = PROGRAM.weeks[week - 1]
    base = baseline(week, when.weekday())
    recent_by_day: dict[date, Checkin] = {}
    unresolved_red = []
    for entry in sorted(history, key=lambda c: (c.local_date, c.revision)):
        if not (cycle.start <= entry.local_date < when and entry.submitted_at <= at):
            continue
        data = entry.data
        if (data.discomfort == "significant_or_worsening" or data.symptom != "none") and (
            reviewed_at is None or entry.submitted_at > reviewed_at
        ):
            unresolved_red.append(entry)
        if (when - entry.local_date).days <= RECOVERY_DAYS:
            recent_by_day[entry.local_date] = entry
    yesterday = recent_by_day.get(when - timedelta(days=1))
    last_two = [c for d, c in recent_by_day.items() if (when - d).days <= 2]
    recent = list(recent_by_day.values())
    reasons = []
    readiness = "green"
    missing = yesterday is None
    review = bool(unresolved_red) or sum(c.data.discomfort != "none" for c in recent) >= 2
    reducing = bool(yesterday and yesterday.data.reduce_next)
    sore = any(c.data.discomfort != "none" or c.data.low_load_hang_minutes for c in last_two)
    if unresolved_red:
        reasons.append("urgent_chest_or_breathing" if any(
            c.data.symptom == "chest_or_breathing" for c in unresolved_red
        ) else "red_flag_requires_review")
    if review and not unresolved_red:
        reasons.append("persistent_discomfort")
    if missing:
        reasons.append("missing_previous_checkin")
    if len(recent) < min(day - 1, 7):
        reasons.append("incomplete_recent_history")
    incomplete = {"partial", "missed"}
    if (yesterday and yesterday.data.completion in incomplete) or (
        sum(c.data.completion in incomplete for c in recent) >= 2
    ):
        reasons.append("incomplete_no_catchup")
    if reducing:
        reasons.append("athlete_requested_reduction")
    if sore:
        reasons.append("recent_discomfort_or_extra_finger_load")
    if any(
        c.data.energy == "poor" or c.data.sleep == "poor" or c.data.nutrition == "under_fueled"
        or (c.data.rpe or 0) >= HIGH_RPE or (c.data.pump or 0) >= HIGH_PUMP
        for c in last_two
    ) or sum((c.data.rpe or 0) >= HIGH_RPE for c in recent) >= 2:
        reasons.append("fatigue_or_high_effort")
    if yesterday and yesterday.data.completion in {"full", "partial"} and yesterday.data.rpe is None:
        reasons.append("missing_effort_rating")
    if reviewed_at is not None and timedelta(0) <= at - reviewed_at < timedelta(days=2):
        reasons.append("return_after_review")
    returning = resumed_at is not None and timedelta(0) <= at - resumed_at < timedelta(days=7)
    if returning:
        reasons.append("return_after_pause")
    history_plans = {p.local_date: p for p in previous
                     if p.cycle_id == cycle.cycle_id and p.local_date < when and p.created_at <= at}
    if base.kind in HARD_FINGER:
        for old_day, prior in history_plans.items():
            if prior.session.kind not in HARD_FINGER or (when - old_day).days > 2:
                continue
            log = recent_by_day.get(old_day)
            if log and log.data.completion == "missed":
                continue
            # Submission time bounds when the session could have ended. If unknown,
            # conservatively assume it could have ended late that local day.
            end = min(log.submitted_at, datetime.combine(old_day, time.max, DENVER)) if log else (
                datetime.combine(old_day, time.max, DENVER)
            )
            if at.astimezone(UTC) - end.astimezone(UTC) < timedelta(hours=48):
                reasons.append("hard_finger_spacing")
                break
    if review:
        readiness = "red"
    elif reasons:
        readiness = "yellow"
    plan = base
    if cycle.status in {"draft", "paused", "completed"}:
        reasons.append("cycle_inactive")
        plan = Session(kind=Kind.REST, minutes=0)
    elif readiness == "red":
        plan = Session(kind=Kind.REST, minutes=0)
    elif readiness == "yellow" and not (day == 1 and reasons == ["missing_previous_checkin"]):
        comparable = next((p.session for d, p in sorted(history_plans.items(), reverse=True)
                           if d.weekday() == when.weekday() and p.session.kind != Kind.REST), None)
        plan = _reduced(plan, sore, comparable if not returning else None)
    if base.kind == Kind.INTERVALS and athlete.clearance != "yes":
        reasons.append("intervals_need_clearance")
        if plan.kind == Kind.INTERVALS:
            plan = Session(kind=Kind.EASY_RUN, minutes=plan.minutes, miles=plan.miles)
    if row.phase in {"deload", "taper"}:
        reasons.append(row.phase)
    used = {c.checkin_id: c for c in [*recent, *unresolved_red]}
    return Prescription(
        prescription_id=f"{cycle.cycle_id}-{when.isoformat()}", cycle_id=cycle.cycle_id, local_date=when,
        created_at=at, week=week, day=day, template_version=PROGRAM.version,
        baseline=base, session=plan, nutrition=target(plan.kind),
        decision=Decision(readiness=readiness, reason_codes=tuple(reasons or ["follow_template"]),
                          previous_missing=missing, review_required=review, manual_override=reducing,
                          confidence="moderate" if readiness == "green" else "low",
                          inputs=tuple((c.checkin_id, c.submitted_at) for c in sorted(
                              used.values(), key=lambda c: (c.local_date, c.revision)))),
        lesson_id=f"w{week:02d}-d{when.weekday()+1}", lesson=row.lesson,
    )
