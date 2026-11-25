import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from streamlit.testing.v1 import AppTest

from project514.store import transaction


class AppFlow(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.config = {
            "APP_PASSWORD": "a fictional test password",
            "LOCAL_SQLITE_PATH": str(Path(temp.name) / "log"),
        }
        self.entrypoint = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")

    def open(self):
        app = AppTest.from_file(self.entrypoint)
        app.secrets.update(self.config)
        app.run()
        self.assertFalse(app.exception)
        self.assertFalse(app.radio)
        app.text_input[0].set_value(self.config["APP_PASSWORD"])
        app.button[0].click().run()
        self.assertFalse(app.exception)
        return app

    def button(self, app, label):
        next(b for b in app.button if b.label == label).click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error, [x.value for x in app.error])

    def test_login_onboard_reopen_checkin_benchmark_and_lock(self):
        app = self.open()
        self.button(app, "Create my schedule")
        self.assertTrue(app.title)
        day = date.fromisoformat(next(iter(self.saved("plan"))))
        with transaction(self.config, True) as db:
            p = db.get("profile")
            p["start"] = (day - timedelta(days=30)).isoformat()
            db.put("profile", "", p)
            db.remove("plan", day.isoformat())
        app = self.open()
        self.assertTrue(any("How did" in h.value for h in app.subheader))
        self.assertFalse(app.title)
        self.button(app, "Skip and use an easy plan")
        self.assertTrue(app.title)
        self.assertTrue(any("benchmark is due" in i.value for i in app.info))
        app.radio[0].set_value("Progress").run()
        self.button(app, "Save benchmark")
        self.assertIn(day.isoformat(), self.saved("benchmark"))
        app.radio[0].set_value("Profile").run()
        self.button(app, "Pause training")
        app.radio[0].set_value("Today").run()
        self.assertEqual(app.title[0].value, "Recovery day")
        self.button(app, "Lock app")
        self.assertFalse(app.radio)

    def test_wrong_password_cannot_open_database(self):
        app = AppTest.from_file(self.entrypoint)
        app.secrets.update(self.config)
        app.run()
        app.text_input[0].set_value("incorrect")
        app.button[0].click().run()
        self.assertFalse(app.radio)
        self.assertFalse(app.title)
        self.assertTrue(app.error)
        self.assertFalse(Path(self.config["LOCAL_SQLITE_PATH"]).exists())

    def saved(self, kind):
        with transaction(self.config) as db:
            return db.recent(kind, "9999-12-31", 10)
