# Pilot and launch approval

## Three-day procedure

Use synthetic entries and local previews for the first rehearsal. To send a message during a future live pilot, obtain explicit authorization for the exact sender and recipient, pilot dates and per-day sends before enabling any provider. Keep the official 84-day program paused until pilot acceptance.

1. **Day 1 — Baseline.** Choose the start date and timezone. At 06:00 Denver time compare the local day, expected session, HTML and text. Complete the form on a phone-size screen and record whether it takes about a minute. Correct the entry, confirm the existing email still matches, and inspect the stored revision IDs.
2. **Day 2 — Adverse conditions.** Use a fresh synthetic run to exercise fatigue, missing and red-flag inputs. Check the next prescription, alert language and absence of added high-intensity work. Replay the manual dispatch, induce the mock timeout, and inspect the backoff and single logical delivery. Verify the link expires and cannot read another day.
3. **Day 3 — Recovery and operations.** Exercise pause, review and resume, check that no missed work is stacked, and review the generated Sunday sample. Restore a copy of the SQLite database and compare plan/check-in/outbox counts. Record observed dispatch timing, successful saves, failures, unexpected advice and owner feedback. In an explicitly authorized live pilot, compare provider receipt times with the planned times and verify the approved recipient only.

Pilot exit criteria: all three days reviewed, no duplicate logical deliveries or unauthorized access, conservative responses to flagged inputs, usable mobile flow and a tested restore. Resolve any failures and repeat the affected pilot step before signing off.

## Owner approval checklist

- [ ] Confirm repository privacy and permissions; approve the source, synthetic datasets and retention boundaries.
- [ ] Approve pilot dates and official 84-day start, program ceilings, clearance handling, pause/review ownership and training guidance.
- [ ] Select hosting, TLS, authentication and access revocation; agree how the athlete will export and delete data.
- [ ] Approve database location, encryption, backup access, retention limits and tracking preferences. Weight and health detail collection start off.
- [ ] Approve the email provider, sender identity, recipient address and explicit test-send authorization. Verify opt-out and do not reuse an address from unrelated systems.
- [ ] Approve the timezone-aware scheduler and variance alerts at 06:00 America/Denver. Confirm provider latency and retry policy. Evening reminders start off.
- [ ] Approve spending and secret scopes. A small hosted app/database may be roughly US$5–25/month, email and scheduling may fit free allowances or add cost, and narration is optional. These are planning estimates; verify current vendor fees before selection. Credentials would include scoped hosting/deploy access, database access if managed, an email sender credential, and a scheduler service identity. Optional narration needs separate authorization and an API credential.
- [ ] Review pilot results and authorize production deployment, actual sending and scheduling explicitly. Each requires implementation and owner approval beyond this MVP.

## Rollback and restore rehearsal

For local use, stop the server and use `control pause` before any further mock runs using the same demo state. Keep the previous database file with restricted permissions, copy it while the app is stopped, and reopen the copy with `serve --db PATH`. Compare history and email previews; reauthenticate using that process's private entry URL. Keep simulation data in its own output directory. For future production, disable dispatch and scheduling first, reconcile queued sends, preserve existing audit rows, and restore the last verified backup and matching template/rule version before a supervised restart.

## Gmail authorization for unattended delivery

A Gmail connection in Codex can authorize actions in the chat. A hosted worker needs a separate Google OAuth client with Gmail API enabled and the narrow `https://www.googleapis.com/auth/gmail.send` scope. The approved sender authorizes this client with offline access. Store its client ID, client secret and refresh token through the host's secret settings. Do not paste tokens into chat or source control. Confirm the OAuth consent configuration supports ongoing offline use; an external OAuth app in Google's Testing state can receive refresh tokens that expire after seven days. If applicable, check Google Workspace policy and consent or verification requirements before relying on the worker.

The Gmail transport has mock HTTP tests for OAuth refresh, a single approved recipient, multipart formatting and ambiguous send failures. Its endpoints are `oauth2.googleapis.com` and `gmail.googleapis.com`. The current app and manual dispatch still use the mock only. Before connecting the transport, choose the production host, configure authenticated HTTPS check-in URLs, set the approved sender and recipient, and verify how a worker will reconcile an uncertain Gmail response without automatically resending.

Run the preflight inside the environment that holds the five Gmail settings:

```sh
python -m project514.gmail_preflight
python -m project514.gmail_preflight --refresh
```

The first command checks presence and address format without network access. The second asks Google's token endpoint to validate the refresh grant and discards the access token. Neither command sends an email. A successful refresh does not establish the sender's identity or verify receipt. Keep the refresh grant and the final pilot send separate.

For the GitHub `pilot` environment, open **Actions → Gmail pilot preflight → Run workflow**, select `main`, and inspect the **Check refresh grant without sending mail** step. The workflow is manual and reads the configured `pilot` values only for that step.
