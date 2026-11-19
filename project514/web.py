"""Loopback-only synthetic check-in and preview UI."""
import hmac
import secrets
from collections import deque
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from html import escape
from threading import Lock
from time import monotonic
from typing import Protocol
from urllib.parse import parse_qsl, quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .delivery import Coach
from .models import CLIMBING, DENVER, CheckinData, Kind
from .render import workout
from .store import latest_checkins

COOKIE = "project514"
SESSION_SECONDS = 3600
LINK_SECONDS = 36 * 3600
MAX_BODY = 4096


class AuthenticationProvider(Protocol):
    def issue(self, purpose: str, scope: str, at: datetime, ttl: int) -> str: ...
    def verify(self, token: str, purpose: str, at: datetime) -> str | None: ...
    def csrf(self, session: str, scope: str) -> str: ...


class LocalAuth:
    def __init__(self, key: bytes | None = None):
        self.key = key if key is not None else secrets.token_bytes(32)

    def sign(self, value: str) -> str:
        return hmac.digest(self.key, value.encode(), "sha256").hex()

    def issue(self, purpose: str, scope: str, at: datetime, ttl: int) -> str:
        payload = f"{purpose}:{scope}:{int(at.timestamp()) + ttl}:{secrets.token_urlsafe(12)}"
        return f"{payload}.{self.sign(payload)}"

    def verify(self, token: str, purpose: str, at: datetime) -> str | None:
        if len(token) > 512 or not token.isascii():
            return None
        try:
            payload, signature = token.split(".")
            use, scope, expiry, _nonce = payload.split(":")
            if use == purpose and int(expiry) > int(at.timestamp()) and hmac.compare_digest(
                signature, self.sign(payload)
            ):
                return scope
        except ValueError:
            return None
        return None

    def csrf(self, session: str, scope: str) -> str:
        return self.sign(f"csrf:{scope}:{session}")


STYLE = """
:root{font:16px/1.45 system-ui,sans-serif;color:#143032;background:#eaf1ed}
*{box-sizing:border-box}body{margin:0}main{max-width:38rem;margin:auto;padding:1.2rem}
h1{font-size:1.8rem;margin:.6rem 0}h2{font-size:1.2rem}a{color:#075951}
.card,form{background:white;border-radius:.9rem;padding:1rem;margin:1rem 0}
label{display:block;font-weight:600;margin-top:.75rem}select,input:not([type=checkbox]),button{
font:inherit;padding:.55rem;width:100%;min-height:44px;border:1px solid #75918b;border-radius:.4rem}
input[type=checkbox]{width:1.2rem;height:1.2rem;vertical-align:middle}
button{background:#124e47;color:white;font-weight:700;margin-top:1rem}
summary{padding:.7rem 0;cursor:pointer}small{display:block;margin:.5rem 0}
:focus-visible{outline:3px solid #bd4d27;outline-offset:2px}
"""


def page(title: str, body: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(
        f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" '
        f'content="width=device-width, initial-scale=1"><title>{escape(title)}</title>'
        f'<style>{STYLE}</style><main><h1>{escape(title)}</h1>{body}</main></html>', status
    )


def select(name: str, label: str, choices: dict[str, str], values: dict, required: bool = False) -> str:
    options = "".join(
        f'<option value="{escape(key)}"{" selected" if values.get(name) == key else ""}>{escape(description)}</option>'
        for key, description in choices.items()
    )
    return (f'<label for="{name}">{label}</label><select id="{name}" name="{name}"'
            f'{" required" if required else ""}><option value="">Choose…</option>{options}</select>')


ENERGY = {"good": "Good", "okay": "Okay", "poor": "Poor"}
COMPLETION = {"full": "Completed", "partial": "Partially completed", "missed": "Missed"}
OPTIONS = {
    "discomfort": {"none": "None", "mild": "Mild", "significant_or_worsening": "Significant or worsening"},
    "symptom": {"none": "None", "illness": "Illness", "chest_or_breathing": "Chest or breathing symptoms",
                "unsafe_movement": "Could not move safely"},
    "area": {"finger": "Finger", "shoulder": "Shoulder", "tendon": "Tendon", "other": "Other"},
    "late_technique": {"steady": "Steady", "faded": "Faded"},
    "nutrition": {"well_fueled": "Well fueled", "under_fueled": "Underfueled", "unknown": "Unsure"},
    "strength_done": {"true": "Yes", "false": "No"},
}
NUMBERS = {
    "rpe": ("Session effort (RPE 1–10)", 1, 10, "1"),
    "pump": ("Forearm pump (0–10)", 0, 10, "1"),
    "duration": ("Primary session minutes", 0, 600, "1"),
    "miles": ("Actual running miles", 0, 50, ".01"),
    "low_load_hang_minutes": ("Supplemental low-load hang minutes", 0, 30, "1"),
}
FORM_FIELDS = set(CheckinData.model_fields) - {"schema_version"}


def form(plan, values: dict, csrf: str, rev: int, saved: bool = False, error: str = "") -> Response:
    resting = plan.session.kind == Kind.REST
    climbing = plan.session.kind in CLIMBING
    completion = {"rest_done": "Rest day", "full": "Other activity", "partial": "Some activity"} if resting else COMPLETION

    def number(name: str) -> str:
        label, low, high, step = NUMBERS[name]
        value = values.get(name)
        return (f'<label for="{name}">{label}</label><input id="{name}" name="{name}" type="number" '
                f'min="{low}" max="{high}" step="{step}" value="{escape(str(value), quote=True) if value is not None else ""}">')

    def choice(name: str, label: str) -> str:
        return select(name, label, OPTIONS[name], values)

    marker = ('<p role="status">Saved. You can correct this entry below.</p>' if saved else "")
    if error:
        marker += f'<p role="alert">{escape(error)}</p>'
    fields = select("completion", "Session outcome", completion, values, True)
    fields += select("energy", "Energy", ENERGY, values, True)
    fields += select("discomfort", "Discomfort", OPTIONS["discomfort"], values, True)
    fields += choice("symptom", "Safety symptoms")
    if not resting:
        fields += number("rpe")
    if climbing:
        fields += number("pump")
    optional = number("duration") + number("miles") + choice("area", "Discomfort area")
    optional += select("sleep", "Sleep", ENERGY, values) + choice("nutrition", "Fueling")
    optional += choice("strength_done", "Supplemental strength completed") + number("low_load_hang_minutes")
    if climbing:
        optional += choice("late_technique", "Final-third climbing technique")
    response = page(
        "Daily check-in",
        f'<p>Project 5.14 · {plan.local_date} · {escape(plan.session.kind)}</p>'
        f'<p class="card">{escape(workout(plan.session, plan.week))}</p>'
        f'{marker}<form method="post"><input type="hidden" name="csrf" value="{csrf}">'
        f'<input type="hidden" name="revision" value="{rev}">{fields}'
        f'<details><summary>Optional details</summary>{optional}</details>'
        f'<label><input type="checkbox" name="reduce_next" value="true"'
        f'{" checked" if values.get("reduce_next") else ""}> Request a lighter next day</label>'
        '<button type="submit">Save check-in</button>'
        '<small>Local test data only. Stop painful loading and seek urgent help for concerning chest or breathing symptoms.</small>'
        '</form><p><a href="/">Dashboard</a></p>',
        422 if error else 200,
    )
    # Chromium sends an opaque Origin for a no-referrer form navigation. The
    # authenticated form URL is clean; capabilities still use no-referrer.
    response.headers["Referrer-Policy"] = "same-origin"
    return response


def create_app(coach: Coach, auth: AuthenticationProvider, base_url: str,
               clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> tuple[FastAPI, str]:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    bootstrap = secrets.token_urlsafe(32)
    dashboard = "dashboard"
    # Per-instance budget for authenticated mutations and capability exchanges.
    recent: deque[float] = deque()
    lock = Lock()

    def rate_limit() -> None:
        now = monotonic()
        with lock:
            while recent and now - recent[0] >= 60:
                recent.popleft()
            if len(recent) >= 30:
                raise HTTPException(429, "Too many requests. Try again shortly.")
            recent.append(now)

    @app.middleware("http")
    async def headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.update({
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; "
                                       "form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
        })
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    def scope(day: date) -> str:
        return f"{coach.cycle.cycle_id}/{day}"

    def get_session(request: Request, allowed: str = dashboard) -> str:
        token = request.cookies.get(COOKIE, "")
        if auth.verify(token, "session", clock()) not in {dashboard, allowed}:
            raise HTTPException(403, "Open the local preview entry link or a valid check-in link.")
        return token

    def redirect_session(path: str, allowed: str) -> Response:
        response = RedirectResponse(path, status_code=303)
        response.set_cookie(COOKIE, auth.issue("session", allowed, clock(), SESSION_SECONDS),
                            httponly=True, samesite="strict", max_age=SESSION_SECONDS)
        return response

    def state():
        with coach.store.transaction() as db:
            return (coach.store.plans(db, coach.cycle.cycle_id),
                    latest_checkins(coach.store.history(db, coach.cycle.cycle_id)))

    @app.get("/enter")
    def enter(key: str = ""):
        rate_limit()
        if not key.isascii() or not hmac.compare_digest(key, bootstrap):
            raise HTTPException(403, "Invalid local entry key.")
        return redirect_session("/", dashboard)

    @app.get("/")
    def index(request: Request):
        get_session(request)
        now = clock()
        today = now.astimezone(DENVER).date()
        if coach.cycle.start <= today <= coach.cycle.end:
            coach.prepare(today, now)
        plans, logs = state()
        rows = "".join(
            f'<li>{p.local_date} · {escape(p.session.kind)} · '
            f'{escape(logs[p.local_date].data.completion) if p.local_date in logs else "Awaiting check-in"} · '
            f'<a href="/email/{p.local_date}">HTML</a> · <a href="/email/{p.local_date}?plain=true">Text</a> · '
            f'<a href="/check-in/{p.local_date}">Check-in</a></li>'
            for p in reversed(plans)
        )
        return page("Project 5.14", '<p>Local coaching preview. Use synthetic entries only.</p>'
                    f'<section class="card"><h2>Plan history</h2><ul>{rows}</ul></section>')

    @app.get("/email/{day}")
    def preview(day: date, request: Request, plain: bool = False):
        get_session(request)
        plans, _ = state()
        plan = next((p for p in plans if p.local_date == day), None)
        if plan is None:
            raise HTTPException(404, "No prepared plan.")
        with coach.store.transaction() as db:
            row = db.execute("SELECT plain,html FROM outbox WHERE key=?", (plan.prescription_id,)).fetchone()
        return PlainTextResponse(row["plain"]) if plain else HTMLResponse(row["html"])

    def for_day(day: date):
        plans, logs = state()
        plan = next((p for p in plans if p.local_date == day), None)
        if plan is None:
            raise HTTPException(404, "No prepared plan.")
        return plan, logs.get(day)

    @app.get("/check-in/{day}")
    def checkin(day: date, request: Request, link: str = "", saved: bool = False):
        allowed = scope(day)
        if link:
            rate_limit()
            if auth.verify(request.cookies.get(COOKIE, ""), "session", clock()) == dashboard:
                return RedirectResponse(f"/check-in/{day}", status_code=303)
            if auth.verify(link, "checkin", clock()) != allowed:
                raise HTTPException(403, "Invalid or expired check-in link.")
            return redirect_session(f"/check-in/{day}", allowed)
        token = get_session(request, allowed)
        plan, entry = for_day(day)
        values = entry.data.model_dump() if entry else {"symptom": "none"}
        if values.get("strength_done") is not None:
            values["strength_done"] = str(values["strength_done"]).lower()
        return form(plan, values, auth.csrf(token, allowed), entry.revision if entry else 0, saved)

    @app.post("/check-in/{day}")
    async def submit(day: date, request: Request):
        allowed = scope(day)
        token = get_session(request, allowed)
        rate_limit()
        if request.headers.get("origin", base_url) != base_url:
            raise HTTPException(403, "Invalid form origin.")
        if request.headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
            raise HTTPException(415, "Expected form submission.")
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_BODY:
                raise HTTPException(413, "Form too large.")
            body.extend(chunk)
        try:
            pairs = parse_qsl(body.decode("ascii"), keep_blank_values=True, strict_parsing=True,
                              encoding="utf-8", errors="strict", max_num_fields=25)
            values = dict(pairs)
            if len(values) != len(pairs):
                raise ValueError
        except ValueError:
            raise HTTPException(400, "Malformed form.") from None
        csrf = values.pop("csrf", "")
        if not csrf.isascii() or not hmac.compare_digest(csrf, auth.csrf(token, allowed)):
            raise HTTPException(403, "Invalid form signature.")
        if day > clock().astimezone(DENVER).date():
            raise HTTPException(422, "This session is in the future.")
        plan, entry = for_day(day)
        try:
            rev = int(values.pop("revision"))
            if set(values) - FORM_FIELDS:
                raise ValueError("Unknown field")
            data = CheckinData.model_validate({k: v for k, v in values.items() if v != ""})
            coach.store.submit(plan, data, clock(), rev)
        except (KeyError, ValueError):
            # Do not echo raw validation input, credentials, or private payloads.
            safe = {k: v for k, v in values.items() if k in FORM_FIELDS and k not in NUMBERS}
            return form(plan, safe, auth.csrf(token, allowed), entry.revision if entry else 0,
                        error="Check the marked ranges and session outcome. If this form is stale, reload it.")
        return RedirectResponse(f"/check-in/{day}?saved=true", status_code=303)

    return app, f"{base_url}/enter?key={quote(bootstrap)}"
