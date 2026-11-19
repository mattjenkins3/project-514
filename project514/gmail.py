"""Gmail API transport for a future approved worker. Importing this module is inert."""
import base64
import json
from dataclasses import dataclass
from email.message import EmailMessage
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import SecretStr

from .render import Message

TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


class GmailError(Exception):
    """Contains only a safe failure category. Never stores a provider response."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class GmailConfig:
    sender: str
    recipient: str
    client_id: str
    client_secret: SecretStr
    refresh_token: SecretStr

    def __post_init__(self):
        for address in (self.sender, self.recipient):
            # A single approved address per header. No address lists or display names.
            if not address.isascii() or any(c.isspace() or c in ',;<>:"\\' for c in address):
                raise ValueError("Use one approved Gmail address per field.")
            if address.count("@") != 1 or not all(address.split("@")):
                raise ValueError("Use one approved Gmail address per field.")
        if not all((self.client_id, self.client_secret.get_secret_value(), self.refresh_token.get_secret_value())):
            raise ValueError("Gmail OAuth requires an app client and refresh token.")


class GmailEmail:
    """One approved recipient; no retries on an ambiguous send outcome."""

    def __init__(self, config: GmailConfig):
        self.config = config
        self._open = build_opener(_NoRedirect()).open

    def _post(self, url: str, data: bytes, content_type: str, token: str | None = None) -> dict:
        headers = {"Content-Type": content_type}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            with self._open(Request(url, data=data, headers=headers, method="POST"), timeout=10) as response:
                body = json.loads(response.read(65536))
        except HTTPError as exc:
            # Once Gmail has accepted a POST, an ambiguous response must be reconciled
            # before any replay. The app should not assume Message-ID deduplicates sends.
            kind = "gmail_send_uncertain" if token and exc.code >= 500 else "gmail_request_rejected"
            raise GmailError(kind) from None
        except (OSError, URLError, ValueError):
            raise GmailError("gmail_send_uncertain" if token else "gmail_token_unavailable") from None
        if not isinstance(body, dict):
            raise GmailError("gmail_send_uncertain" if token else "gmail_token_unavailable")
        return body

    def _refresh(self) -> str:
        cfg = self.config
        form = urlencode({
            "grant_type": "refresh_token",
            "client_id": cfg.client_id,
            "client_secret": cfg.client_secret.get_secret_value(),
            "refresh_token": cfg.refresh_token.get_secret_value(),
        }).encode()
        response = self._post(TOKEN_URL, form, "application/x-www-form-urlencoded")
        scope = response.get("scope")
        if scope is not None and (not isinstance(scope, str) or
                                  "https://www.googleapis.com/auth/gmail.send" not in scope.split()):
            raise GmailError("gmail_send_scope_missing")
        token = response.get("access_token")
        if not isinstance(token, str) or not token or any(c.isspace() for c in token):
            raise GmailError("gmail_token_unavailable")
        return token

    def preflight(self) -> None:
        """Verify Google accepts the refresh grant without calling the send endpoint."""
        self._refresh()

    def deliver(self, key: str, content: Message) -> str:
        cfg = self.config
        token = self._refresh()
        email = EmailMessage()
        email["From"], email["To"], email["Subject"] = cfg.sender, cfg.recipient, content.subject
        email["Message-ID"] = f"<project514-{key}@{cfg.sender.split('@')[1]}>"
        email.set_content(content.plain)
        email.add_alternative(content.html, subtype="html")
        data = json.dumps({"raw": base64.urlsafe_b64encode(email.as_bytes()).decode("ascii")}).encode()
        result = self._post(SEND_URL, data, "application/json", token)
        provider_id = result.get("id")
        if not isinstance(provider_id, str) or not provider_id or not provider_id.isascii() or not provider_id.isalnum():
            raise GmailError("gmail_send_uncertain")
        return provider_id
