# Project 5.14

A local coaching prototype for a 12-week climbing and running block. It prepares a daily plan, accepts a short mobile check-in, and records the evidence behind the next plan. Every email is a browser preview, file, or in-process mock. The demo uses synthetic data and keeps the official start date unset.

## Run locally

From the repository root with Python 3.12 and IANA timezone data installed:

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m project514.demo serve --port 8000
```

Open the private loopback entry URL printed by `serve` in a browser on the same machine. The dashboard links to that day's **HTML**, **Text**, and **Check-in**. Save a synthetic entry, then edit it to see correction history take effect on future plans. Use the printed URL again after the dashboard session expires. Stop the server with Ctrl+C. To preview in a remote cloud workspace, open the URL using a browser on that machine.

To generate a week of HTML and text samples plus deload and red-flag examples, run:

```sh
.venv/bin/python -m project514.demo simulate --start 2026-02-16 --output .local/mixed
.venv/bin/python -m project514.demo simulate --start 2026-02-16 --scenario steady --output .local/steady
```

Choose fresh output directories if these exist already. Open `.local/mixed/email-2026-02-16.html` or read its `.txt` counterpart. The links in exported emails are illustrative. The mixed run produces 84 plans, 82 mock deliveries, two paused days and one recovered timeout. The steady run produces 84 mock deliveries. Each writes a JSON summary, the full decision trace, and a SQLite ledger.

Local controls affect future days. The review command records manual acknowledgement after the concern has been assessed; it cannot determine fitness to exercise.

```sh
.venv/bin/python -m project514.demo control pause
.venv/bin/python -m project514.demo control resume
.venv/bin/python -m project514.demo control review
```

The default local database is `.local/demo.sqlite3`. Pass `--db PATH` to use a separate synthetic sandbox. Stop the app before copying or removing a demo database. Keep local databases, terminal entry links, real athlete data, and preview artifacts out of source control.

See the [architecture and decisions](docs/architecture.md) for rules and scope, and the [pilot runbook](docs/pilot.md) for rollback and the production approval gate.
