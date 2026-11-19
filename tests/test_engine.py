import unittest
from datetime import UTC, date, datetime, timedelta

from pydantic import ValidationError

from project514.delivery import LocalMorning, morning
from project514.engine import PROGRAM, baseline, prescribe
from project514.models import DENVER, HARD_FINGER, Athlete, Checkin, CheckinData, Cycle, Kind
from project514.nutrition import calibration_review, resting_kcal, target
from project514.render import message, weekly

START = date(2026, 2, 16)
ATHLETE = Athlete()
CYCLE = Cycle(cycle_id="test", athlete_id=ATHLETE.athlete_id, start=START)
LINK = "http://127.0.0.1/check-in"
GOOD = {"completion": "full", "energy": "good", "discomfort": "none", "rpe": 6}


def item(day, data=None, revision=1, at=None):
    return Checkin(checkin_id=f"{day}-r{revision}", prescription_id=f"test-{day}", revision=revision,
                   local_date=day, submitted_at=at or morning(ATHLETE, day) + timedelta(hours=7),
                   data=CheckinData.model_validate(GOOD | (data or {})))


def plan(day, history=(), prior=(), athlete=ATHLETE, review=None, at=None, cycle=CYCLE):
    return prescribe(athlete, cycle, day, at or morning(athlete, day), history, prior, review)


def week_history(day):
    return [item(day - timedelta(days=i)) for i in range(1, 8)]


class ProgramTests(unittest.TestCase):
    def test_all_weeks_and_offset_start(self):
        for offset in range(7):
            cycle = CYCLE.model_copy(update={"start": START + timedelta(days=offset)})
            for i in range(84):
                day = cycle.start + timedelta(days=i)
                p = plan(day, cycle=cycle)
                self.assertEqual((p.day, p.week), (i+1, 1+i//7))
                self.assertEqual(p.template_version, PROGRAM.version)
                if day.weekday() == 4:
                    self.assertEqual(p.session.kind, Kind.REST)
            self.assertEqual(cycle.end, cycle.start + timedelta(days=83))
        with self.assertRaises(ValueError):
            CYCLE.day(START + timedelta(days=84))

    def test_periodization(self):
        expected_runs = [6, 7, 8, 6, 9, 10, 10, 7, 10, 10, 10, 8]
        expected_climb = [150, 180, 215, 150, 240, 240, 270, 180, 270, 270, 270, 180]
        for week in range(1, 13):
            self.assertEqual(sum(baseline(week, d).miles for d in range(7)), expected_runs[week-1])
            self.assertEqual(sum(baseline(week, d).minutes for d in (0, 2, 5)), expected_climb[week-1])
        self.assertEqual([baseline(w, 5).kind for w in (9, 10, 11)], [Kind.PAIRS, Kind.PROJECT, Kind.PAIRS])
        self.assertEqual(baseline(12, 5).kind, Kind.ASSESS)
        self.assertEqual(baseline(1, 0).kind, Kind.TECHNIQUE)
        self.assertTrue(all(baseline(w, 3).kind == Kind.EASY_RUN for w in (1, 2, 3, 4, 5, 8, 12)))

    def test_dst_spring_and_fall(self):
        cycle = CYCLE.model_copy(update={"start": date(2026, 10, 19)})
        for d, hour, c in [(date(2026, 3, 7), 13, CYCLE), (date(2026, 3, 8), 12, CYCLE),
                           (date(2026, 10, 31), 12, cycle), (date(2026, 11, 1), 13, cycle)]:
            at = morning(ATHLETE, d)
            self.assertEqual(at.hour, hour)
            self.assertEqual(at.astimezone(DENVER).hour, 6)
            self.assertIsNone(LocalMorning().due(ATHLETE, c, at - timedelta(seconds=1)))
            self.assertEqual(LocalMorning().due(ATHLETE, c, at), d)
            self.assertIsNone(LocalMorning().due(ATHLETE, c, at + timedelta(minutes=30)))


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.today = START + timedelta(days=40)
        self.yesterday = self.today - timedelta(days=1)

    def test_red_survives_correction_and_requires_review(self):
        red = item(self.yesterday, {"discomfort": "significant_or_worsening", "area": "finger"})
        correction = item(self.yesterday, revision=2)
        p = plan(self.today, [red, correction])
        self.assertEqual((p.decision.readiness, p.session.kind), ("red", Kind.REST))
        self.assertIn(red.checkin_id, dict(p.decision.inputs))
        reviewed = plan(self.today, [red, correction], review=morning(ATHLETE, self.today)-timedelta(hours=1))
        self.assertEqual(reviewed.decision.readiness, "yellow")
        self.assertIn("return_after_review", reviewed.decision.reason_codes)

    def test_respiratory_flag_has_no_training_and_urgent_guidance(self):
        p = plan(self.today, [item(self.yesterday, {"symptom": "chest_or_breathing"})])
        self.assertEqual(p.session.minutes, 0)
        self.assertIn("Seek urgent medical help", message(p, LINK).plain)

    def test_persistent_discomfort_and_underfueling(self):
        p = plan(self.today, [item(self.yesterday, {"discomfort": "mild"}),
                              item(self.yesterday - timedelta(days=4), {"discomfort": "mild"})])
        self.assertIn("persistent_discomfort", p.decision.reason_codes)
        self.assertEqual(p.session.kind, Kind.REST)
        p = plan(self.today, [item(self.yesterday, {"nutrition": "under_fueled", "pump": 9})])
        self.assertEqual(p.decision.readiness, "yellow")
        self.assertLessEqual(p.session.minutes, p.baseline.minutes * .8)

    def test_future_data_and_missing_history_never_prove_recovery(self):
        now = morning(ATHLETE, self.today)
        future = item(self.yesterday, at=now+timedelta(seconds=1), data={"symptom": "chest_or_breathing"})
        p = plan(self.today, [future])
        self.assertEqual(p.decision.readiness, "yellow")
        self.assertTrue(p.decision.previous_missing)
        self.assertEqual(p.decision.inputs, ())
        self.assertNotIn(p.session.kind, HARD_FINGER)

    def test_reduction_missed_and_extra_loading(self):
        p = plan(self.today, [item(self.yesterday, {"completion": "missed", "rpe": None, "reduce_next": True})])
        self.assertTrue(p.decision.manual_override)
        self.assertIn("incomplete_no_catchup", p.decision.reason_codes)
        self.assertEqual(p.session.kind, Kind.TECHNIQUE)
        p = plan(self.today, [item(self.yesterday, {"low_load_hang_minutes": 10})])
        self.assertEqual(p.session.kind, Kind.REST)

    def test_intervals_need_clearance_and_green(self):
        day = START + timedelta(days=38)
        history = week_history(day)
        self.assertEqual(plan(day, history).session.kind, Kind.EASY_RUN)
        cleared = Athlete(clearance="yes")
        p = plan(day, history, athlete=cleared)
        self.assertEqual((p.session.kind, p.session.effort_minutes), (Kind.INTERVALS, 1))
        p = plan(day, [item(day-timedelta(days=1), {"energy": "poor"})], athlete=cleared)
        self.assertEqual(p.session.kind, Kind.EASY_RUN)

    def test_finger_spacing_blocks_second_high_load(self):
        monday = START + timedelta(days=42)
        saturday = monday - timedelta(days=2)
        saturday_plan = plan(saturday, week_history(saturday))
        self.assertIn(saturday_plan.session.kind, HARD_FINGER)
        p = plan(monday, week_history(monday), [saturday_plan])
        self.assertIn("hard_finger_spacing", p.decision.reason_codes)
        self.assertNotIn(p.session.kind, HARD_FINGER)
        later = morning(ATHLETE, monday) + timedelta(hours=8)
        self.assertIn(plan(monday, week_history(monday), [saturday_plan], at=later).session.kind, HARD_FINGER)

    def test_form_model_rejects_nonfinite_and_invalid_metrics(self):
        for override in ({"miles": "nan"}, {"pain": "invalid"}, {"rpe": 11}, {"pump": -1},
                         {"area": "finger"}, {"completion": "missed"}):
            with self.subTest(override=override), self.assertRaises(ValidationError):
                CheckinData.model_validate(GOOD | override)


class NutritionAndRenderTests(unittest.TestCase):
    def test_math_and_optional_calibration(self):
        self.assertAlmostEqual(resting_kcal(80, 180, 30, "male"), 1780)
        self.assertEqual([target(k).kcal for k in (Kind.REST, Kind.EASY_RUN, Kind.PAIRS)], [2505, 2705, 2985])
        d = date(2026, 4, 19)
        samples = [(d-timedelta(days=i), 84.5 if i <= 6 else 85) for i in range(14)]
        self.assertEqual(calibration_review(samples[:4], d)[0], 0)
        self.assertEqual(calibration_review(samples, d)[0], 120)
        self.assertEqual(calibration_review([(d-timedelta(days=i), 86 if i <= 6 else 85)
                                             for i in range(14)], d)[0], 0)
        with self.assertRaises(ValueError):
            calibration_review(samples + samples[:1], d)

    def test_narrator_fallback_and_no_arbitrary_html(self):
        class Timeout:
            def cue(self, lesson_id):
                raise TimeoutError

        class Invalid:
            def cue(self, lesson_id):
                return {"cue_index": 1000, "minutes": 400}

        p = plan(START)
        default = message(p, LINK)
        self.assertEqual(default, message(p, LINK, narrator=Timeout()))
        self.assertEqual(default, message(p, LINK, narrator=Invalid()))
        self.assertIn("Provisional", default.html)
        self.assertIn("check-in", default.plain)
        self.assertIn("&amp;", message(p, LINK + "?q=a&b=c").html)
        with self.assertRaises(ValueError):
            message(p, "javascript:alert(1)")

    def test_weekly_uses_corrected_data_and_marks_missing(self):
        p = plan(START)
        report = weekly(START, [p], [item(START, {"duration": 30, "pump": 4}),
                                     item(START, {"duration": 42, "pump": 5}, revision=2)])
        self.assertIn("0.7 h across 1 timed entries", report)
        self.assertIn("mean 5.0, high 5", report)
        self.assertIn("RPE missing", weekly(START, [p], []))
