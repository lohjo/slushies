# platform — Agent Deployment Prompt
# msitarzewski/agency-agents
---

## Suggested agents for this project scope

| Agent | File | Best used for |
|-------|------|---------------|
| 🏗️ Backend Architect | `engineering/engineering-backend-architect.md` | Flask structure, ORM, API design, Google Sheets integration |
| 🚀 DevOps Automator | `engineering/engineering-devops-automator.md` | Railway/Render deployment, env vars, gunicorn, CI |
| 🔒 Security Engineer | `engineering/engineering-security-engineer.md` | Auth review, webhook secret, participant privacy (no PII) |

The **Agents Orchestrator** (`specialized/agents-orchestrator.md`) can run
all three in sequence if you want a single end-to-end deployment session.

---

## Prompt 1 — Backend Architect
### Use this to: validate the Flask structure, review the Google Sheets pipeline, and extend the API

```
Activate Backend Architect mode.

You are reviewing and extending a Flask application called `platform` — a
survey pipeline tool for a youth-at-risk programme run by Impart Singapore
and Ngee Ann Polytechnic.

## Project context

The app is scaffolded at ``. Read `ARCHITECTURE.md` first for
the full data pipeline. Key facts:

- Stack: Flask + SQLAlchemy + SQLite (dev) / PostgreSQL (prod)
- External API: Google Sheets API v4 via a Service Account JSON key
- Pipeline: Google Forms → Google Sheets → Flask webhook → scoring → PDF card
- Four psychometric frameworks: ACT SG, CMI, Rosenberg, Eudaimonic WB
- No PII is stored — participants use self-generated anonymous codes

## Files to read first

1. `ARCHITECTURE.md` — full pipeline documentation
2. `app/models.py` — four tables: User, Participant, SurveyResponse, GrowthCard
3. `app/services/sync_service.py` — the pipeline orchestrator
4. `app/services/sheets_service.py` — Google Sheets API calls and column mapping
5. `app/services/score_service.py` — all scoring logic (pure Python, no Flask deps)

## Your tasks

1. Review `app/services/sheets_service.py`. Confirm the `COL_MAP` column
   order is correctly mapped. Flag any edge cases where a participant
   submits a partial form (some fields blank) — verify `safe_float()` handles
   them gracefully without crashing `process_row()`.

2. Review `app/services/sync_service.py`. Confirm the deduplication logic
   using `sheet_row_index` is watertight — there must be no scenario where
   the same row is written twice even if the webhook fires twice (e.g. Apps
   Script retry on network timeout).

3. Review `app/routes/api.py`. The `/api/export/csv` route currently exports
   a flat CSV. Extend it to include a `delta_*` column for each of the four
   frameworks (ACT, CMI, Rosenberg, EWB) by joining `GrowthCard` to the
   export query. The delta values are already stored on `GrowthCard`.

4. Confirm `app/config.py` correctly handles the `postgres://` →
   `postgresql://` URL rewrite that Heroku/Render inject. Verify
   `ProductionConfig` will not silently fall back to SQLite if
   `DATABASE_URL` is unset.

## Definition of done

- No crashes on partial form submissions
- No duplicate rows under webhook retry
- CSV export includes delta columns
- Production config fails loudly (not silently) when `DATABASE_URL` is missing
```

---

## Prompt 2 — DevOps Automator
### Use this to: deploy to Railway, set up environment variables, configure gunicorn

```
Activate DevOps Automator mode.

You are deploying a Flask application called `platform` to Railway.app.
The app is at ``. Read `ARCHITECTURE.md` for the full system
overview before starting.

## Stack

- Python 3.11, Flask 3.x, SQLAlchemy, Flask-Migrate
- Database: PostgreSQL (Railway plugin)
- PDF generation: WeasyPrint (requires system-level fonts in the container)
- External dependency: Google Sheets API (Service Account JSON key — must
  be injected as a secret, NOT committed to the repo)

## Your tasks

### Task 1 — Procfile and gunicorn

Create a `Procfile` in the project root:

```
web: gunicorn run:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
release: flask db upgrade
```

The `release` command runs Flask-Migrate on every deploy so the
PostgreSQL schema stays in sync automatically.

### Task 2 — railway.json

Create `railway.json` in the project root to configure the build:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "gunicorn run:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120",
    "healthcheckPath": "/login",
    "healthcheckTimeout": 30,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

### Task 3 — nixpacks.toml (WeasyPrint system dependencies)

WeasyPrint requires Pango, Cairo, and font libraries. Create `nixpacks.toml`:

```toml
[phases.setup]
nixPkgs = [
  "python311",
  "pango",
  "cairo",
  "gdk-pixbuf",
  "libffi",
  "fontconfig",
  "freetype",
]

[phases.install]
cmds = ["pip install -r requirements.txt"]
```

### Task 4 — Environment variable checklist

Verify the following variables are set in the Railway dashboard
(Settings → Variables) before the first deploy:

| Variable | Value source |
|----------|-------------|
| `FLASK_ENV` | `production` |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | Auto-injected by Railway PostgreSQL plugin |
| `GOOGLE_SHEET_ID` | From the Google Sheet URL |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Path to the key file (see Task 5) |
| `WEBHOOK_SECRET` | Match the value in Google Apps Script |

### Task 5 — Service Account key injection

The `service-account-key.json` must NOT be in the repository. Configure it
as a Railway volume or inject the JSON content as an environment variable:

Option A (recommended): Store the entire JSON as `GOOGLE_SERVICE_ACCOUNT_JSON`
and update `sheets_service._get_service()` to load from env:

```python
import json, os
from google.oauth2 import service_account

def _get_service():
    json_str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if json_str:
        info = json.loads(json_str)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=SCOPES
        )
    else:
        creds = service_account.Credentials.from_service_account_file(
            current_app.config["GOOGLE_SERVICE_ACCOUNT_FILE"], scopes=SCOPES
        )
    return build("sheets", "v4", credentials=creds)
```

### Task 6 — Post-deploy smoke test

After the first successful deploy, run these checks:

1. `GET /login` returns 200 (healthcheck passes)
2. Log in with the admin account seeded via `flask create-admin`
3. `POST /api/sync` returns a JSON array of row results
4. `GET /api/export/csv` returns a valid CSV download

## Definition of done

- App deploys without build errors on Railway
- WeasyPrint renders PDFs without font/library errors in the container
- `flask db upgrade` runs cleanly on the PostgreSQL plugin database
- All six environment variables are confirmed set
- Smoke test passes on the live URL
```

---

## Prompt 3 — Security Engineer
### Use this to: review auth, the webhook, and participant privacy before going live

```
Activate Security Engineer mode.

You are performing a pre-launch security review of a Flask application
called `platform`. This app handles survey responses from youth-at-risk
participants. Privacy is critical — no PII is stored by design, but that
design must be verified.

Read `ARCHITECTURE.md` fully before starting. Then review the files below.

## Threat model context

- Users of the admin interface: Impart staff and NP volunteers (trusted)
- Data sensitivity: Psychometric scores for youth-at-risk (sensitive but not
  clinical/medical). Participant codes are anonymous mnemonics.
- Attack surface: Public-facing webhook endpoint, staff login form,
  Google Service Account key file
- Compliance context: Singapore PDPA — no names, NRIC, or contact details
  may be stored

## Files to review

1. `app/routes/auth.py` — login, logout, register
2. `app/routes/webhook.py` — the public-facing Apps Script receiver
3. `app/routes/api.py` — protected CRUD and export routes
4. `app/models.py` — confirm no PII columns exist anywhere
5. `app/__init__.py` — Flask-Login configuration
6. `app/config.py` — `SECRET_KEY` and `WEBHOOK_SECRET` handling

## Your tasks

### Task 1 — Authentication review

Review `auth.py` and `__init__.py`:

- Confirm passwords are stored as bcrypt hashes (never plaintext)
- Confirm `login_manager.login_view` redirects unauthenticated users to
  `/login` rather than returning a 500
- Confirm the `/register` route is gated behind `@login_required` AND
  an `admin` role check — staff must not be able to create new admin accounts
- Flag any missing `next` parameter sanitisation on the post-login redirect
  (open redirect risk if `next` accepts absolute URLs)

### Task 2 — Webhook security review

Review `webhook.py`:

- Confirm `hmac.compare_digest()` is used (not `==`) to prevent timing attacks
- Confirm the endpoint returns 401 (not 403 or 200) on secret mismatch
- Confirm the endpoint does NOT log or echo back the raw payload in error
  responses (would expose participant codes in server logs)
- Assess whether rate limiting is needed — an unauthenticated POST endpoint
  with no rate limit could be abused to flood the database with fake rows

### Task 3 — PII audit

Review `app/models.py` column by column:

- Confirm `Participant` stores only `code` and `cohort` — no name, email,
  school, phone, or any other identifier
- Confirm `SurveyResponse` stores only numeric scores and open-text
  reflections (E1–E4). Flag if any reflection question asked for the
  participant's name or contact details (check `growth_card.html` too)
- Confirm `GrowthCard` stores only file paths and score deltas — no email
  address for delivery is stored in the DB

### Task 4 — Secret key risk

Review `app/config.py`:

- Confirm `SECRET_KEY` has a non-trivial default and emits a warning in
  production if the default is still in use
- Confirm `WEBHOOK_SECRET` is not hardcoded anywhere in source files
- Confirm `service-account-key.json` is listed in `.gitignore`

### Task 5 — Output

Produce a threat model summary in this format:

```
## Security review — platform

### Findings

| Severity | Area | Issue | Fix |
|----------|------|-------|-----|
| HIGH     | ...  | ...   | ... |
| MEDIUM   | ...  | ...   | ... |
| LOW      | ...  | ...   | ... |

### PDPA compliance assessment
[Pass / Needs attention] + rationale

### Cleared for launch?
[ ] YES — no blockers found
[ ] NO — resolve HIGH findings first
```

## Definition of done

- All HIGH severity findings resolved
- PDPA assessment returns Pass
- `.gitignore` confirmed to exclude `service-account-key.json` and `.env`
```

---

## Optional: Run all three agents in sequence with the Orchestrator

```
Activate AgentsOrchestrator mode.

Run the following three-agent pipeline on the `` project.
Read `ARCHITECTURE.md` first to understand the system.

Pipeline:

1. Spawn **Backend Architect** — run the Backend Architect prompt in
   `AGENT_PROMPTS.md` (Task 1: partial form handling, Task 2: dedup,
   Task 3: CSV delta columns, Task 4: production config).
   Mark complete when all four tasks pass.

2. Spawn **DevOps Automator** — run the DevOps Automator prompt in
   `AGENT_PROMPTS.md` (Tasks 1–6: Procfile, railway.json, nixpacks.toml,
   env vars, service account injection, smoke test).
   Mark complete when the smoke test passes on the live Railway URL.

3. Spawn **Security Engineer** — run the Security Engineer prompt in
   `AGENT_PROMPTS.md` (Tasks 1–4: auth, webhook, PII audit, secrets).
   Mark complete only when the security review table shows no HIGH findings
   and PDPA assessment returns Pass.

Do not advance to the next agent until the current one marks its tasks
complete. If any agent returns a FAIL or finds a HIGH severity issue,
loop back to Backend Architect to fix it before proceeding.
```
