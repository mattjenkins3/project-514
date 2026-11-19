"""Repeatable synthetic fixture generation and local command-line entry points."""
import argparse
import json
import os
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from .delivery import Coach, MockEmail, morning
from .models import CLIMBING, DENVER, Athlete, CheckinData, Cycle, Kind, Prescription
from .store import Store


def synthetic_checkin(offset: int, plan: Prescription, baseline_only: bool) -> CheckinData | None:
    if not baseline_only and offset in {17, 18, 19}:
        return None
    if not baseline_only and offset == 9:
        return CheckinData(completion="missed", energy="okay", discomfort="none")
    if not baseline_only and offset == 30:
        return CheckinData(completion="missed", energy="poor", discomfort="significant_or_worsening", area="finger")
    if not baseline_only and offset == 57:
        return CheckinData(completion="missed", energy="poor", discomfort="none", symptom="chest_or_breathing")
    session = plan.session
    train = session.kind != Kind.REST
    return CheckinData(
        completion="full" if train else "rest_done", energy="poor" if not baseline_only and offset == 46 else "good",
        discomfort="none", duration=session.minutes if train else None, miles=session.miles or None,
        rpe=6 if train else None, pump=(9 if not baseline_only and offset == 12 else 4)
        if session.kind in CLIMBING else None,
        late_technique="steady" if session.kind in CLIMBING else None,
        strength_done=True if session.strength_sets else None,
    )


def simulate(start: date, output: Path, scenario: str = "mixed") -> dict:
    if scenario not in {"mixed", "steady"}:
        raise ValueError("Unknown synthetic scenario.")
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    database = output / "simulation.sqlite3"
    if database.exists():
        raise FileExistsError(f"Choose a fresh output directory; {database} already exists.")
    athlete = Athlete(clearance="yes" if scenario == "steady" else "unknown")
    cycle = Cycle(cycle_id=f"simulation-{scenario}", athlete_id=athlete.athlete_id, start=start)
    store = Store(database)
    coach = Coach(store, athlete, cycle, lambda d, _: f"http://127.0.0.1:8000/check-in/{d}")
    mock = MockEmail(fail_first=1 if scenario == "mixed" else 0)
    plans, elapsed_offsets = [], set()
    for i in range(84):
        day = start + timedelta(days=i)
        at = morning(athlete, day)
        elapsed_offsets.add(at.isoformat()[11:16])
        if scenario == "mixed" and i in {33, 60}:
            store.control(cycle.cycle_id, "review", at - timedelta(minutes=15))
        if scenario == "mixed" and i in {65, 67}:
            store.control(cycle.cycle_id, "pause" if i == 65 else "resume", at - timedelta(minutes=15))
        status = coach.tick(at, mock)
        if status == "retry":
            status = coach.tick(at + timedelta(minutes=1), mock)
        if status not in {"test", "suppressed"} or coach.tick(at + timedelta(minutes=4), mock) != status:
            raise RuntimeError(f"Unexpected mock delivery outcome for {day}: {status}")
        plan = coach.prepare(day, at)
        plans.append(plan)
        entry = synthetic_checkin(i, plan, scenario == "steady")
        if entry is not None:
            # Daytime log supports conservative 48h checks across the weekend.
            store.submit(plan, entry, at + timedelta(hours=9), expected_revision=0)
    with store.transaction() as db:
        statuses = Counter(row["status"] for row in db.execute("SELECT status FROM outbox"))
        samples = db.execute(
            """SELECT p.day,o.subject,o.html,o.plain FROM outbox o JOIN prescriptions p ON p.id=o.key
               WHERE p.day BETWEEN ? AND ? OR p.day IN (?,?) ORDER BY p.day""",
            (*[str(start + timedelta(days=n)) for n in (0, 6, 22, 31)],),
        ).fetchall()
    report = {
        "scenario": scenario, "start": str(start), "end": str(cycle.end), "prescriptions": len(plans),
        "outbox": dict(statuses), "mock_attempts": mock.calls,
        "readiness": dict(Counter(p.decision.readiness for p in plans)),
        "reason_counts": dict(Counter(reason for p in plans for reason in p.decision.reason_codes)),
        "morning_utc_times": sorted(elapsed_offsets), "real_deliveries": 0,
    }
    (output / "plans.json").write_text(json.dumps([p.model_dump(mode="json") for p in plans], indent=2) + "\n")
    for row in samples:
        (output / f"email-{row['day']}.html").write_text(row["html"])
        (output / f"email-{row['day']}.txt").write_text(row["plain"])
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    sim = commands.add_parser("simulate", help="Run 84 days of synthetic check-ins and mock email.")
    sim.add_argument("--start", type=date.fromisoformat, default=date(2026, 2, 16))
    sim.add_argument("--output", type=Path, required=True)
    sim.add_argument("--scenario", choices=["mixed", "steady"], default="mixed")
    web = commands.add_parser("serve", help="Start the local browser demo.")
    web.add_argument("--port", type=int, default=8000)
    web.add_argument("--start", type=date.fromisoformat)
    web.add_argument("--db", type=Path, default=Path(os.getenv("PROJECT514_DB", ".local/demo.sqlite3")))
    control = commands.add_parser("control", help="Audit a pause, resume or safety review for future demo days.")
    control.add_argument("action", choices=["pause", "resume", "review"])
    control.add_argument("--db", type=Path, default=Path(os.getenv("PROJECT514_DB", ".local/demo.sqlite3")))
    control.add_argument("--start", type=date.fromisoformat)
    args = parser.parse_args()
    if args.command == "simulate":
        print(json.dumps(simulate(args.start, args.output, args.scenario), indent=2))
        return
    if args.start is None and args.db.is_file():
        with Store(args.db).transaction() as db:
            row = db.execute("SELECT body FROM cycles").fetchone()
            if row:
                args.start = Cycle.model_validate_json(row["body"]).start
    start = args.start or datetime.now(DENVER).date()
    athlete = Athlete()
    cycle = Cycle(cycle_id=f"demo-{start}", athlete_id=athlete.athlete_id, start=start)
    store = Store(args.db)
    if args.command == "control":
        store.control(cycle.cycle_id, args.action, datetime.now(UTC))
        print(f"Recorded {args.action} for future prescriptions.")
        return
    import uvicorn
    from .web import LINK_SECONDS, LocalAuth, create_app
    auth = LocalAuth()
    url = f"http://127.0.0.1:{args.port}"

    def link(day: date, at: datetime) -> str:
        token = auth.issue("checkin", f"{cycle.cycle_id}/{day}", at, LINK_SECONDS)
        return f"{url}/check-in/{day}?link={token}"

    app, entry = create_app(Coach(store, athlete, cycle, link), auth, url)
    print(f"Open the local dashboard: {entry}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False, proxy_headers=False)


if __name__ == "__main__":
    main()
