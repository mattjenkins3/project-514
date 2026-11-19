import base64
import io
import json
import unittest
from email import policy
from email.parser import BytesParser
from urllib.error import HTTPError

from pydantic import SecretStr

from project514.gmail import GmailConfig, GmailEmail, GmailError, SEND_URL, TOKEN_URL
from project514.render import Message


def config(recipient="athlete@example.test"):
    return GmailConfig("coach@example.test", recipient, "test-client",
                       SecretStr("synthetic-client-secret"), SecretStr("synthetic-refresh-token"))


class GmailTests(unittest.TestCase):
    def test_mime_and_scope_use_fixed_endpoints_and_approved_addresses(self):
        adapter = GmailEmail(config())
        calls = []

        def fake(request, *, timeout):
            calls.append(request)
            reply = {"access_token": "synthetic-access"} if len(calls) == 1 else {"id": "abc123"}
            return io.BytesIO(json.dumps(reply).encode())

        adapter._open = fake
        self.assertEqual(adapter.deliver("morning-1", Message("Subject", "text", "<p>HTML</p>")), "abc123")
        first, second = calls
        self.assertEqual((first.full_url, second.full_url), (TOKEN_URL, SEND_URL))
        self.assertEqual(second.headers["Authorization"], "Bearer synthetic-access")
        email = BytesParser(policy=policy.default).parsebytes(
            base64.urlsafe_b64decode(json.loads(second.data)["raw"])
        )
        self.assertEqual(email["To"], "athlete@example.test")
        self.assertEqual(email["From"], "coach@example.test")
        self.assertEqual(email["Message-ID"], "<project514-morning-1@example.test>")
        self.assertIn("text", email.get_body(("plain",)).get_content())
        self.assertIn("<p>HTML</p>", email.get_body(("html",)).get_content())

    def test_ambiguous_send_failure_has_safe_reason(self):
        adapter = GmailEmail(config())

        def fake(request, *, timeout):
            if request.full_url == TOKEN_URL:
                return io.BytesIO(b'{"access_token":"synthetic-access"}')
            raise HTTPError(SEND_URL, 503, "raw payload", {}, None)

        adapter._open = fake
        with self.assertRaisesRegex(GmailError, "^gmail_send_uncertain$"):
            adapter.deliver("morning-1", Message("Subject", "text", "<p>HTML</p>"))

    def test_multi_recipient_and_header_injection_rejected(self):
        for value in ("user@example.test,extra@example.test", "user@example.test\nBcc: bad@example.test"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                config(value)


class GmailPreflightTests(unittest.TestCase):
    def test_preflight_never_calls_send_and_checks_reported_scope(self):
        adapter = GmailEmail(config())
        urls = []

        def fake(request, *, timeout):
            urls.append(request.full_url)
            return io.BytesIO(b'{"access_token":"synthetic","scope":"https://www.googleapis.com/auth/gmail.send"}')

        adapter._open = fake
        adapter.preflight()
        self.assertEqual(urls, [TOKEN_URL])
        adapter._open = lambda request, *, timeout: io.BytesIO(b'{"access_token":"synthetic","scope":"openid"}')
        with self.assertRaisesRegex(GmailError, "^gmail_send_scope_missing$"):
            adapter.preflight()

    def test_presence_check_makes_no_network_request_and_reports_missing_names(self):
        from unittest.mock import patch

        from project514.gmail_preflight import check

        values = {
            "GMAIL_CLIENT_ID": "synthetic-client",
            "GMAIL_CLIENT_SECRET": "synthetic-secret",
            "GMAIL_REFRESH_TOKEN": "synthetic-refresh",
            "GMAIL_SENDER": "coach@example.test",
            "GMAIL_RECIPIENT": "athlete@example.test",
        }
        with patch("project514.gmail_preflight.GmailEmail") as provider:
            self.assertIn("No network request", check(values))
            provider.assert_not_called()
            del values["GMAIL_REFRESH_TOKEN"]
            with self.assertRaisesRegex(ValueError, "^Missing settings: GMAIL_REFRESH_TOKEN$"):
                check(values, refresh=True)
            provider.assert_not_called()
