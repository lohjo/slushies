# ARCHITECTURE.md
# platform — Data Pipeline & System Architecture

> **Project:** platform by Impart × Ngee Ann Polytechnic
> **Stack:** Flask · SQLAlchemy · SQLite (dev) / PostgreSQL (prod) · Google Sheets API v4 · WeasyPrint
> **Last updated:** 2025

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Repository Structure](#2-repository-structure)
3. [Data Pipeline — End to End](#3-data-pipeline--end-to-end)
   - 3.1 [Stage 1 — Survey Submission](#31-stage-1--survey-submission-google-forms)
   - 3.2 [Stage 2 — Transport to Flask](#32-stage-2--transport-webhook-vs-poll)
   - 3.3 [Stage 3 — Parsing & Validation](#33-stage-3--parsing--validation)
   - 3.4 [Stage 4 — Scoring](#34-stage-4--scoring)
   - 3.5 [Stage 5 — Persistence](#35-stage-5--persistence)
   - 3.6 [Stage 6 — Growth Card Generation](#36-stage-6--growth-card-generation)
   - 3.7 [Stage 7 — Delivery](#37-stage-7--delivery)
4. [Database Schema](#4-database-schema)
5. [Authentication & Route Protection](#5-authentication--route-protection)
6. [Google Sheets API Integration](#6-google-sheets-api-integration)
7. [Scoring Logic Reference](#7-scoring-logic-reference)
8. [Configuration & Environment Variables](#8-configuration--environment-variables)
9. [Running Locally](#9-running-locally)
10. [Deployment](#10-deployment)
11. [Testing](#11-testing)
12. [Security Considerations](#12-security-considerations)
13. [Extending the System](#13-extending-the-system)

---

## 1. System Overview

*platform* is a Flask web application that automates the full impact-measurement pipeline for Impart's youth-at-risk programme. It connects four validated psychometric frameworks — ACT SG, CMI, Rosenberg Self-Esteem Scale, and Eudaimonic Well-Being Scale — to a live data source (Google Forms → Google Sheets), computes pre/post change scores, and generates a personalised PDF growth card for each participant immediately after they complete the post-survey.

```
┌─────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL LAYER                             │
│                                                                     │
│   Google Forms (pre)          Google Forms (post)                   │
│         │                           │                               │
│         └──────────┬────────────────┘                               │
│                    │  auto-appends rows                             │
│                    ▼                                                │
│             Google Sheets (responses DB)                            │
│                    │                                                │
│         ┌──────────┴──────────────┐                                 │
│         │ Apps Script trigger     │  OR  │ Manual /api/sync │       │
│         │ (real-time webhook)     │      │ (staff-initiated) │       │
└─────────┼─────────────────────────┼──────┴──────────────────┴───────┘
          │                         │
          ▼                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          FLASK APPLICATION                          │
│                                                                     │
│  /webhook/form-submit          /api/sync                            │
│         │                         │                                 │
│         └──────────┬──────────────┘                                 │
│                    │                                                │
│             sync_service.py  (orchestrator)                         │
│                    │                                                │
│         ┌──────────┼──────────────┐                                 │
│         ▼          ▼              ▼                                 │
│  sheets_service  score_service  card_service                        │
│  (parse row)    (compute Δ)    (render PDF)                         │
│         │          │              │                                 │
│         └──────────┼──────────────┘                                 │
│                    ▼                                                │
│             SQLAlchemy ORM                                          │
│                    │                                                │
│         ┌──────────┴──────────┐                                     │
│         │  SQLite (dev)       │                                     │
│         │  PostgreSQL (prod)  │                                     │
│         └─────────────────────┘                                     │
│                                                                     │
│  Protected routes (Flask-Login):                                    │
│  /dashboard  /api/*  /webhook/*                                     │
└─────────────────────────────────────────────────────────────────────┘
          │
          ▼
   PDF growth card → emailed to participant / saved to Drive
```

---

## 2. Repository Structure

```

│
├── run.py                        # App entrypoint + Flask CLI commands
├── requirements.txt
├── .env.example                  # Copy to .env and fill in secrets
│
├── app/
│   ├── __init__.py               # App factory (create_app)
│   ├── config.py                 # Dev / Prod / Testing configs
│   ├── models.py                 # SQLAlchemy models (User, Participant,
│   │                             #   SurveyResponse, GrowthCard)
│   │
│   ├── routes/
│   │   ├── auth.py               # /login  /logout  /register
│   │   ├── dashboard.py          # /dashboard  /dashboard/participant/<code>
│   │   ├── api.py                # /api/sync  /api/participants  /api/responses
│   │   │                         # /api/cards  /api/export/csv
│   │   └── webhook.py            # /webhook/form-submit  (Apps Script target)
│   │
│   ├── services/
│   │   ├── sheets_service.py     # Google Sheets API calls + row parsing
│   │   ├── score_service.py      # All scoring logic (pure Python)
│   │   ├── card_service.py       # HTML → PDF via WeasyPrint
│   │   └── sync_service.py       # Orchestrator — ties all services together
│   │
│   └── templates/
│       ├── auth/
│       │   ├── login.html
│       │   └── register.html
│       ├── dashboard/
│       │   ├── index.html
│       │   └── participant.html
│       └── cards/
│           └── growth_card.html  # Jinja2 template rendered to PDF
│
├── instance/
│   ├── platform_dev.db           # SQLite file (git-ignored)
│   └── cards/                    # Generated PDFs (git-ignored)
│
├── migrations/                   # Flask-Migrate / Alembic files
│
├── tests/
│   └── test_score_service.py     # Unit tests for scoring logic
│
└── scripts/
    └── apps_script_trigger.gs    # Paste into Google Apps Script
```

---

## 3. Data Pipeline — End to End

### 3.1 Stage 1 — Survey Submission (Google Forms)

Two separate Google Forms are created — one for the pre-survey (administered at the start of Workshop 1) and one for the post-survey (administered at the end of Workshop 2c). Both forms are linked to **the same Google Sheet**, with each form writing to its own tab (`Pre` and `Post` respectively), or alternatively to the same tab with a question at the top of the form that asks the participant to select `pre` or `post`.

Every form includes a **participant code** question as the second field (after the auto-generated timestamp). The code is a self-generated mnemonic (e.g. first two letters of the participant's mother's name + birth day number) that allows pre and post responses to be matched without storing any personally identifiable information.

Column order in the sheet is fixed and must match the `COL_MAP` dictionary in `sheets_service.py`. The current expected order is:

| Column | Content |
|--------|---------|
| A | Timestamp (auto) |
| B | Participant code |
| C | Survey type (`pre` / `post`) |
| D–E | Profile fields F1–F2 |
| F–K | ACT SG items A1–A6 |
| L–Q | CMI items B1–B6 |
| R–AA | Rosenberg items C1–C10 |
| AB–AG | Eudaimonic WB items D1–D6 |
| AH–AK | Open reflection E1–E4 (post only; blank for pre) |

If the form question order changes, update `COL_MAP` in `sheets_service.py` to match. Nothing else needs to change.

---

### 3.2 Stage 2 — Transport: Webhook vs Poll

There are two ways the Flask app learns about new form submissions. Both ultimately call the same `process_row()` function in `sync_service.py`, so they produce identical results.

#### Option A — Apps Script Webhook (recommended for production)

An `onFormSubmit` trigger is registered in Google Apps Script inside the Sheet. When a form is submitted, Apps Script immediately fires an HTTP POST to `/webhook/form-submit` on the Flask server, passing the row values and row index as JSON.

```
Google Forms submit
      │
      ▼ (milliseconds)
Google Sheets (new row appended)
      │
      ▼ (Apps Script trigger fires)
POST /webhook/form-submit
  { "row_index": 42, "values": ["2025-04-01", "AB01", "post", ...] }
      │
      ▼
sync_service.process_row()
```

The webhook endpoint validates a shared secret passed in the `X-Webhook-Secret` header before processing anything. This prevents unauthenticated actors from injecting fake submissions.

**Setup steps:**
1. Open the Google Sheet → Extensions → Apps Script
2. Paste the contents of `scripts/apps_script_trigger.gs`
3. Set `WEBHOOK_URL` to your server URL
4. Set `WEBHOOK_SECRET` to the same value as in your `.env`
5. Add the trigger: Triggers → Add Trigger → `onFormSubmit` → On form submit

#### Option B — Manual Sync (fallback / development)

Any logged-in staff member can trigger a full sheet sync from the dashboard by calling `POST /api/sync`. This fetches every row from the sheet, deduplicates against `sheet_row_index`, and processes any rows not yet in the database.

This is safe to run multiple times — the deduplication check in `sync_service.py` ensures no row is processed twice.

---

### 3.3 Stage 3 — Parsing & Validation

`sheets_service.parse_row(raw_row, row_index)` converts the flat list of strings returned by the Sheets API into a typed dictionary:

- Numeric item responses are cast to `float` via `safe_float()`, which returns `None` on empty or malformed values rather than raising an exception.
- String fields (code, survey type, open reflection) are kept as strings.
- `survey_type` is normalised to lowercase and validated against `{"pre", "post"}`. Any row with a missing code or unrecognised survey type is skipped with a `"skipped"` status.

Rows with `None` values for any scored item will produce `None` domain totals. These are stored as `NULL` in the database and excluded from group-level analysis. This is preferable to imputing values or crashing on incomplete submissions.

---

### 3.4 Stage 4 — Scoring

All scoring logic lives in `score_service.py` and is deliberately decoupled from Flask, SQLAlchemy, and any other framework dependency. This makes it fully unit-testable in isolation.

#### ACT SG (items A1–A6, scale 1–5)

```
act_total   = A1 + A2 + A3 + A4 + A5 + A6   (range 6–30)
act_connect = A1 + A2                          (range 2–10)
act_act     = A3 + A4                          (range 2–10)
act_thrive  = A5 + A6                          (range 2–10)
```

#### CMI (items B1–B6, scale 1–4)

```
cmi_total = B1 + B2 + B3 + B4 + B5 + B6   (range 6–24)
```

#### Rosenberg Self-Esteem Scale (items C1–C10, scale 1–4)

Five items are reverse-scored before summing: C2, C5, C6, C8, C9.

```
Positive items (C1,C3,C4,C7,C10):  score = raw - 1   → 0 to 3
Reverse items  (C2,C5,C6,C8,C9):   score = 4 - raw   → 0 to 3

rsem_total = sum of all 10 scored items   (range 0–30)
Scores below 15 indicate low self-esteem.
```

#### Eudaimonic Well-Being (items D1–D6, scale 1–5)

```
ewb_total = D1 + D2 + D3 + D4 + D5 + D6   (range 6–30)
```

#### Change scores (post minus pre)

```
delta_act  = post.act_total  − pre.act_total
delta_cmi  = post.cmi_total  − pre.cmi_total
delta_rsem = post.rsem_total − pre.rsem_total
delta_ewb  = post.ewb_total  − pre.ewb_total
```

A positive delta indicates improvement. Meaningful change thresholds:

| Scale | Threshold (|Δ| ≥) | Rationale |
|-------|-------------------|-----------|
| ACT SG | 2.0 | ~17% of a 6-item range |
| CMI | 2.0 | ~17% of a 6-item range |
| Rosenberg | 3.0 | Standard MDC for 10-item scale |
| Eudaimonic WB | 2.0 | ~17% of a 6-item range |

#### Cohen's d (group-level effect size)

Computed after all post-surveys are collected, not per-card:

```
d = mean(Δ) / SD(Δ)

Interpretation:
  |d| < 0.2  →  negligible
  |d| < 0.5  →  small
  |d| < 0.8  →  medium
  |d| ≥ 0.8  →  large
```

---

### 3.5 Stage 5 — Persistence

`sync_service.process_row()` orchestrates the database writes:

1. **Upsert Participant** — looks up by `code`. Creates a new `Participant` record if none exists.
2. **Deduplication check** — queries `SurveyResponse` for the same `participant_id`, `survey_type`, and `sheet_row_index`. Skips if found.
3. **Write SurveyResponse** — persists all raw item scores and computed domain totals.
4. **Conditional card generation** — if `survey_type == "post"` and a matching `pre` response exists in the database, proceeds to Stage 6.

All writes within a single row's processing happen in one `db.session.commit()` to prevent partial writes if an error occurs mid-pipeline.

---

### 3.6 Stage 6 — Growth Card Generation

`card_service.generate_card()` is called only when both pre and post responses are present for a participant.

**Steps:**

1. Normalise pre and post domain scores to a 0–100 scale for the radar chart display.
2. Compute human-readable highlight sentences for each scale where `is_meaningful_change()` returns `True`.
3. Extract the participant's answer to reflection question E3 ("What moment are you most proud of?") as a pull quote.
4. Render `templates/cards/growth_card.html` via Jinja2 with all computed values.
5. Pass the rendered HTML string to `WeasyPrint`, which produces a pixel-accurate PDF without requiring a browser or Puppeteer.
6. Save the PDF to `instance/cards/growth_card_{code}_{date}.pdf`.
7. Write a `GrowthCard` record to the database with the file path and delta snapshot.

The `GrowthCard` model stores a snapshot of the deltas at the time of generation. If a post-survey response is later corrected and the card is regenerated, the new deltas are stored in a new `GrowthCard` record — the old one is not overwritten.

---

### 3.7 Stage 7 — Delivery

The generated PDF can be delivered in two ways:

**Email** — using `nodemailer` (Node.js) or Flask-Mail (Python), the PDF is attached to an email sent to the participant's address. Since no email addresses are stored (privacy), this step requires a staff member to manually associate a code with a contact, or alternatively the email is collected in the form as an optional field.

**Download from dashboard** — staff can download any participant's card via `GET /api/cards/<code>`, which calls `send_file()` on the stored PDF path.

A `Drive URL` field on the `GrowthCard` model accommodates optional upload to a shared Google Drive folder via the Drive API, enabling batch sharing with school counsellors.

---

## 4. Database Schema

### Entity Relationship

```
users
  id PK
  email (unique)
  password (bcrypt hash)
  name
  role  ['admin' | 'staff']
  created_at
  is_active

participants
  id PK
  code (unique, indexed)   ← self-generated anonymous key
  cohort                   ← e.g. "platform_apr_2025"
  created_at

survey_responses
  id PK
  participant_id FK → participants.id
  survey_type    ['pre' | 'post']
  submitted_at
  sheet_row_index          ← deduplication key
  act_a1 … act_a6          ← raw item scores
  act_total                ← computed domain total
  act_connect, act_act, act_thrive  ← sub-domain totals
  cmi_b1 … cmi_b6
  cmi_total
  rsem_c1 … rsem_c10       ← raw scores (pre reverse-scoring)
  rsem_total               ← post reverse-scoring total (0–30)
  ewb_d1 … ewb_d6
  ewb_total
  reflect_e1 … reflect_e4  ← open text (post only)

growth_cards
  id PK
  participant_id FK → participants.id (one-to-one in practice)
  generated_at
  file_path
  drive_url
  emailed  BOOLEAN
  delta_act, delta_cmi, delta_rsem, delta_ewb  ← change score snapshot
  cohens_d                 ← individual effect size at time of generation
```

### Key design decisions

**No PII on participants.** The `participants` table stores only the self-generated code and cohort. Email addresses, names, and school details are never written to the database. This is a deliberate privacy design choice appropriate for working with youth-at-risk.

**Raw items stored alongside totals.** Both the individual item scores and the computed domain totals are stored. This means if the scoring rubric changes (e.g. a re-analysis of the Rosenberg reverse-scoring logic), totals can be recomputed from raw items without re-fetching the Google Sheet.

**`sheet_row_index` as deduplication key.** Rather than relying on timestamps (which can be identical for rapid submissions), the physical row index in the Google Sheet is used to guarantee idempotent processing.

---

## 5. Authentication & Route Protection

Authentication is handled by **Flask-Login** with **Flask-Bcrypt** password hashing.

### User roles

| Role | Capabilities |
|------|-------------|
| `staff` | View dashboard, view participants, download cards, trigger manual sync |
| `admin` | All staff capabilities + create/delete users, delete responses, export CSV |

### Protected route summary

| Route | Method | Auth | Role |
|-------|--------|------|------|
| `/dashboard` | GET | Required | any |
| `/dashboard/participant/<code>` | GET | Required | any |
| `/api/sync` | POST | Required | any |
| `/api/participants` | GET | Required | any |
| `/api/participants/<code>` | PUT | Required | any |
| `/api/participants/<code>` | DELETE | Required | admin |
| `/api/responses/<id>` | DELETE | Required | admin |
| `/api/cards/<code>` | GET | Required | any |
| `/api/export/csv` | GET | Required | admin |
| `/webhook/form-submit` | POST | Webhook secret | — |
| `/login` | GET/POST | None | — |

The webhook route at `/webhook/form-submit` is intentionally not protected by Flask-Login — it is called by Google Apps Script, not a human browser session. Instead it uses a shared HMAC secret validated via `hmac.compare_digest()` to prevent timing attacks.

---

## 6. Google Sheets API Integration

### Authentication method: Service Account

A **Service Account** is a bot identity created in Google Cloud Console. It has its own email address (e.g. `platform-bot@your-project.iam.gserviceaccount.com`). You share the Google Sheet with that email address (read-only access is sufficient), and download a JSON key file.

The key file is referenced in `GOOGLE_SERVICE_ACCOUNT_FILE` in `.env`. It is never committed to version control — add it to `.gitignore`.

### Setup steps

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or use an existing one)
3. Enable the **Google Sheets API** in APIs & Services → Library
4. Go to APIs & Services → Credentials → Create Credentials → Service Account
5. Download the JSON key and save as `service-account-key.json` in the project root
6. Open your Google Sheet → Share → paste the service account email → Viewer

### API call

```python
# sheets_service._get_service()
creds = service_account.Credentials.from_service_account_file(
    key_file, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
service = build("sheets", "v4", credentials=creds)

# Fetch rows A2:AJ (skipping header row 1)
result = service.spreadsheets().values().get(
    spreadsheetId=SHEET_ID,
    range="Sheet1!A2:AJ"
).execute()
rows = result.get("values", [])
```

### Quota

The Google Sheets API free tier allows 300 read requests per minute per project and 60 requests per minute per user. For a cohort of 30 participants, this quota will never be approached. Webhook-based processing makes only one API call per sync (the full sheet fetch), not one per row.

---

## 7. Scoring Logic Reference

All functions live in `app/services/score_service.py`. They are pure Python with no side effects and no framework dependencies.

| Function | Input | Output |
|----------|-------|--------|
| `compute_act_totals(row)` | dict with `act_a1`…`act_a6` | `act_total`, `act_connect`, `act_act`, `act_thrive` |
| `compute_cmi_total(row)` | dict with `cmi_b1`…`cmi_b6` | `cmi_total` |
| `compute_rsem_total(row)` | dict with `rsem_c1`…`rsem_c10` | `rsem_total` (reverse-scored) |
| `compute_ewb_total(row)` | dict with `ewb_d1`…`ewb_d6` | `ewb_total` |
| `compute_all_totals(row)` | full parsed row dict | all of the above |
| `compute_change_scores(pre, post)` | two dicts with `*_total` keys | `delta_act`, `delta_cmi`, `delta_rsem`, `delta_ewb` |
| `cohens_d(delta, std_dev)` | floats | effect size `d` |
| `effect_size_label(d)` | float | `"negligible"` / `"small"` / `"medium"` / `"large"` |
| `is_meaningful_change(delta, scale)` | float, str | bool |

---

## 8. Configuration & Environment Variables

Copy `.env.example` to `.env` and populate all values before running.

| Variable | Required | Description |
|----------|----------|-------------|
| `FLASK_ENV` | Yes | `development` or `production` |
| `SECRET_KEY` | Yes | Random string for session signing. Use `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DEV_DATABASE_URL` | No | SQLite path for dev. Defaults to `instance/platform_dev.db` |
| `DATABASE_URL` | Prod only | Full PostgreSQL connection string |
| `GOOGLE_SHEET_ID` | Yes | Found in the Sheet URL between `/d/` and `/edit` |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Yes | Path to the downloaded JSON key file |
| `WEBHOOK_SECRET` | Yes (prod) | Shared secret between Apps Script and Flask |
| `MAIL_USERNAME` | Optional | Gmail address for sending growth cards |
| `MAIL_PASSWORD` | Optional | Gmail App Password (not your account password) |

---

## 9. Running Locally

```bash
# 1. Clone and enter the project
git clone <repo>
cd .

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your values

# 5. Initialise the database
flask init-db

# 6. Create the first admin user
flask create-admin

# 7. Run the development server
flask run
# → http://127.0.0.1:5000

# 8. (Optional) Manually sync from Google Sheets
flask sync
# or via the API after logging in:
# POST http://127.0.0.1:5000/api/sync
```

---

## 10. Deployment

The application is stateless between requests and deploys cleanly to any Python-compatible host. Recommended platforms:

### Railway (easiest)

```bash
# railway.app — connect GitHub repo, set env vars in dashboard
# Railway auto-detects Flask and runs: flask run --host=0.0.0.0
```

Add a PostgreSQL plugin in the Railway dashboard. It will inject `DATABASE_URL` automatically.

### Render

```bash
# render.com — set Build Command and Start Command:
# Build:  pip install -r requirements.txt
# Start:  gunicorn run:app
```

### Cloud Run (Google Cloud)

Cloud Run does not execute `Procfile` release hooks. The `release: flask db upgrade`
line in `Procfile` only applies on Procfile-aware platforms (for example Railway/Heroku).

For Cloud Run, run Alembic migrations explicitly before deploy. This repository uses
Cloud Build with a migration gate step:

```bash
gcloud run jobs execute slushies-migrate --region=asia-southeast1 --wait
```

Then deploy the service revision.

### Production checklist

- [ ] `FLASK_ENV=production` in environment
- [ ] `SECRET_KEY` is a long random string (32+ bytes)
- [ ] `DATABASE_URL` points to PostgreSQL, not SQLite
- [ ] Cloud Run service has required vars/secrets: `DATABASE_URL`, `SECRET_KEY`, `GOOGLE_SHEET_ID`, `WEBHOOK_SECRET`
- [ ] Cloud Run migration job (`slushies-migrate`) succeeds before service deploy
- [ ] `service-account-key.json` is uploaded as a secret file (not in the repo)
- [ ] `WEBHOOK_SECRET` is set and matches Apps Script
- [ ] Apps Script `WEBHOOK_URL` points to the active Cloud Run region (for this project: `https://slushies-411994757215.asia-southeast1.run.app/webhook/form-submit`)
- [ ] `instance/cards/` directory exists and is writable
- [ ] HTTPS is enforced (Railway and Render do this automatically)

---

## 11. Testing

```bash
# Run all tests
pytest tests/

# Run with coverage
pip install pytest-cov
pytest --cov=app tests/
```

`tests/test_score_service.py` covers:
- ACT SG total and sub-domain computation
- Rosenberg reverse-scoring (positive and reverse items)
- CMI and EWB totals
- Change score calculation
- Cohen's d computation and edge cases (zero SD)
- Effect size labelling
- Meaningful change thresholds per scale

The scoring service has no Flask or database dependency, so tests run without any app context or fixtures.

---

## 12. Security Considerations

| Risk | Mitigation |
|------|-----------|
| Unauthenticated dashboard access | Flask-Login required on all `/dashboard` and `/api` routes |
| Fake webhook submissions | HMAC shared secret on `/webhook/form-submit`; `hmac.compare_digest()` prevents timing attacks |
| Participant re-identification | No PII stored; codes are self-generated mnemonics with no lookup table |
| SQL injection | All queries via SQLAlchemy ORM; no raw SQL strings |
| Session hijacking | `SECRET_KEY` signs session cookies; HTTPS enforced in production |
| Service account key exposure | JSON key file is git-ignored; deployed as a secret environment file |
| Brute-force login | Rate limiting can be added via `flask-limiter` as the system scales |

---

## 13. Extending the System

### Adding a new psychometric scale

1. Add columns to `SurveyResponse` in `models.py` (new item scores + domain total).
2. Run `flask db migrate && flask db upgrade` to update the schema.
3. Add the column index to `COL_MAP` in `sheets_service.py`.
4. Add a `compute_<scale>_total()` function to `score_service.py`.
5. Call it inside `compute_all_totals()`.
6. Add a corresponding card panel to `templates/cards/growth_card.html`.
7. Add unit tests to `tests/test_score_service.py`.

### Adding a new programme cohort

Update the `cohort` field on `Participant` records via the `/api/participants/<code>` PUT endpoint, or set it during the sync step by deriving it from the Google Sheet tab name.

### Scaling to multiple programmes

The `Participant.cohort` field and `SurveyResponse.survey_type` field are intentionally generic. Running a second programme (e.g. "lohi" or "dudu") requires only a second pair of Google Forms linked to new tabs on the same sheet — no code changes needed, as long as the column order matches `COL_MAP`.

### Adding email delivery

Install Flask-Mail (`pip install flask-mail`), configure `MAIL_*` variables in `.env`, and call `mail.send_message()` in `sync_service.process_row()` after `generate_card()` returns a path. The `GrowthCard.emailed` boolean tracks delivery status.
