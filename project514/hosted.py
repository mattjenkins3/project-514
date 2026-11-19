"""Private HTTPS pilot entry point for a single Render service."""
import os
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from .delivery import Coach
from .models import Athlete, Cycle
from .store import Store
from .web import LocalAuth, create_app


def build(settings: Mapping[str, str]):
    origin = settings.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    url = urlsplit(origin)
    if url.scheme != "https" or not url.hostname or url.netloc != url.hostname or any(
        (url.path, url.query, url.fragment)
    ):
        raise ValueError("RENDER_EXTERNAL_URL must be the hosted HTTPS origin.")
    try:
        start = date.fromisoformat(settings["PROJECT514_PILOT_START"])
    except (KeyError, ValueError):
        raise ValueError("Set PROJECT514_PILOT_START to YYYY-MM-DD in Denver time.") from None
    password = settings.get("PROJECT514_PILOT_PASSWORD", "").encode()
    key = settings.get("PROJECT514_SESSION_KEY", "").encode()
    if min(len(password), len(key)) < 32 or password == key:
        raise ValueError("Set distinct, randomly generated pilot password and session key (32+ characters each).")
    disk = Path(settings.get("PROJECT514_DATA_DIR", "/var/data"))
    if not disk.is_absolute() or not disk.is_dir():
        raise ValueError("Attach the persistent disk before starting the hosted pilot.")
    athlete = Athlete()
    cycle = Cycle(cycle_id=f"pilot-{start}", athlete_id=athlete.athlete_id, start=start)
    coach = Coach(Store(disk / "project514.sqlite3"), athlete, cycle,
                  lambda when, _at: f"{origin}/check-in/{when}")
    app, _ = create_app(coach, LocalAuth(key), origin, hosted_password=password)
    return app


def main():
    import uvicorn

    uvicorn.run(build(os.environ), host="0.0.0.0", port=int(os.getenv("PORT", "10000")),
                access_log=False, proxy_headers=False)


if __name__ == "__main__":
    main()
