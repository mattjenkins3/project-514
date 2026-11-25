import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from project514.coach import save_feedback, today_plan
from project514.store import transaction


class CoachFlow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = {"LOCAL_SQLITE_PATH": str(Path(self.temp.name) / "log.sqlite3")}
        self.first = date(2026, 1, 5)
        self.profile = {
            "start": self.first.isoformat(),
            "zone": "America/Denver",
            "target": "5.11a",
            "grade": "5.9",
            "deadline": "2027-01-01",
            "climb_days": ["Monday", "Friday"],
            "run_days": ["Wednesday"],
            "climb_minutes": 40,
            "run_minutes": 20,
            "session_cap": 35,
            "aerobic_goal": "Running",
        }
        with transaction(self.settings, True) as db:
            db.put("profile", "", self.profile)

    def plan(self, day):
        with transaction(self.settings, True) as db:
            return today_plan(db, day)

    def feedback(self, day, **fields):
        with transaction(self.settings, True) as db:
            save_feedback(db, day, fields)

    def test_first_day_restart_rollover_and_day_365(self):
        p = self.plan(self.first)
        self.assertEqual(p["kind"], "Climb")
        self.assertEqual(self.plan(self.first), p)
        tomorrow = self.first + timedelta(days=1)
        self.assertIsNone(self.plan(tomorrow))
        self.feedback(tomorrow, outcome="Skipped")
        self.assertEqual(self.plan(tomorrow)["kind"], "Rest")
        later = self.first + timedelta(weeks=52)
        self.assertIsNone(self.plan(later))
        self.feedback(later, outcome="Skipped")
        self.assertEqual(self.plan(later)["week"], 53)
        self.assertFalse(self.plan(later)["hard"])

    def test_concerning_symptoms_persist_through_skips_and_corrections(self):
        day = self.first + timedelta(days=2)
        self.feedback(day, outcome="Rested", symptoms="Chest or breathing symptoms", recovery="Recovered")
        self.assertEqual(self.plan(day)["readiness"], "Hold")
        self.feedback(day, outcome="Skipped")
        self.assertIn("urgent", self.plan(day)["reasons"][0])
        later = day + timedelta(weeks=8)
        self.feedback(later, outcome="Rested", symptoms="None", recovery="Recovered")
        self.assertEqual(self.plan(later)["kind"], "Rest")

    def test_sunday_summary_counts_only_reported_work(self):
        sun = self.first + timedelta(days=6)
        self.plan(self.first)
        self.feedback(
            sun,
            outcome="Completed",
            activity="Aerobic",
            minutes=13,
            miles=1.2,
            effort=4,
            symptoms="None",
            recovery="Recovered",
        )
        review = self.plan(sun)["review"]
        self.assertIn("1 saved training sessions", review)
        self.assertIn("13 min", review)
        self.assertIn("1.2 mi", review)

    def test_transaction_rollback(self):
        with self.assertRaises(RuntimeError), transaction(self.settings, True) as db:
            db.put("profile", "", {"grade": "corrupt"})
            raise RuntimeError()
        with transaction(self.settings) as db:
            self.assertEqual(db.get("profile"), self.profile)

    def test_yellow_and_grade_update(self):
        day = self.first + timedelta(weeks=5)
        self.feedback(
            day,
            outcome="Partial",
            activity="Climb",
            minutes=9,
            recovery="A little tired or sore",
            effort=9,
            symptoms="None",
        )
        with transaction(self.settings, True) as db:
            db.put("benchmark", (day - timedelta(days=4)).isoformat(), {"grade": "5.12a"})
        p = self.plan(day)
        self.assertEqual(p["readiness"], "Easy")
        self.assertIn("5.11c", p["work"])
        self.assertLess(p["minutes"], self.profile["session_cap"])


if __name__ == "__main__":
    unittest.main()
