import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from re import search

from fastapi.testclient import TestClient

from project514.delivery import Coach, MockEmail, morning
from project514.demo import simulate
from project514.models import CheckinData, Kind
from project514.store import Store
from project514.web import LINK_SECONDS, LocalAuth, create_app

from test_engine import ATHLETE, CYCLE, GOOD, START

BASE = "http://127.0.0.1:8000"


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.store = Store(self.path / "coach.sqlite3")
        self.now = morning(ATHLETE, START)
        self.auth = LocalAuth(bytes(32))
        self.coach = Coach(self.store, ATHLETE, CYCLE, self.link)

    def link(self, day, at):
        token = self.auth.issue("checkin", f"{CYCLE.cycle_id}/{day}", at, LINK_SECONDS)
        return f"{BASE}/check-in/{day}?link={token}"

    def client(self):
        app, enter = create_app(self.coach, self.auth, BASE, lambda: self.now)
        return TestClient(app, base_url=BASE), enter

    def form_data(self, response, **kwargs):
        return {
            "csrf": search(r'name="csrf" value="([^"]+)"', response.text)[1],
            "revision": search(r'name="revision" value="([^"]+)"', response.text)[1],
            **GOOD, **kwargs,
        }

    def test_timeout_backoff_max_attempts_and_sanitized_ledger(self):
        mock = MockEmail(fail_first=10)
        self.assertEqual(self.coach.tick(self.now, mock), "retry")
        self.assertEqual(self.coach.tick(self.now + timedelta(seconds=59), mock), "waiting")
        self.assertEqual(self.coach.tick(self.now + timedelta(minutes=1), mock), "retry")
        self.assertEqual(self.coach.tick(self.now + timedelta(minutes=3), mock), "failed")
        self.assertEqual(self.coach.tick(self.now + timedelta(minutes=5), mock), "failed")
        self.assertEqual(mock.calls, 3)
        with self.store.transaction() as db:
            self.assertEqual(len(self.store.plans(db, CYCLE.cycle_id)), 1)
            row = db.execute("SELECT status, attempts, error, due_at FROM outbox").fetchone()
            self.assertEqual(tuple(row)[:3], ("failed", 3, "provider_timeout"))

    def test_dispatch_guard_and_concurrency(self):
        prescription = self.coach.prepare(START, self.now)

        class UnexpectedProvider:
            def deliver(self, key, message):
                raise AssertionError("Provider must never be called")

        with self.assertRaises(ValueError):
            self.coach.dispatch(prescription, self.now, UnexpectedProvider())
        mock = MockEmail()
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: self.coach.tick(self.now, mock), range(16)))
        self.assertTrue(set(results) <= {"test", "sending"})
        self.assertEqual((mock.calls, len(mock.delivered)), (1, 1))
        with Store(self.store.path).transaction() as db:
            self.assertEqual(db.execute("SELECT count(*), sum(attempts) FROM outbox").fetchone()[:], (1, 1))

    def test_pause_resume_and_no_catchup(self):
        self.coach.prepare(START, self.now)
        self.store.control(CYCLE.cycle_id, "pause", self.now)
        mock = MockEmail()
        self.assertEqual(self.coach.tick(self.now, mock), "suppressed")
        tomorrow = START + timedelta(days=1)
        next_at = morning(ATHLETE, tomorrow)
        self.assertEqual(self.coach.tick(next_at, mock), "suppressed")
        self.assertEqual(self.coach.prepare(tomorrow, next_at).session.kind, Kind.REST)
        self.store.control(CYCLE.cycle_id, "resume", next_at)
        d3 = tomorrow + timedelta(days=1)
        plan = self.coach.prepare(d3, morning(ATHLETE, d3))
        self.assertEqual(plan.session.kind, Kind.TECHNIQUE)
        self.assertIn("missing_previous_checkin", plan.decision.reason_codes)
        self.assertIn("return_after_pause", plan.decision.reason_codes)
        self.assertLess(plan.session.minutes, plan.baseline.minutes)

    def test_mobile_save_correct_replay_and_immutable_email(self):
        client, enter = self.client()
        url = f"/check-in/{START}"
        self.assertEqual(client.get(url).status_code, 403)
        dashboard = client.get(enter)
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("Plan history", dashboard.text)
        html = client.get(f"/email/{START}")
        plain = client.get(f"/email/{START}?plain=true")
        self.assertIn("Project 5.14", html.text)
        self.assertIn("Fueling", plain.text)
        get = client.get(url)
        self.assertEqual(get.headers["referrer-policy"], "same-origin")
        self.assertEqual(html.headers["referrer-policy"], "no-referrer")
        self.assertIn('name="viewport"', get.text)
        self.assertIn('id="pump"', get.text)
        first = self.form_data(get, pump="3", duration="35")
        result = client.post(url, data=first)
        self.assertIn("Saved.", result.text)
        self.assertEqual(client.post(url, data=first).status_code, 422)
        second = self.form_data(result, pump="9", duration="38", reduce_next="true")
        self.assertEqual(client.post(url, data=second).status_code, 200)
        self.assertEqual(client.get(f"/email/{START}").text, html.text)
        with self.store.transaction() as db:
            history = self.store.history(db, CYCLE.cycle_id)
            self.assertEqual([c.data.pump for c in history], [3, 9])
        self.now = morning(ATHLETE, START + timedelta(days=1))
        self.assertEqual(client.get(enter).status_code, 200)
        with self.store.transaction() as db:
            plans = self.store.plans(db, CYCLE.cycle_id)
        self.assertEqual(plans[1].decision.inputs[0][0], history[1].checkin_id)
        self.assertEqual(plans[1].decision.readiness, "yellow")

    def test_scoped_links_expiry_and_hostile_form(self):
        client, enter = self.client()
        url = f"/check-in/{START}"
        client.get(enter)
        other = START + timedelta(days=1)
        self.coach.prepare(other, morning(ATHLETE, other))
        client.cookies.clear()
        link = self.link(START, self.now)
        self.assertEqual(client.get(link.replace(str(START), str(other), 1)).status_code, 403)
        get = client.get(link)
        self.assertEqual(get.status_code, 200)
        self.assertEqual(client.get(f"/check-in/{other}").status_code, 403)
        self.assertEqual(client.get(f"/email/{START}").status_code, 403)
        self.assertEqual(client.get(url, headers={"Host": "evil.example"}).status_code, 400)
        data = self.form_data(get, duration="<script>alert(1)</script>")
        response = client.post(url, data=data)
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("alert(1)", response.text)
        self.assertEqual(client.post(url, data=self.form_data(get) | {"csrf": "bad"}).status_code, 403)
        self.assertEqual(client.post(url, data=self.form_data(get),
                                     headers={"Origin": "http://evil.example"}).status_code, 403)
        self.assertEqual(client.post(url, json={}).status_code, 415)
        self.assertEqual(client.post(url, data={"oversized": "x" * 5000}).status_code, 413)
        dup = f"csrf={data['csrf']}&revision=0&revision=1"
        self.assertEqual(client.post(url, content=dup, headers={
            "content-type": "application/x-www-form-urlencoded"}).status_code, 400)
        self.now += timedelta(seconds=LINK_SECONDS)
        self.assertEqual(client.get(link).status_code, 403)

    def test_rate_limit(self):
        client, enter = self.client()
        for _ in range(30):
            self.assertEqual(client.get(enter, follow_redirects=False).status_code, 303)
        self.assertEqual(client.get(enter, follow_redirects=False).status_code, 429)

    def test_simulator_scenarios_and_outputs(self):
        for scenario in ("mixed", "steady"):
            output = self.path / scenario
            result = simulate(START, output, scenario)
            self.assertEqual(result["prescriptions"], 84)
            self.assertEqual(result["morning_utc_times"], ["12:00", "13:00"])
            self.assertEqual(result["real_deliveries"], 0)
            self.assertEqual(len(list(output.glob("email-*.html"))), 9)
            if scenario == "mixed":
                self.assertEqual(result["outbox"], {"test": 82, "suppressed": 2})
                self.assertGreater(result["reason_counts"]["urgent_chest_or_breathing"], 0)
                self.assertEqual(result["mock_attempts"], 83)
            else:
                self.assertEqual(result["outbox"], {"test": 84})
            with self.assertRaises(FileExistsError):
                simulate(START, output, scenario)
