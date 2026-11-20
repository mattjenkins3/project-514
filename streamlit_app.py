import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, available_timezones

import psycopg
import streamlit as st

from project514.coach import DAYS, GRADES, save_feedback, scheduled, today_plan
from project514.store import transaction

st.set_page_config(page_title="Project 5.14", page_icon="🧗", layout="centered")
ROOT = Path(__file__).parent
ZONES = sorted(available_timezones())
GOALS = ["Climbing only", "Running", "Aerobic fitness / VO₂ max", "Running and VO₂ max"]


def local_day(zone):
    return datetime.now(ZoneInfo(zone)).date()


def authenticate():
    try:
        password = st.secrets.get("APP_PASSWORD", "")
    except FileNotFoundError:
        password = ""
    if not isinstance(password, str) or len(password) < 16 or password == "YOUR-UNIQUE-APP-PASSWORD":
        st.error(
            "Set a private APP_PASSWORD of at least 16 characters in Streamlit Secrets to open this app."
        )
        st.stop()
    fingerprint = hashlib.sha256(password.encode()).digest()
    if hmac.compare_digest(st.session_state.get("login", b""), fingerprint):
        return
    st.image(str(ROOT / "assets/project-514.svg"), width=340)
    st.header("Open your training log")
    with st.form("unlock_form", clear_on_submit=True):
        supplied = st.text_input("App password", type="password")
        enter = st.form_submit_button("Unlock", type="primary")
    if enter:
        if time.monotonic() < st.session_state.get("try_after", 0):
            st.error("Wait a few seconds before trying again.")
        elif hmac.compare_digest(supplied.encode(), password.encode()):
            st.session_state.login = fingerprint
            st.rerun()
        else:
            st.session_state.try_after = time.monotonic() + 3
            st.error("That password didn’t match.")
    st.stop()


def profile_form(profile=None):
    p = profile or {}
    st.header("Your training profile" if p else "Build your training week")
    st.caption("Choose the grade, days and session lengths that fit your life. You can update these later.")
    zone = p.get("zone") or st.context.timezone or "America/Denver"
    with st.form("profile"):
        a, b = st.columns(2)
        grade = a.selectbox(
            "Current repeatable route grade (YDS)", GRADES, GRADES.index(p.get("grade", "5.9"))
        )
        target = b.selectbox("Goal route grade (YDS)", GRADES, GRADES.index(p.get("target", "5.10a")))
        zone = st.selectbox(
            "Training time zone", ZONES, ZONES.index(zone) if zone in ZONES else ZONES.index("UTC")
        )
        now = local_day(zone)
        deadline = st.date_input(
            "Goal review date",
            value=date.fromisoformat(p["deadline"]) if p else now + timedelta(weeks=24),
            min_value=date(2000, 1, 1),
            max_value=now + timedelta(days=36525),
        )
        a, b = st.columns(2)
        height = a.number_input(
            "Height · cm (optional)", min_value=1.0, max_value=300.0, value=p.get("height")
        )
        weight = b.number_input(
            "Weight · kg (optional)", min_value=1.0, max_value=650.0, value=p.get("weight")
        )
        goal = st.selectbox("Additional exercise goal", GOALS, GOALS.index(p.get("aerobic_goal", GOALS[0])))
        climb = st.multiselect(
            "Climbing days", DAYS, default=p.get("climb_days", ["Monday", "Wednesday", "Friday"])
        )
        run = st.multiselect(
            "Run / walk days",
            DAYS,
            default=p.get("run_days", []),
            help="Leave unavailable days out of both lists. A day can have one primary workout.",
        )
        st.caption("Leave both lists empty for a rest-only schedule.")
        a, b = st.columns(2)
        climb_min = a.number_input("Comfortable climbing session · min", 5, 180, p.get("climb_minutes", 30))
        run_min = b.number_input("Comfortable aerobic session · min", 5, 180, p.get("run_minutes", 20))
        cap = st.number_input("Time available per session · min", 5, 240, p.get("session_cap", 45))
        strength = st.checkbox(
            "Include optional strength on recovered aerobic days", value=p.get("strength", False)
        )
        with st.expander("Personal fueling targets (optional)"):
            st.caption(
                "Enter your own reference targets, if you use them. The daily plan also includes meal and hydration cues."
            )
            fuel = {
                level: st.text_input(
                    f"{level} day · kcal and macros",
                    value=p.get("fuel_targets", {}).get(level, ""),
                    max_chars=120,
                    placeholder="Energy, protein, carbohydrate, fat",
                )
                for level in ("Rest", "Moderate", "Hard")
            }
        submitted = st.form_submit_button("Save profile" if p else "Create my schedule", type="primary")
    if submitted:
        if set(climb) & set(run):
            st.error("Choose a single primary workout for each day.")
            return
        if (run and goal == GOALS[0]) or (goal != GOALS[0] and not run):
            st.error(
                "Choose at least one run / walk day for an aerobic goal, or select Climbing only and clear the run days."
            )
            return
        if deadline is None or (not p and deadline < now):
            st.error("Choose a goal review date today or later.")
            return
        if GRADES.index(target) < GRADES.index(grade):
            st.error("Choose a goal grade equal to or higher than your current grade.")
            return
        with transaction(st.secrets, True) as db:
            current = db.get("profile")
            if current != (profile or None):
                st.warning("Your profile changed in another tab. Reload to edit the latest version.")
                return
            db.put(
                "profile",
                "",
                {
                    **p,
                    "grade": grade,
                    "target": target,
                    "deadline": deadline.isoformat(),
                    "starting_grade": p.get("starting_grade", p.get("grade", grade)),
                    "height": height,
                    "weight": weight,
                    "aerobic_goal": goal,
                    "climb_days": [d for d in DAYS if d in climb],
                    "run_days": [d for d in DAYS if d in run],
                    "strength": strength,
                    "zone": zone,
                    "start": p.get("start", now.isoformat()),
                    "climb_minutes": climb_min,
                    "run_minutes": run_min,
                    "session_cap": cap,
                    "fuel_targets": fuel,
                },
            )
        st.session_state.notice = "Schedule saved. New workouts use your latest profile."
        st.rerun()


@st.fragment(run_every="5min")
def imported_minutes(yesterday):
    with transaction(st.secrets) as db:
        health = db.get("health", yesterday.isoformat())
    if health and "workout_minutes" in health:
        st.caption(
            f"Apple Health reported {health['workout_minutes']} workout minutes. Confirm what you actually did below."
        )


def checkin(day, previous_plan, saved):
    yesterday = day - timedelta(days=1)
    st.subheader(f"How did {yesterday:%A, %b %d} go?")
    if previous_plan:
        st.caption(f"Planned · {previous_plan['title']} · {previous_plan['minutes']} min")
    imported_minutes(yesterday)
    options = ["Completed", "Partial", "Missed", "Rested"]
    prior = saved or {}

    def pick(label, items, field, default=None):
        v = prior.get(field, default)
        return st.selectbox(
            label, items, index=items.index(v) if v in items else None, key=f"{yesterday}-{field}"
        )

    result = pick("Outcome", options, "outcome")
    data = {"outcome": result}
    if result in ("Completed", "Partial"):
        activity = pick(
            "Actual activity", ["Climb", "Aerobic", "Other"], "activity", (previous_plan or {}).get("kind")
        )
        data["activity"] = activity
        a, b = st.columns(2)
        data["minutes"] = a.number_input(
            "Actual minutes", 1, 1440, value=prior.get("minutes"), key=f"min-{yesterday}"
        )
        data["effort"] = b.selectbox(
            "Effort · 1–10",
            list(range(1, 11)),
            index=prior["effort"] - 1 if prior.get("effort") else None,
            key=f"rpe-{yesterday}",
        )
        if activity == "Climb":
            data["pump"] = pick("Peak pump · 0–10 (optional)", list(range(11)), "pump")
            data["technique"] = pick(
                "Final-third technique (optional)", ["Steady", "Faded", "Unsafe movement"], "technique"
            )
        elif activity == "Aerobic":
            data["miles"] = st.number_input(
                "Actual miles (optional)", 0.0, 300.0, value=prior.get("miles"), key=f"miles-{yesterday}"
            )
            data["talk"] = pick("Could you speak in full sentences? (optional)", ["Yes", "No"], "talk")
    data["recovery"] = pick(
        "How do you feel this morning?",
        ["Recovered", "A little tired or sore", "Poorly recovered"],
        "recovery",
    )
    data["symptoms"] = pick(
        "Any new or unusual discomfort?",
        ["None", "Mild discomfort", "Significant or worsening", "Chest or breathing symptoms"],
        "symptoms",
    )
    if data["symptoms"] == "Chest or breathing symptoms":
        st.error(
            "Stop exercise and seek urgent medical help. Call emergency services if symptoms are severe or ongoing."
        )
    elif data["symptoms"] == "Significant or worsening" or data.get("technique") == "Unsafe movement":
        st.warning("Stop training and seek appropriate evaluation before returning.")
    a, b = st.columns(2)
    submit = a.button("Save check-in", key=f"save-{yesterday}", type="primary")
    skip = b.button(
        "Skip and use an easy plan",
        key=f"skip-{yesterday}",
        disabled=data["symptoms"] not in (None, "None") or data.get("technique") == "Unsafe movement",
    )
    if submit or skip:
        if not skip and (
            not result
            or not data["recovery"]
            or not data["symptoms"]
            or (result in ("Completed", "Partial") and not data["activity"])
        ):
            st.error("Choose an outcome, recovery, discomfort and, if you trained, the activity.")
            return
        with transaction(st.secrets, True) as db:
            if local_day(db.get("profile")["zone"]) != day:
                st.rerun()
            if db.get("checkin", yesterday.isoformat()) != saved:
                st.warning("This check-in changed in another tab. Reload to see it.")
                return
            save_feedback(db, day, {"outcome": "Skipped"} if skip else data)
        st.session_state.pop("edit_day", None)
        st.rerun()


@st.fragment(run_every="60s")
def watch_date(day, zone):
    if local_day(zone) != day:
        st.rerun()


def today(profile, day):
    with transaction(st.secrets, True) as db:
        plan = today_plan(db, day)
        yesterday = (day - timedelta(days=1)).isoformat()
        previous = db.get("plan", yesterday)
        saved = db.get("checkin", yesterday)
        latest = next(iter(db.recent("benchmark", day.isoformat(), 1)), profile["start"])
        hold = db.get("hold")
    st.caption(f"{day:%A, %B %d, %Y} · {profile['zone']}")
    if day.isoformat() < profile["start"]:
        st.info(f"Your training starts on {profile['start']}.")
        return
    if hold:
        st.error(hold["message"])
    if not plan or st.session_state.get("edit_day") == day.isoformat():
        checkin(day, previous, saved)
        return
    st.caption(f"Week {plan['week']} · Day {plan['day_number']} · {plan['phase']}")
    st.write(f"*{plan['intention']}*")
    st.title(plan["title"])
    st.caption(f"{plan['minutes']} minutes · {plan['readiness']}")
    with st.container(border=True):
        st.subheader("Main work")
        st.write(plan["work"])
        st.write(plan["alternative"])
        st.markdown("**Secondary work**")
        st.write(plan["secondary"])
    for title, body in [
        ("Fueling", plan["fuel"]),
        ("Why today", " ".join(plan["reasons"])),
        ("Technique cue", plan["cue"]),
        ("Carry into your next session", plan["encouragement"]),
    ]:
        st.markdown(f"**{title}**")
        st.write(body)
        if title == "Fueling" and plan.get("fuel_target"):
            st.text(f"Personal reference target · {plan['fuel_target']}")
    if "review" in plan:
        with st.expander("Sunday review · previous seven days", expanded=True):
            st.write(plan["review"])
    if (day - date.fromisoformat(latest)).days >= 28:
        st.info("Your four-week benchmark is due. Open Progress to log a comparable route.")
    if day >= date.fromisoformat(profile["deadline"]):
        st.info(
            "Your goal review date has arrived. Compare your latest grade in Progress and update your goal in Profile."
        )
    st.caption(
        "Stop any movement that hurts. You can switch today to rest or update your schedule in Profile."
    )
    a, b = st.columns(2)
    if plan["kind"] != "Rest" and a.button("Rest today"):
        with transaction(st.secrets, True) as db:
            db.put("rest", day.isoformat(), True)
            db.remove("plan", day.isoformat())
        st.rerun()
    if saved and b.button("Correct yesterday’s check-in"):
        st.session_state.edit_day = day.isoformat()
        st.rerun()
    with st.expander("Coming week"):
        for n in range(1, 8):
            future = day + timedelta(days=n)
            kind = "Rest" if profile.get("paused") or hold else scheduled(profile, future)
            st.write(f"{future:%a, %b %d} · {kind}")
        st.caption("Each morning’s check-in sets the final workload.")


@st.fragment(run_every="5min")
def health_summary(key):
    with transaction(st.secrets) as db:
        health = db.recent("health", key, 28)
    if health:
        st.subheader("Apple Health summaries")
        st.dataframe([{"Date": d, **v} for d, v in health.items()], hide_index=True)


def progress(profile, day):
    key = day.isoformat()
    with transaction(st.secrets) as db:
        benchmarks = db.recent("benchmark", key, 100)
        logs = db.recent("checkin", key, 14)
    last_date = next(iter(benchmarks), profile["start"])
    latest = next(iter(benchmarks.values()), {})
    grade = latest.get("grade", profile["grade"])
    st.header("Progress")
    a, b, c = st.columns(3)
    a.metric("Starting grade", profile.get("starting_grade", profile["grade"]))
    b.metric("Latest grade", grade)
    c.metric("Goal grade", profile["target"])
    due = date.fromisoformat(last_date) + timedelta(days=28)
    st.caption(f"Next benchmark · {due:%b %d, %Y}   |   Goal review · {profile['deadline']}")
    with st.expander("Record a benchmark", expanded=day >= due):
        st.write(
            "Use a familiar route under similar conditions. A higher high point or steadier footwork can show progress between grades."
        )
        with st.form(f"benchmark-{key}"):
            recorded = st.selectbox("Repeatable grade today", GRADES, GRADES.index(grade))
            route = st.text_input("Benchmark route or wall", value=latest.get("route", ""), max_chars=160)
            high = st.text_input("High point or send", value="", max_chars=160)
            attempts = st.number_input("Attempts (optional)", 1, 100, value=None)
            technique = st.selectbox(
                "Final-third technique", ["Steady", "Faded", "Did not reach final third", "Unknown"], index=3
            )
            vo2 = st.number_input("Measured VO₂ max · mL/kg/min (optional)", 1.0, 150.0, value=None)
            submit = st.form_submit_button("Save benchmark", type="primary")
        if submit:
            with transaction(st.secrets, True) as db:
                db.put(
                    "benchmark",
                    key,
                    {
                        "grade": recorded,
                        "route": route,
                        "high_point": high,
                        "attempts": attempts,
                        "technique": technique,
                        "vo2_max": vo2,
                    },
                )
            st.session_state.notice = "Benchmark saved."
            st.rerun()
    if benchmarks:
        st.subheader("Benchmark history")
        st.dataframe([{"Date": d, **v} for d, v in benchmarks.items()], hide_index=True)
    health_summary(key)
    if logs:
        st.subheader("Recent check-ins")
        st.dataframe([{"Date": d, **v} for d, v in logs.items()], hide_index=True)


def preferences(profile, day):
    profile_form(profile)
    st.subheader("Training status")
    with transaction(st.secrets) as db:
        hold = db.get("hold")
        phone = db.get("phone")
    if hold:
        st.warning(hold["message"])
        reviewed = st.checkbox("I have addressed this concern and am ready for an easy return.")
    else:
        reviewed = False
    resume = profile.get("paused", False)
    toggle = st.button("Resume training" if resume else "Pause training")
    clear = bool(hold) and st.button("Record review and clear hold", disabled=not reviewed)
    if toggle or clear:
        with transaction(st.secrets, True) as db:
            p = db.get("profile")
            if clear and db.get("hold") == hold:
                db.remove("hold")
            if toggle:
                p["paused"] = not resume
            if clear or (toggle and resume):
                p["reentry_until"] = (day + timedelta(days=6)).isoformat()
            db.put("profile", "", p)
            db.remove("plan", day.isoformat())
        st.rerun()
    st.subheader("Apple Health")
    st.write(
        "Your iPhone can send dated workout minutes and measured VO₂ max directly to your database. Your daily check-in confirms recovery and effort."
    )
    if st.secrets.get("DATABASE_URL"):
        enabled = st.toggle("Allow iPhone Shortcut imports", value=bool(phone))
        if enabled != bool(phone):
            with transaction(st.secrets, True) as db:
                if enabled:
                    token = secrets.token_urlsafe(32)
                    db.put("phone", "", {"digest": hashlib.sha256(token.encode()).hexdigest()})
                    st.session_state.phone_token = token
                else:
                    db.remove("phone")
                    st.session_state.pop("phone_token", None)
            st.rerun()
        if phone:
            if "phone_token" in st.session_state:
                st.caption("Copy the import token to your private Shortcut. Signing out clears this display.")
                st.code(st.session_state.phone_token)
            st.caption("Turn imports off to revoke the token. Turn them back on for a new token.")
            with st.expander("Set up the iPhone Shortcut"):
                st.markdown((ROOT / "docs/apple-health.md").read_text())
    else:
        st.caption(
            "Automatic imports need the hosted database. You can enter measured VO₂ max in Progress here."
        )
    st.subheader("Your data")
    if st.button("Prepare private JSON export"):
        with transaction(st.secrets) as db:
            data = {}
            for kind in ("profile", "plan", "checkin", "benchmark", "health", "rest", "hold"):
                data[kind] = db.recent(kind, "9999-12-31", 2147483647)
        st.download_button(
            "Download training log",
            json.dumps(data, indent=2),
            "project-514.json",
            "application/json",
            on_click="ignore",
        )


def main():
    authenticate()
    with st.sidebar:
        st.image(str(ROOT / "assets/project-514.svg"), width=210)
        view = st.radio("Training log", ["Today", "Progress", "Profile"])
        if st.button("Lock app"):
            st.session_state.clear()
            st.rerun()
    if "notice" in st.session_state:
        st.success(st.session_state.pop("notice"))
    with transaction(st.secrets) as db:
        profile = db.get("profile")
    if not profile:
        profile_form()
        return
    day = local_day(profile["zone"])
    watch_date(day, profile["zone"])
    if view == "Today":
        today(profile, day)
    elif view == "Progress":
        progress(profile, day)
    else:
        preferences(profile, day)


try:
    main()
except (psycopg.Error, sqlite3.Error, OSError, ValueError):
    st.error(
        "Couldn’t open or update your training log. Check the database connection and setup in Streamlit Secrets, then reload. Your saved log can be reopened when the database is available."
    )
