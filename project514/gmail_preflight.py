"""Check an environment's Gmail OAuth grant without sending email."""
import argparse
import os
import sys
from collections.abc import Mapping

from pydantic import SecretStr

from .gmail import GmailConfig, GmailEmail, GmailError

SETTINGS = ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN",
            "GMAIL_SENDER", "GMAIL_RECIPIENT")


def load_config(settings: Mapping[str, str]) -> GmailConfig:
    missing = [key for key in SETTINGS if not settings.get(key, "").strip()]
    if missing:
        raise ValueError("Missing settings: " + ", ".join(missing))
    return GmailConfig(
        sender=settings["GMAIL_SENDER"].strip(),
        recipient=settings["GMAIL_RECIPIENT"].strip(),
        client_id=settings["GMAIL_CLIENT_ID"].strip(),
        client_secret=SecretStr(settings["GMAIL_CLIENT_SECRET"].strip()),
        refresh_token=SecretStr(settings["GMAIL_REFRESH_TOKEN"].strip()),
    )


def check(settings: Mapping[str, str], *, refresh: bool = False) -> str:
    config = load_config(settings)
    if not refresh:
        return "Required Gmail settings are present and addresses passed validation. No network request made."
    GmailEmail(config).preflight()
    return "Google accepted the refresh grant. The send endpoint was not called."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Verify the refresh grant with Google.")
    args = parser.parse_args()
    try:
        print(check(os.environ, refresh=args.refresh))
    except (ValueError, GmailError) as exc:
        print(f"Gmail preflight failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
