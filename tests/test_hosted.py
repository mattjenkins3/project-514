import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from re import search

from fastapi.testclient import TestClient

from project514.hosted import build
from project514.models import DENVER

ORIGIN = "https://pilot.example.test"


class HostedTests(unittest.TestCase):
    def setUp(self):
        disk = tempfile.TemporaryDirectory()
        self.addCleanup(disk.cleanup)
        self.today = datetime.now(DENVER).date()
        self.settings = {
            "RENDER_EXTERNAL_URL": ORIGIN,
            "PROJECT514_PILOT_START": str(self.today),
            "PROJECT514_DATA_DIR": disk.name,
            "PROJECT514_PILOT_PASSWORD": "synthetic-pilot-password-" * 2,
            "PROJECT514_SESSION_KEY": "synthetic-session-signing-key-" * 2,
        }
        self.url = f"/check-in/{self.today}"

    def test_https_health_login_and_restart_preserve_checkin(self):
        with TestClient(build(self.settings), base_url=ORIGIN) as client:
            self.assertEqual(client.get("/healthz").text, "ok")
            self.assertEqual(client.get("/enter").status_code, 404)
            self.assertEqual(client.get("/").url.path, "/login")
            response = client.post("/login", data={"password": self.settings["PROJECT514_PILOT_PASSWORD"]},
                                   headers={"Origin": ORIGIN}, follow_redirects=False)
            self.assertEqual(response.status_code, 303)
            self.assertIn("Secure", response.headers["set-cookie"])
            self.assertIn("HttpOnly", response.headers["set-cookie"])
            self.assertIn("max-age=", response.headers["strict-transport-security"])
            self.assertEqual(client.get("/").status_code, 200)
            form = client.get(self.url).text
            csrf = search(r'name="csrf" value="([^"]+)"', form)[1]
            data = {"csrf": csrf, "revision": "0", "completion": "full",
                    "energy": "okay", "discomfort": "none"}
            result = client.post(self.url, data=data, headers={"Origin": ORIGIN})
            self.assertIn("Saved.", result.text)
            cookie = dict(client.cookies)
        self.assertTrue((Path(self.settings["PROJECT514_DATA_DIR"]) / "project514.sqlite3").is_file())
        with TestClient(build(self.settings), base_url=ORIGIN, cookies=cookie) as restarted:
            self.assertIn('name="revision" value="1"', restarted.get(self.url).text)
            self.assertIn(f"{ORIGIN}{self.url}", restarted.get(f"/email/{self.today}?plain=true").text)

    def test_anonymous_and_cross_origin_access_is_blocked(self):
        with TestClient(build(self.settings), base_url=ORIGIN) as client:
            response = client.get(self.url, follow_redirects=False)
            self.assertEqual(response.headers["location"], f"/login?next={self.url}")
            self.assertEqual(client.get(f"/email/{self.today}").status_code, 403)
            self.assertEqual(client.get("/healthz", headers={"Host": "wrong.example.test"}).status_code, 400)
            credentials = {"password": self.settings["PROJECT514_PILOT_PASSWORD"], "next": "//other.example.test"}
            self.assertEqual(client.post("/login", data=credentials).status_code, 403)
            response = client.post("/login", data=credentials, headers={"Origin": ORIGIN},
                                   follow_redirects=False)
            self.assertEqual(response.headers["location"], "/")

    def test_hosted_start_requires_https_and_persistent_directory(self):
        for override in ({"RENDER_EXTERNAL_URL": "http://pilot.example.test"},
                         {"PROJECT514_DATA_DIR": "/nonexistent/project514-pilot-test"},
                         {"PROJECT514_PILOT_PASSWORD": "weak"}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                build(self.settings | override)
