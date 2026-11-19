"""Deterministic, escaped message rendering. Narration cannot edit decisions."""
from dataclasses import dataclass
from datetime import date, timedelta
from html import escape
from statistics import mean
from typing import Protocol

from .models import CLIMBING, HARD_FINGER, Checkin, Kind, Prescription, Session
from .store import latest_checkins

REASONS = {
    "missing_previous_checkin": "No previous-day check-in was available.",
    "incomplete_recent_history": "Recent check-in history is incomplete.",
    "incomplete_no_catchup": "Missed or partial work stays in the past.",
    "athlete_requested_reduction": "You requested a lighter day.",
    "recent_discomfort_or_extra_finger_load": "Recent discomfort or extra finger load calls for caution.",
    "fatigue_or_high_effort": "Recent recovery, fueling or effort signals call for a lighter day.",
    "missing_effort_rating": "There is no effort rating for the latest logged workout.",
    "return_after_pause": "Resume with an easy reentry week and leave missed workouts in the past.",
    "return_after_review": "Keep the return after review easy.",
    "hard_finger_spacing": "Allow at least 48 hours between hard finger sessions.",
    "intervals_need_clearance": "Controlled running intervals require recorded high-intensity clearance.",
    "red_flag_requires_review": "Stop training and review the reported concern. Seek qualified advice if needed.",
    "urgent_chest_or_breathing": "Stop exercise. Seek urgent medical help for new or concerning chest or breathing symptoms; call emergency services if severe or ongoing.",
    "persistent_discomfort": "Repeated discomfort calls for rest and review with a qualified professional.",
    "cycle_inactive": "The cycle is inactive; resume without making up missed work.",
    "deload": "The template reduces load this week.",
    "taper": "Protect freshness for a rested assessment.",
    "follow_template": "Recent check-ins support following the scheduled template.",
}

CUES = (
    "Judge this session by the quality of the last move.",
    "A repeatable effort is useful practice for the long route ahead.",
    "Give one movement cue your full attention.",
    "Leave enough in reserve to learn again next session.",
    "Let recovery support your next good attempt.",
    "Practice the movement you want to have available near the anchors.",
    "A steady week gives you a clearer picture of your capacity.",
)


def workout(s: Session, week: int) -> str:
    if s.kind == Kind.REST:
        return "Full rest. Optional gentle mobility if comfortable. Prioritize a regular sleep window."
    if s.kind in {Kind.EASY_RUN, Kind.INTERVALS}:
        surface = "Choose a flat path or treadmill." if s.kind == Kind.INTERVALS else (
            "Use a path, mellow trail or treadmill."
        )
        reps = f"4 × {s.effort_minutes} min at RPE 7/10, with {max(2, s.effort_minutes)} min easy between." if s.effort_minutes else (
            "Maintain a conversational RPE 3–4/10. Walk as needed."
        )
        return (f"Up to {s.miles:g} mi or {s.minutes} min, whichever comes first. {surface} Start with "
                f"5–10 min easy, then {reps} End with 5 min easy within the cap. "
                "Finish in control; cut repetitions if the budget is short.")
    if s.kind == Kind.TECHNIQUE:
        main = (f"2 × up to {s.continuous_minutes} min of easy low traverses or safe laps, 5 min rest; "
                "keep pump at 2–3/10. Practice quiet feet and relaxed grip.")
    elif s.kind == Kind.BOULDER:
        main = (f"Across 2–4 problems, use up to {s.attempts} controlled attempts at RPE 7–8/10, "
                "resting 3–5 min. Use familiar holds and safe landings. Stop before repeated failures.")
    elif s.kind == Kind.PAIRS:
        main = (f"Up to {s.attempts} route pairs at RPE 7–8/10, 2–3 min between climbs and "
                "8–12 min between pairs. Choose grades that preserve clean final-third movement. "
                "Without safe route access, substitute a low traverse and technique session.")
    elif s.kind in {Kind.PROJECT, Kind.ASSESS}:
        main = (f"Up to {s.attempts} high-quality attempts on a suitable hard route, "
                "10–20 min between attempts. Record the high point and quality near the top; a send isn't required.")
    else:
        main = (f"Up to {s.attempts} controlled routes at RPE {'6–7' if week == 1 else '7–8'}/10, "
                "10–15 min between attempts. Keep movement clean in the final third.")
    setup = "Use an indoor wall or a familiar outdoor equivalent with appropriate safety systems."
    if s.kind != Kind.BOULDER:
        setup += " Use a qualified partner and safe lowering; stop before pump compromises safety."
    warmup = 10 if s.minutes < 45 else 15
    return (f"Up to {s.minutes} min. {setup} Warm up gradually for {warmup} min. {main} "
            "Allow 5–10 min to cool down, and shorten drills if needed to stay within the cap.")


def strength(sets: int) -> str:
    return (f"Up to 20–25 min: {sets} sets each of assisted pull-ups or rows (4–6), floor knee raises "
            "(6–10), hollow holds (20–30 sec), controlled scapular work (8–10) and pushups (8–12). "
            "Rest 60–90 sec; keep 2–3 reps in reserve. Skip any painful movement.")


def weekly(when: date, plans: list[Prescription], history: list[Checkin]) -> str:
    start = when - timedelta(days=6)
    window = [p for p in plans if start <= p.local_date <= when]
    by_day = latest_checkins([c for c in history if start <= c.local_date <= when])
    logged = [c.data for c in by_day.values()]
    trained = {"full", "partial"}
    climbing = [p for p in window if p.session.kind in CLIMBING]
    actual_climbing = [by_day[p.local_date].data for p in climbing if p.local_date in by_day
                       and by_day[p.local_date].data.completion in trained]
    climbing_minutes = [d.duration for d in actual_climbing if d.duration is not None]
    miles = [d.miles for d in logged if d.miles is not None]
    effort = [d.rpe for d in logged if d.rpe is not None]
    pump = [d.pump for d in logged if d.pump is not None]
    hangs = [d.low_load_hang_minutes for d in logged if d.low_load_hang_minutes is not None]
    strengths = [d.strength_done for d in logged if d.strength_done is not None]
    technique = [d.late_technique for d in logged if d.late_technique]
    flags = sum(d.discomfort != "none" or d.symptom != "none" or d.energy == "poor" for d in logged)

    def rating(values: list[int]) -> str:
        return f"mean {mean(values):.1f}, high {max(values)}, n={len(values)}" if values else "missing"

    return (
        f"Check-ins {len(logged)}/{len(window)} prepared days; unlogged days are unknown. "
        f"Climbing: {len(actual_climbing)} logged full/partial vs {len(climbing)} planned; "
        f"{sum(climbing_minutes)/60:.1f} h across {len(climbing_minutes)} timed entries "
        f"vs {sum(p.session.minutes for p in climbing)/60:.1f} h planned. "
        f"Running: {sum(miles):g} mi logged ({len(miles)} entries) vs {sum(p.session.miles for p in window):g} mi planned. "
        f"Strength: {sum(strengths)} logged ({len(strengths)} explicit entries) vs "
        f"{sum(bool(p.session.strength_sets) for p in window)} planned. "
        f"Supplemental hangs: {sum(hangs)} min across {len(hangs)} explicit entries; none prescribed. "
        f"Late-route technique: {technique.count('steady')} steady and {technique.count('faded')} faded"
        f"{' (missing)' if not technique else ''}. RPE {rating(effort)}; pump {rating(pump)}. "
        f"Recovery flags in {flags} logged entries. Benchmark comparison needs matched wall/route conditions. "
        "Nutrition remains provisional. Hold discretionary progression: next week uses template ceilings "
        "adjusted by new check-ins. Priorities: keep easy sessions easy and log final-third technique."
    )


class Narrator(Protocol):
    def cue(self, lesson_id: str) -> object: ...


class MockNarrator:
    def cue(self, lesson_id: str) -> object:
        return None


@dataclass(frozen=True)
class Message:
    subject: str
    plain: str
    html: str


def message(plan: Prescription, link: str, review: str = "", narrator: Narrator | None = None) -> Message:
    session, nutrition = plan.session, plan.nutrition
    cue_index = (plan.day - 1 + plan.week - 1) % len(CUES)
    if narrator is not None:
        try:
            choice = narrator.cue(plan.lesson_id)
            if type(choice) is dict and choice.keys() == {"cue_index"}:
                index = choice["cue_index"]
                if type(index) is int and 0 <= index < len(CUES):
                    cue_index = index
        except Exception:
            pass  # Optional narrator failure never changes training or delivery.
    subject = f"Project 5.14 | W{plan.week:02d} D{(plan.day-1)%7+1:02d} | {session.kind}"
    fuel = ("Have carbohydrate before training, carbohydrate and protein afterward, and bring water."
            if session.kind in HARD_FINGER or session.kind == Kind.INTERVALS else
            "Eat regular meals with protein and carbohydrate and drink to thirst.")
    sections = [
        ("Session", workout(session, plan.week)),
        ("Fueling", f"Provisional: {nutrition.kcal:,} kcal; {nutrition.protein_g} g protein, "
         f"{nutrition.carbs_g} g carbs, {nutrition.fat_g} g fat. {fuel}"),
        ("Why today", " ".join(REASONS[r] for r in plan.decision.reason_codes)),
        ("Technique cue", plan.lesson),
        ("Perspective", CUES[cue_index]),
    ]
    if session.strength_sets:
        sections.insert(1, ("Supplemental strength", strength(session.strength_sets)))
    if review:
        sections.append(("Sunday review", review))
    sections.append(("Adjustments and privacy", "Stop any painful loading. In the form, select a lighter next day "
                     "if needed. This local demo is for synthetic or test entries only."))
    plain = subject + "\n\n" + "\n\n".join(f"{label}\n{body}" for label, body in sections)
    plain += f"\n\nOpen your check-in: {link}\n"
    # The renderer is also callable outside the app. Never place an arbitrary URI
    # scheme in an HTML link, even though normal callers issue loopback HTTP URLs.
    from urllib.parse import urlsplit
    url = urlsplit(link)
    if url.scheme not in {"http", "https"} or not url.hostname:
        raise ValueError("Check-in link must be HTTP(S).")
    body = "".join(f"<h2>{escape(label)}</h2><p>{escape(detail)}</p>" for label, detail in sections)
    html = ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{escape(subject)}</title><body style="margin:0;background:#edf2f1;color:#172d2e">'
            '<main style="max-width:620px;margin:auto;padding:24px;background:#fff;'
            f'font:16px/1.55 system-ui,sans-serif"><h1>{escape(subject)}</h1>{body}'
            f'<p><a href="{escape(link, quote=True)}">Open your check-in</a></p></main></body></html>')
    return Message(subject, plain, html)
