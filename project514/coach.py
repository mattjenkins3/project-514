"""The single-athlete coaching rules shared by the app and its tests."""

from datetime import date, timedelta

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
GRADES = [f"5.{i}" for i in range(10)] + [f"5.{i}{letter}" for i in range(10, 16) for letter in "abcd"]
PHASES = (
    "Reentry",
    "Movement economy",
    "Pacing",
    "Deload",
    "Route practice",
    "Repeatability",
    "Endurance",
    "Deload",
    "Route reading",
    "Project practice",
    "Consistency",
    "Assessment",
)
CUES = (
    "Finish with enough in reserve to repeat the session comfortably.",
    "Relax the non-supporting hand and keep your feet quiet.",
    "Choose a secure rest before the final third of the route.",
    "Use the same wall and holds when you repeat a benchmark.",
    "Keep one foot weighted as you reach.",
    "Maintain foot pressure as your hips move away from the wall.",
    "Try one deliberate shakeout and a long exhale at a secure rest.",
    "Repeat your benchmark under similar conditions and note recovery.",
    "Read the last crux and find the most useful rest before you start.",
    "Choose one movement cue you can use at the last crux.",
    "Keep foot placement precise when a move starts to feel rushed.",
    "Record where movement felt smooth and where it began to fade.",
)


def calendar(profile, day):
    elapsed = (day - date.fromisoformat(profile["start"])).days
    return elapsed // 7 + 1, elapsed // 7 % 12, elapsed % 7 + 1


def scheduled(profile, day):
    name = DAYS[day.weekday()]
    if name in profile["climb_days"]:
        return "Climb"
    if name in profile["run_days"]:
        return "Aerobic"
    return "Rest"


def weekly_review(plans, logs):
    sessions = [p for p in plans.values() if p["kind"] != "Rest"]
    reported = [r for r in logs.values() if r["outcome"] in ("Completed", "Partial")]
    minutes = [r["minutes"] for r in reported if r.get("minutes") is not None]
    miles = [r["miles"] for r in reported if r.get("miles") is not None]
    recovered = sum(r.get("recovery") == "Recovered" for r in logs.values())
    steady = sum(r.get("technique") == "Steady" for r in reported)
    return (
        f"{len(sessions)} saved training sessions ({sum(p['minutes'] for p in sessions)} min planned). "
        f"{len(reported)} sessions reported. "
        f"Reported totals: {str(sum(minutes)) + ' min' if minutes else 'minutes unknown'}, "
        f"{str(round(sum(miles), 1)) + ' mi' if miles else 'mileage unknown'}. "
        f"{recovered} recovered check-ins and {steady} steady final-third reports. "
        "Unlogged days are unknown. Next week, repeat one familiar effort and record how it feels."
    )


def make_plan(profile, day, logs, hold, benchmark, lighter=False, previous_plan=None):
    week, phase, day_number = calendar(profile, day)
    weekday = DAYS[day.weekday()]
    yesterday = (day - timedelta(days=1)).isoformat()
    recent = logs.get(yesterday, {})
    kind = scheduled(profile, day)
    grade = (benchmark or {}).get("grade", profile["grade"])
    target = profile["target"]
    reasons = []
    readiness = "Ready"
    if hold:
        kind, readiness = "Rest", "Hold"
        reasons.append(hold["message"])
    elif profile.get("paused") or lighter:
        kind, readiness = "Rest", "Rest"
        reasons.append("You chose rest today." if lighter else "Training is paused.")
    elif recent.get("symptoms") == "Mild discomfort":
        kind, readiness = "Rest", "Recover"
        reasons.append("Give the reported discomfort time to settle. Stop activity that hurts.")
    else:
        if not recent or recent.get("outcome") == "Skipped":
            reasons.append(
                "Start with easy reentry."
                if day.isoformat() == profile["start"]
                else f"Recovery for {yesterday} is unknown."
            )
        elif (
            recent["outcome"] in ("Partial", "Missed")
            or recent["recovery"] != "Recovered"
            or (recent.get("effort") or 0) >= 9
            or (recent.get("pump") or 0) >= 8
            or recent.get("talk") == "No"
            or recent.get("technique") == "Faded"
        ):
            reasons.append(f"Your {yesterday} feedback calls for an easier day.")
        if profile.get("reentry_until", "") >= day.isoformat():
            reasons.append("Ease back during your return week.")
        if recent.get("outcome") in ("Completed", "Partial") and recent.get("effort") is None:
            reasons.append("Yesterday’s effort is unknown.")
        if (
            previous_plan
            and recent.get("activity") == previous_plan["kind"]
            and (recent.get("minutes") or 0) > previous_plan["minutes"]
        ):
            reasons.append("Yesterday’s session exceeded its planned duration.")
        if reasons:
            readiness = "Easy"
        else:
            reasons.append(f"Your {yesterday} check-in supports the scheduled session.")
    if kind == "Rest":
        return {
            "kind": kind,
            "title": "Recovery day",
            "minutes": 0,
            "readiness": readiness,
            "intention": "Leave space for recovery today.",
            "work": "Full rest. Keep a regular sleep window.",
            "secondary": "No supplemental work.",
            "alternative": "Keep the day free of training.",
            "fuel": "Eat regular meals and drink to thirst on rest days, too.",
            "cue": "Set aside a few minutes to prepare for your next session.",
            "encouragement": "Rest is part of the schedule you chose.",
            "reasons": reasons,
            "week": week,
            "phase": PHASES[phase],
            "day_number": day_number,
            "hard": False,
        }

    recent_sessions = [
        r
        for r in logs.values()
        if r.get("activity") == kind
        and r.get("minutes")
        and r["outcome"] == "Completed"
        and r.get("recovery") == "Recovered"
        and r.get("symptoms") == "None"
        and 0 < (r.get("effort") or 0) < 9
        and (r.get("pump") or 0) < 8
        and r.get("technique") != "Faded"
        and r.get("talk") != "No"
    ]
    comfortable = profile["climb_minutes" if kind == "Climb" else "run_minutes"]
    cap = min(comfortable, profile["session_cap"])
    if recent_sessions:
        last_minutes = recent_sessions[0]["minutes"]
        cap = min(cap, last_minutes + min(5, round(last_minutes * 0.1)))
    elif readiness == "Ready":
        # A recovered rest day alone gives no evidence of a tolerated training dose.
        cap = min(cap, 30 if kind == "Climb" else 20)
    if readiness == "Easy" or phase in (0, 3, 7, 11):
        cap = min(cap, max(1, round(cap * 0.7)))
    minutes = cap
    warm = min(8, minutes // 4)
    cool = min(5, minutes // 4)
    main = minutes - warm - cool
    hard = False
    if kind == "Climb":
        # Two full intervening calendar days also cover evening-to-morning turnarounds.
        spacing = [logs.get((day - timedelta(days=n)).isoformat(), {}) for n in (1, 2)]
        clear = all(
            r.get("outcome") in ("Rested", "Missed")
            or (
                r.get("activity") in ("Climb", "Aerobic")
                and r.get("effort") is not None
                and r["effort"] <= 5
                and r.get("symptoms") == "None"
            )
            for r in spacing
        )
        hard = bool(
            clear
            and recent_sessions
            and phase in (4, 5, 6, 8, 9, 10)
            and readiness == "Ready"
            and weekday == profile["climb_days"][-1]
            and minutes >= 30
        )
        easy_grade = GRADES[max(0, GRADES.index(grade) - 2)]
        if hard:
            title = "Rested route practice"
            drill = (
                f"Explore one sequence on a familiar {grade} route at effort 6–7/10. "
                "Take 5–10 min between tries. Stop while your footwork is still precise."
            )
        else:
            title = "Quiet feet & easy laps"
            drill = (
                f"Try routes around {easy_grade} or easier. Alternate easy laps or low traverses "
                "with rests of equal length. Keep forearm pump at 2–3/10."
            )
        work = (
            f"Warm up gradually for {warm} min. Use up to {main} min for practice and rests. "
            f"{drill} Finish with {cool} min of easy movement. Aim for a controlled final third."
        )
        intention = "Give the last foothold as much attention as the first."
        alternative = "Use a familiar indoor wall or a safely protected outdoor equivalent. Without wall access, take a comfortable walk or rest."
        cue = CUES[phase]
        if (benchmark or {}).get("technique") == "Faded":
            cue = "On a familiar route, identify a secure rest before the point where your benchmark footwork faded."
        review_window = 0 <= (date.fromisoformat(profile["deadline"]) - day).days <= 28
        if review_window:
            encouragement_note = "Your goal review is within four weeks. Revisit a familiar route so your next comparison is meaningful."
            reasons.append(encouragement_note)
        encouragement = (
            f"One repeatable sequence gives you something concrete to revisit on the way to {target}."
        )
        fuel = "Have a familiar carbohydrate snack before climbing. Follow the session with a meal containing protein and carbohydrate, and water."
    else:
        title = (
            "Conversational run / walk"
            if profile["aerobic_goal"] != "Aerobic fitness / VO₂ max"
            else "Aerobic base"
        )
        intention = "Set a pace that lets you finish a sentence comfortably."
        work = (
            f"Walk for {warm} min, then alternate easy jogging and walking for {main} min on a flat path "
            f"or treadmill. Stay at effort 3–4/10 and walk whenever speech becomes difficult. Cool down for {cool} min."
        )
        alternative = "Walk the entire session or shorten the loop."
        cue = "Use the full-sentence talk test again on each incline."
        encouragement = "Finishing with energy to spare makes this a session you can repeat."
        fuel = "Start hydrated. After your session, include carbohydrate and protein in your next meal."
    secondary = "No supplemental work today."
    if kind == "Aerobic" and readiness == "Ready" and profile.get("strength") and minutes >= 25:
        secondary = "Optional within the time cap: replace the last 5 min of jogging with one set each of 6–8 rows and 6–8 wall pushups. Keep 3 reps in reserve."
    return {
        "kind": kind,
        "title": title,
        "minutes": minutes,
        "hard": hard,
        "readiness": readiness,
        "intention": intention,
        "work": work,
        "secondary": secondary,
        "alternative": alternative,
        "cue": cue,
        "encouragement": encouragement,
        "fuel": fuel,
        "reasons": reasons,
        "week": week,
        "phase": PHASES[phase],
        "day_number": day_number,
    }


def save_feedback(db, day, data):
    yesterday = (day - timedelta(days=1)).isoformat()
    db.put("checkin", yesterday, data)
    symptom = data.get("symptoms")
    if (
        symptom in ("Significant or worsening", "Chest or breathing symptoms")
        or data.get("technique") == "Unsafe movement"
    ):
        urgent = symptom == "Chest or breathing symptoms"
        previous = db.get("hold") or {}
        if urgent or not previous.get("urgent"):
            message = (
                "Stop exercise and seek urgent medical help for new or concerning chest or breathing symptoms. "
                "Call emergency services if symptoms are severe or ongoing."
                if urgent
                else "Stop training and seek appropriate evaluation before returning."
            )
            db.put("hold", "", {"message": message, "urgent": urgent, "date": yesterday})
    db.remove("plan", day.isoformat())


def today_plan(db, day):
    profile = db.get("profile")
    key = day.isoformat()
    start = profile["start"]
    if key < start:
        return None
    end = (day - timedelta(days=1)).isoformat()
    logs = db.recent("checkin", end, 7, (day - timedelta(days=7)).isoformat())
    if key > start and end not in logs:
        return None
    plan = db.get("plan", key)
    if plan is None:
        latest = next(iter(db.recent("benchmark", key, 1).values()), None)
        plan = make_plan(
            profile, day, logs, db.get("hold"), latest, bool(db.get("rest", key)), db.get("plan", end)
        )
        plan["fuel_target"] = profile.get("fuel_targets", {}).get(
            "Rest" if plan["kind"] == "Rest" else "Hard" if plan["hard"] else "Moderate", ""
        )
        if day.weekday() == 6:
            plans = db.recent("plan", end, 7, (day - timedelta(days=7)).isoformat())
            plan["review"] = weekly_review(plans, logs)
        db.put("plan", key, plan)
    return plan
